"""Causal observations, separate from trade triggers and projected outcomes."""
from range_engine.structural import _find_pivot_highs, _find_pivot_lows
import numpy as np


def range_observations(bars, timeline, cfg):
    events = []
    last = {}
    for i in range(1, len(bars)):
        bar, prev = bars[i], bars[i-1]
        snap = timeline.at(bar.timestamp)
        if not snap.established or snap.low is None or snap.high <= snap.low or snap.state == "breakout":
            continue
        mid = snap.midpoint
        band = max((snap.high - snap.low) * .03, (snap.atr or 0) * .1)
        if not snap.low <= bar.close <= snap.high:
            continue
        kind = None
        if prev.close < mid - band and bar.close > mid + band:
            kind = "midpoint_reclaim"
        elif prev.close > mid + band and bar.close < mid - band:
            kind = "midpoint_lost"
        elif prev.close < mid - band and bar.high >= mid - band and bar.close < mid - band and bar.close < bar.open:
            kind = "midpoint_rejection"
        elif prev.close > mid + band and bar.low <= mid + band and bar.close > mid + band and bar.close > bar.open:
            kind = "midpoint_support"
        key = (snap.established, kind)
        if kind and i - last.get(key, -100) >= 3:
            repeated = kind in ("midpoint_rejection", "midpoint_support") and i - last.get(key, -100) <= 20
            last[key] = i
            events.append(dict(kind=kind, repeated=repeated, timestamp=bar.timestamp, level=mid,
                               range_low=snap.low, range_high=snap.high,
                               range_established=snap.established))
    return events


def nearby_levels(bars, snap, cfg):
    """Only pivots fully confirmed BEFORE the range began can be external POIs."""
    if not snap.origin or snap.low is None or not snap.atr:
        return []
    prior = [b for b in bars if b.close_time_ms <= snap.origin][-int(cfg['lookback']):]
    if len(prior) < 2 * int(cfg['pivot_window']) + 1:
        return []
    levels = []
    for kind, attr, finder, boundary in (
        ('prior_support', 'low', _find_pivot_lows, snap.low),
        ('prior_resistance', 'high', _find_pivot_highs, snap.high),
    ):
        values = np.array([getattr(b, attr) for b in prior])
        candidates = [j for j in finder(values, int(cfg['pivot_window']))
                      if abs(float(values[j]) - boundary) <= snap.atr]
        if candidates:
            j = min(candidates, key=lambda j: abs(float(values[j]) - boundary))
            levels.append(dict(kind=kind, price=float(values[j]), timestamp=prior[j].timestamp,
                               distance_atr=abs(float(values[j])-boundary)/snap.atr))
    return levels
