"""Causal multi-timeframe range/reclaim rules, shared by live scans and replay."""

import math
from bisect import bisect_right
from dataclasses import dataclass

import numpy as np
import pandas as pd

from range_engine.structural import _find_pivot_highs, _find_pivot_lows

DEFAULTS = dict(
    lookback=100,
    pivot_window=2,
    min_touches=2,
    touch_tolerance=0.05,
    min_height_atr=2.5,
    adx_max=22.0,
    adx_trend=25.0,
    ema_slope_atr=0.15,
    edge_zone=0.15,
    stop_buffer_atr=0.375,
    breakout_buffer_atr=0.375,
    hold_closes=2,
    reclaim_bars=3,
    volume_multiple=0.0,
    tp1_fraction=0.5,
    target_inset=0.02,
    min_reward_risk=2.0,
    risk_per_trade=0.01,
    max_leverage=3.0,
    confirmation="sfp_or_rejection",
    range_policy="contextual",
    runner_fraction=0.0,
    runner_trail_percent=0.02,
)
ENTRY_TIMEFRAMES = ("1m", "5m", "15m")
CONTEXT_TIMEFRAMES = ("1w", "1d", "4h", "1h")


def settings(payload):
    cfg = dict(DEFAULTS)
    for key in ("range_config", "signal_config", "risk_config"):
        cfg.update({k: v for k, v in payload.get(key, {}).items() if k in DEFAULTS})
    for key, default in DEFAULTS.items():
        value = cfg[key]
        if key == "range_policy":
            if value not in ("contextual", "strict"):
                raise ValueError("range_policy must be contextual or strict")
            continue
        if key == "confirmation":
            if value not in ("sfp", "sfp_or_rejection", "any"):
                raise ValueError("confirmation must be sfp, sfp_or_rejection or any")
            continue
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError(f"{key} must be a finite number")
        if isinstance(default, int) and (int(value) != value or value < 1):
            raise ValueError(f"{key} must be a positive integer")
        if value < 0:
            raise ValueError(f"{key} cannot be negative")
    if not 20 <= cfg["lookback"] <= 500 or not 1 <= cfg["pivot_window"] <= 10:
        raise ValueError("Lookback must be 20–500 and swing confirmation 1–10")
    if cfg["min_touches"] < 2 or not 0 < cfg["touch_tolerance"] <= 0.15:
        raise ValueError("Require 2+ touches per boundary and tolerance within (0, 15%]")
    if not 0 < cfg["adx_max"] < cfg["adx_trend"] <= 100:
        raise ValueError("Range ADX must be below trend ADX, at most 100")
    if not 0 < cfg["edge_zone"] <= 0.25 or not 1 <= cfg["reclaim_bars"] <= 3:
        raise ValueError("Edge zone must be within (0, 25%]; reclaim window 1–3 bars")
    if not 0 < cfg["tp1_fraction"] < 1 or not 0 <= cfg["target_inset"] < 0.25:
        raise ValueError("TP1 fraction must be within (0, 100%); target inset below 25%")
    if not 0 <= cfg["runner_fraction"] < 1 - cfg["tp1_fraction"] or not 0 < cfg["runner_trail_percent"] < 1:
        raise ValueError("Runner plus TP1 must be below 100%; trailing distance within (0, 100%)")
    if cfg["stop_buffer_atr"] <= 0 or cfg["min_height_atr"] <= 0:
        raise ValueError("ATR stop buffer and minimum range height must be positive")
    if cfg["min_reward_risk"] < 2 or not 0 < cfg["risk_per_trade"] <= 0.1:
        raise ValueError("Minimum reward/risk must be at least 2; equity risk at most 10%")
    if cfg["max_leverage"] < 1 or cfg["hold_closes"] > 5:
        raise ValueError("Leverage must be at least 1; hold period at most 5 closes")
    return cfg


def _wilder(values, period=14, start=0):
    out = np.full(len(values), np.nan)
    if len(values) < start + period:
        return out
    i = start + period - 1
    out[i] = np.mean(values[start : i + 1])
    for j in range(i + 1, len(values)):
        out[j] = (out[j - 1] * (period - 1) + values[j]) / period
    return out


def indicators(bars):
    """Wilder ATR/ADX (14), seeded averages, plus EMA20/50."""
    if not bars:
        return {}
    h, low, c = (np.array([getattr(b, k) for b in bars]) for k in ("high", "low", "close"))
    prev = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - low, np.maximum(abs(h - prev), abs(low - prev)))
    up, down = np.r_[0.0, np.diff(h)], np.r_[0.0, -np.diff(low)]
    plus, minus = (
        np.where((up > down) & (up > 0), up, 0.0),
        np.where((down > up) & (down > 0), down, 0.0),
    )
    atr = _wilder(tr, start=1)
    p, m = _wilder(plus, start=1), _wilder(minus, start=1)
    total = p + m
    dx = np.divide(100 * abs(p - m), total, out=np.zeros(len(c)), where=total > 0)
    dx[:14] = np.nan
    return dict(
        atr=atr,
        adx=_wilder(dx, start=14),
        ema20=pd.Series(c).ewm(span=20, adjust=False).mean().to_numpy(),
        ema50=pd.Series(c).ewm(span=50, adjust=False).mean().to_numpy(),
    )


@dataclass(frozen=True)
class Snapshot:
    time: int
    state: str
    low: float | None = None
    high: float | None = None
    atr: float | None = None
    adx: float | None = None
    ema20: float | None = None
    ema50: float | None = None
    trend: str | None = None
    low_touches: int = 0
    high_touches: int = 0
    reason: str = ""
    established: int = 0
    reclaimed: bool = False
    origin: int = 0
    preceding_trend: str | None = None

    @property
    def valid(self):
        return self.state == "ranging"

    @property
    def midpoint(self):
        return (self.low + self.high) / 2 if self.low is not None else None


def _cluster(values, tolerance, *, outer=None, min_touches=2):
    """Choose a supported outer cluster when requested; ignore isolated outlier wicks."""
    if not values:
        return None, 0
    groups = [[v for v in values if abs(v - center) <= tolerance] for center in values]
    supported = [g for g in groups if len(g) >= min_touches]
    if outer and supported:
        best = (max if outer == "high" else min)(supported, key=np.median)
        return float(np.median(best)), len(best)
    best = max(
        groups,
        key=lambda group: (len(group), -float(np.std(group))),
    )
    return float(np.median(best)), len(best)


def range_timeline(bars, cfg):
    """Freeze boundaries; retain broken ranges for a close back inside within lookback."""
    ind = indicators(bars)
    snapshots = []
    anchor = None
    broken = None
    reclaimed = False
    retired_at = 0
    outside = 0
    origin, preceding_trend = 0, None
    for i, bar in enumerate(bars):
        t = bar.close_time_ms
        if i < 54:
            snapshots.append(Snapshot(t, "insufficient_data", reason="Indicator warm-up"))
            continue
        atr, adx, e20, e50 = (float(ind[k][i]) for k in ("atr", "adx", "ema20", "ema50"))
        prior = bars[max(retired_at, i - int(cfg["lookback"]) + 1) : i + 1]
        hs, ls = np.array([b.high for b in prior]), np.array([b.low for b in prior])
        ph, pl = (
            _find_pivot_highs(hs, int(cfg["pivot_window"])),
            _find_pivot_lows(ls, int(cfg["pivot_window"])),
        )
        highs, lows = [float(hs[j]) for j in ph], [float(ls[j]) for j in pl]
        epsilon = atr * 0.05
        hh = len(highs) >= 3 and all(
            b > a + epsilon for a, b in zip(highs[-3:-1], highs[-2:], strict=True)
        )
        hl = len(lows) >= 3 and all(
            b > a + epsilon for a, b in zip(lows[-3:-1], lows[-2:], strict=True)
        )
        lh = len(highs) >= 3 and all(
            b < a - epsilon for a, b in zip(highs[-3:-1], highs[-2:], strict=True)
        )
        ll = len(lows) >= 3 and all(
            b < a - epsilon for a, b in zip(lows[-3:-1], lows[-2:], strict=True)
        )
        hold_up = all(
            b.close > max(ind["ema20"][j], ind["ema50"][j])
            for j, b in enumerate(bars[i - 2 : i + 1], start=i - 2)
        )
        hold_down = all(
            b.close < min(ind["ema20"][j], ind["ema50"][j])
            for j, b in enumerate(bars[i - 2 : i + 1], start=i - 2)
        )
        direction = "up" if hh and hl else "down" if lh and ll else None
        trend = (
            ("up" if hold_up else "down" if hold_down else direction)
            if adx >= cfg["adx_trend"]
            else None
        )
        flat = all(
            abs(ind[k][i] - ind[k][i - 5]) / 5 <= atr * cfg["ema_slope_atr"]
            for k in ("ema20", "ema50")
        )
        common = dict(atr=atr, adx=adx, ema20=e20, ema50=e50, trend=trend or direction)
        if broken and anchor is None:
            old, broken_index = broken
            if i - broken_index > int(cfg["lookback"]):
                broken = None
            elif old[0] < bar.close < old[1]:
                # Start a new lifecycle; previously stopped trades stay stopped.
                anchor = (*old[:4], t)
                reclaimed = True
                broken, outside = None, 0
        if anchor:
            lo, hi, ntl, nth, established = anchor
            ntl = max(ntl, sum(abs(v - lo) <= (hi - lo) * cfg["touch_tolerance"] for v in lows))
            nth = max(nth, sum(abs(v - hi) <= (hi - lo) * cfg["touch_tolerance"] for v in highs))
            anchor = lo, hi, ntl, nth, established
            side = (
                1
                if bar.close > hi + atr * cfg["breakout_buffer_atr"]
                else -1
                if bar.close < lo - atr * cfg["breakout_buffer_atr"]
                else 0
            )
            outside = outside + side if side and outside * side > 0 else side
            if abs(outside) >= cfg["hold_closes"]:
                snapshots.append(
                    Snapshot(
                        t,
                        "breakout",
                        lo,
                        hi,
                        **common,
                        low_touches=ntl,
                        high_touches=nth,
                        reason="Closes outside and holds",
                        established=established,
                        origin=origin, preceding_trend=preceding_trend,
                    )
                )
                broken = (anchor, i)
                anchor, retired_at, outside = None, i + 1, 0
                reclaimed = False
                continue
            state = (
                "trending"
                if trend or direction or adx >= cfg["adx_trend"]
                else "ranging"
                if adx < cfg["adx_max"]
                and flat
                and lo <= bar.close <= hi
                and hi - lo >= atr * cfg["min_height_atr"]
                else "transition"
            )
            if cfg["range_policy"] == "contextual":
                state = "ranging" if lo <= bar.close <= hi and hi - lo >= atr * cfg["min_height_atr"] else "transition"
            snapshots.append(
                Snapshot(
                    t,
                    state,
                    lo,
                    hi,
                    **common,
                    low_touches=ntl,
                    high_touches=nth,
                    reason="Don't fade extremes"
                    if state == "trending"
                    else "Awaiting balance"
                    if state != "ranging"
                    else "Reclaimed range" if reclaimed else "Confirmed local range",
                    established=established,
                    reclaimed=reclaimed,
                    origin=origin, preceding_trend=preceding_trend,
                )
            )
            continue
        if not highs or not lows or not atr > 0:
            snapshots.append(Snapshot(t, "transition", **common, reason="Awaiting repeated swings"))
            continue
        # Prefer the widest supported history; fall back to recent local pauses.
        candidates = [prior]
        if cfg["range_policy"] == "contextual":
            candidates += [prior[-n:] for n in (60, 40, 24) if len(prior) > n]
        reason = "Awaiting repeated swings"
        for candidate in candidates:
            hs, ls = np.array([b.high for b in candidate]), np.array([b.low for b in candidate])
            ph, pl = _find_pivot_highs(hs, int(cfg["pivot_window"])), _find_pivot_lows(ls, int(cfg["pivot_window"]))
            highs, lows = [float(hs[j]) for j in ph], [float(ls[j]) for j in pl]
            if not highs or not lows:
                continue
            tolerance = (max(highs) - min(lows)) * cfg["touch_tolerance"]
            hi, nth = _cluster(highs, tolerance, outer="high", min_touches=cfg["min_touches"])
            lo, ntl = _cluster(lows, tolerance, outer="low", min_touches=cfg["min_touches"])
            matches = [j for j in ph if abs(hs[j] - hi) <= tolerance] + [j for j in pl if abs(ls[j] - lo) <= tolerance]
            contained = all(lo - tolerance <= b.close <= hi + tolerance for b in candidate[min(matches):]) if matches else False
            reason = (
                "Awaiting 2+ touches on both sides" if min(ntl, nth) < cfg["min_touches"]
                else "Range too small relative to ATR" if hi - lo < atr * cfg["min_height_atr"]
                else "Closes outside candidate range" if not contained or not lo <= bar.close <= hi
                else ""
            )
            if not reason:
                origin = candidate[min(matches)].timestamp
                before = [b for b in bars[:i+1] if b.timestamp < origin][-20:]
                move = before[-1].close - before[0].close if len(before) >= 5 else 0
                preceding_trend = "up" if move > 2 * atr else "down" if move < -2 * atr else None
                break
        structure_valid = not reason
        if structure_valid:
            anchor = lo, hi, ntl, nth, t
            broken, reclaimed = None, False
        trending = bool(trend or direction or adx >= cfg["adx_trend"])
        if trending:
            reason = "Don't fade extremes"
        elif structure_valid and (adx >= cfg["adx_max"] or not flat):
            reason = "Range structure found; awaiting balance for entry"
        state = "trending" if trending else "transition" if reason else "ranging"
        if cfg["range_policy"] == "contextual":
            state = "ranging" if structure_valid else "developing"
            if structure_valid:
                reason = "Confirmed local range; trend is separate context"
        snapshots.append(
            Snapshot(
                t,
                state,
                lo,
                hi,
                **common,
                low_touches=ntl,
                high_touches=nth,
                reason=reason or "Confirmed balance",
                established=t if structure_valid else 0,
                origin=origin if structure_valid else 0, preceding_trend=preceding_trend if structure_valid else None,
            )
        )
    return snapshots


class Timeline:
    def __init__(self, bars, cfg):
        self.bars = tuple(b for b in bars if b.is_closed)
        self.snapshots = range_timeline(self.bars, cfg)
        self.times = [s.time for s in self.snapshots]

    def at(self, timestamp):
        i = bisect_right(self.times, timestamp) - 1
        return self.snapshots[i] if i >= 0 else Snapshot(timestamp, "insufficient_data")


def evaluate_entry(bars, timelines, cfg, *, range_timeframes=("4h", "1h")):
    """Confirm only from closed entry bars and HTF bars closed before the sweep."""
    waiting = dict(
        direction="none",
        reason="Waiting for confirmation",
        state="transition",
        snapshot=None,
        range_timeframe=None,
        contexts={},
        sfp=None,
    )
    if len(bars) < 20:
        return {**waiting, "reason": "Entry history warm-up"}
    current = bars[-1]
    contexts = {tf: timelines[tf].at(current.close_time_ms) for tf in CONTEXT_TIMEFRAMES}
    waiting["contexts"] = contexts
    # Start with the earliest unreclaimed sweep so its wick defines the protective stop.
    for offset in range(int(cfg["reclaim_bars"]), 0, -1):
        sweep = bars[-offset]
        selected = next(
            (
                (tf, timelines[tf].at(sweep.timestamp))
                for tf in range_timeframes
                if timelines[tf].at(sweep.timestamp).valid
            ),
            None,
        )
        if selected is None:
            continue
        tf, snap = selected
        latest_range = timelines[tf].at(current.close_time_ms)
        if latest_range.state == "breakout" or (cfg["range_policy"] == "strict" and latest_range.state == "trending") or (
            latest_range.established and latest_range.established != snap.established
        ):
            waiting.update(
                snapshot=latest_range,
                range_timeframe=tf,
                state=latest_range.state,
                reason=latest_range.reason,
            )
            continue
        lo, hi = snap.low, snap.high
        width, midpoint = hi - lo, snap.midpoint
        waiting.update(snapshot=snap, range_timeframe=tf, state="ranging")
        seq = bars[-offset:]
        # A reclaim cannot revive an already invalidated instance of this range.
        hold_bars = [b.close for b in bars if b.timestamp >= snap.established]
        values = np.asarray(hold_bars)
        hold_count = int(cfg["hold_closes"])
        held = len(values) >= hold_count and any(
            np.any(
                np.convolve(side.astype(int), np.ones(hold_count, dtype=int), "valid") == hold_count
            )
            for side in (
                values > hi + snap.atr * cfg["breakout_buffer_atr"],
                values < lo - snap.atr * cfg["breakout_buffer_atr"],
            )
        )
        if held:
            waiting.update(state="breakout", reason="Closes outside and holds")
            return waiting
        if sweep.low < lo and sweep.high > hi:
            continue
        bull = sweep.low < lo and lo < current.close <= hi
        bear = sweep.high > hi and lo <= current.close < hi
        # Reclaim fires once; bars after an earlier reclaim cannot re-alert the sweep.
        if offset > 1 and (any(lo < b.close < hi for b in seq[:-1]) or not (bull or bear)):
            continue
        sfp = bull != bear and (bull or bear)
        lower = sweep.low <= lo + width * cfg["edge_zone"] and current.close < midpoint
        upper = sweep.high >= hi - width * cfg["edge_zone"] and current.close > midpoint
        body = abs(current.close - current.open)
        wick = (
            min(current.open, current.close) - current.low
            >= max(body * 2, (current.high - current.low) * 0.5)
            and current.close > current.open
            and lower
        ) or (
            current.high - max(current.open, current.close)
            >= max(body * 2, (current.high - current.low) * 0.5)
            and current.close < current.open
            and upper
        )
        prev = bars[-2]
        engulf = (
            lower
            and current.close > current.open
            and prev.close < prev.open
            and current.open <= prev.close
            and current.close >= prev.open
        ) or (
            upper
            and current.close < current.open
            and prev.close > prev.open
            and current.open >= prev.close
            and current.close <= prev.open
        )
        shift = (lower and current.close > max(b.high for b in bars[-4:-1])) or (
            upper and current.close < min(b.low for b in bars[-4:-1])
        )
        trigger = (
            "sfp"
            if sfp
            else "rejection"
            if offset == 1 and wick and cfg["confirmation"] != "sfp"
            else "engulfing"
            if offset == 1 and engulf and cfg["confirmation"] == "any"
            else "structure_shift"
            if offset == 1 and shift and cfg["confirmation"] == "any"
            else None
        )
        if not trigger or not lo < current.close < hi:
            continue
        direction = "long" if (bull if sfp else lower) else "short"
        if (direction == "long" and not lower) or (direction == "short" and not upper):
            continue
        volumes = [b.volume for b in bars[-20 - offset : -offset] if b.volume is not None]
        if cfg["volume_multiple"] and (
            not volumes
            or sweep.volume is None
            or sweep.volume < np.mean(volumes) * cfg["volume_multiple"]
        ):
            waiting["reason"] = "Sweep volume filter not met"
            continue
        failure = (
            dict(
                direction="bullish" if direction == "long" else "bearish",
                level=lo if direction == "long" else hi,
                timestamp=current.timestamp,
                swing_timestamp=sweep.timestamp,
                grade="A+",
                range_timeframe=tf,
            )
            if sfp
            else None
        )
        blocked = [
            key
            for key in ("1w", "1d")
            if contexts[key].trend == ("down" if direction == "long" else "up")
            or (contexts[key].state == "trending" and contexts[key].trend is None)
        ]
        if any(contexts[key].state == "insufficient_data" for key in ("1w", "1d")):
            waiting.update(reason="Higher-timeframe context unavailable", sfp=failure)
            continue
        if blocked:
            waiting.update(
                reason=f"Against higher-timeframe trend: {', '.join(blocked)}", sfp=failure
            )
            continue
        sign = 1 if direction == "long" else -1
        extreme = min(b.low for b in seq) if sign == 1 else max(b.high for b in seq)
        stop = (
            min(lo, extreme) - snap.atr * cfg["stop_buffer_atr"]
            if sign == 1
            else max(hi, extreme) + snap.atr * cfg["stop_buffer_atr"]
        )
        target = hi - width * cfg["target_inset"] if sign == 1 else lo + width * cfg["target_inset"]
        return dict(
            direction=direction,
            reason=trigger,
            state="sfp" if sfp else "ranging",
            snapshot=snap,
            range_timeframe=tf,
            contexts=contexts,
            sfp=failure,
            entry=current.close,
            stop=stop,
            tp1=midpoint,
            tp2=target,
            timestamp=current.timestamp,
            atr=snap.atr,
        )
    if waiting["snapshot"] is None:
        visible = next(
            ((tf, timelines[tf].at(current.close_time_ms)) for tf in range_timeframes
             if timelines[tf].at(current.close_time_ms).low is not None),
            (range_timeframes[0], timelines[range_timeframes[0]].at(current.close_time_ms)),
        )
        waiting.update(
            range_timeframe=visible[0],
            snapshot=visible[1],
            state=visible[1].state,
            reason=visible[1].reason,
        )
    return waiting


def trade_plan(signal, cfg, equity=10000.0, fee=0.0005, slippage=0.0002, entry=None):
    if signal["direction"] == "none":
        return None
    price = signal["entry"] if entry is None else entry
    sign = 1 if signal["direction"] == "long" else -1
    stop, tp1, tp2 = signal["stop"], signal["tp1"], signal["tp2"]
    distance = sign * (price - stop)
    tp2_fraction = 1 - cfg["tp1_fraction"] - cfg["runner_fraction"]
    reward = cfg["tp1_fraction"] * sign * (tp1 - price) + tp2_fraction * sign * (
        tp2 - price
    )
    costs = (price + cfg["tp1_fraction"] * tp1 + tp2_fraction * tp2 + cfg["runner_fraction"] * price) * (fee + slippage)
    rr = (reward - costs) / (distance + (price + stop) * (fee + slippage)) if distance > 0 else -1
    approved = (
        distance > 0 and sign * (tp1 - price) > 0 and rr >= cfg["min_reward_risk"] and stop > 0
    )
    qty = (
        min(
            equity * cfg["risk_per_trade"] / (distance + (price + stop) * (fee + slippage)),
            equity * cfg["max_leverage"] / price,
        )
        if approved
        else None
    )
    return dict(
        approved=approved,
        status="approved" if approved else "rejected",
        rejection_reason=None if approved else "minimum_weighted_reward_risk",
        entry_price=price,
        stop_price=stop,
        target_price=tp1,
        position_quantity=qty,
        risk_amount=qty * distance if qty else None,
        reward_risk_ratio=rr,
        metadata=dict(
            tp2=tp2,
            tp1_fraction=cfg["tp1_fraction"],
            tp2_fraction=tp2_fraction,
            runner_fraction=cfg["runner_fraction"],
            runner_trail_percent=cfg["runner_trail_percent"],
            runner_reward_assumption="exit_at_entry_after_costs",
            range_timeframe=signal["range_timeframe"],
            min_reward_risk=cfg["min_reward_risk"],
        ),
    )
