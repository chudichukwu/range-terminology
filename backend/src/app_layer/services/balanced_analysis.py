"""Present the shared balanced-range evaluator through the existing analysis API."""

import time
from dataclasses import asdict
from functools import lru_cache

import pandas as pd

from market_data.validation import validate_sequence
from range_engine.balanced import (
    CONTEXT_TIMEFRAMES,
    ENTRY_TIMEFRAMES,
    Timeline,
    evaluate_entry,
    settings,
    trade_plan,
)
from signal_engine.structure import swing_failures
from range_engine.context import range_observations, nearby_levels


@lru_cache(maxsize=128)
def _closed_timeline(bars, config_items):
    """Reuse deterministic structure across scans, chart views and alert checks.

    The key includes every closed candle and setting: new/corrected history or
    strategy changes rebuild it. Live price and freshness are never cached here.
    Callers only read the returned timeline.
    """
    return Timeline(bars, dict(config_items))


def analyze_balanced(
    markets, actor, symbol, timeframe, payload, strategy_id, name, limit, now_ms=None
):
    cfg = settings(payload)
    now = now_ms or time.time_ns() // 1_000_000
    datasets, timelines, issues = {}, {}, []
    stale = False
    for tf in dict.fromkeys((*CONTEXT_TIMEFRAMES, timeframe)):
        ds = markets.candles(
            symbol, tf,
            limit=max(limit if tf == timeframe else 200, int(cfg["lookback"]) + 60),
            include_current=True
        )
        datasets[tf] = ds
        closed = tuple(b for b in ds.candles if b.is_closed and b.close_time_ms <= now)
        report = validate_sequence(ds.symbol, ds.timeframe, closed).report
        errors = set(report.issue_kinds) | (
            set(ds.quality.issue_kinds) - {"unclosed_candle_present"}
        )
        issues.extend(f"{tf}: {e}" for e in errors)
        if not closed or now > closed[-1].close_time_ms + ds.timeframe.duration_ms + 300000:
            stale = True
        timelines[tf] = _closed_timeline(closed, tuple(sorted(cfg.items())))
    ds, timeline = datasets[timeframe], timelines[timeframe]
    bars = timeline.bars
    decision = evaluate_entry(bars, timelines, cfg) if timeframe in ENTRY_TIMEFRAMES else None
    snap = timeline.at(now)
    if decision is None:
        decision = dict(
            direction="none",
            reason="Context only — confirm entries on 15m, 5m or 1m",
            state=snap.state,
            range_timeframe=timeframe,
            snapshot=snap,
            sfp=None,
            contexts={tf: timelines[tf].at(now) for tf in CONTEXT_TIMEFRAMES},
        )
    failures = []
    # Chart observations use this timeframe's own pre-sweep range. Trade eligibility
    # remains governed by the 4H/1H playbook above.
    for i in range(20, len(bars) + 1):
        event = evaluate_entry(
            bars[:i], timelines, cfg, range_timeframes=(timeframe,)
        ).get("sfp")
        if event and event not in failures:
            failures.append(event)
    # Swing observations do not require a tradable range or an approved entry.
    if bars:
        frame = pd.DataFrame([dict(timestamp=b.timestamp, high=b.high, low=b.low,
                                   close=b.close) for b in bars])
        keys = {(e["timestamp"], e["direction"]) for e in failures}
        failures.extend({**e, "kind": "swing", "grade": None} for e in swing_failures(
            frame, pivot_window=int(cfg["pivot_window"]), lookback=int(cfg["lookback"]),
            recent=len(bars)
        ) if (e["timestamp"], e["direction"]) not in keys)
        failures.sort(key=lambda e: e["timestamp"])
    chart_state = (
        "sfp" if failures and failures[-1]["timestamp"] == bars[-1].timestamp else snap.state
    )
    if issues or stale:
        decision = {
            **decision,
            "direction": "none",
            "reason": "Stale or incomplete multi-timeframe data",
        }
    plan = trade_plan(decision, cfg)
    if plan and not plan["approved"]:
        decision = {
            **decision,
            "direction": "none",
            "reason": "Minimum weighted reward/risk not met",
        }
    lo, hi = snap.low, snap.high
    price = ds.candles[-1].close if ds.candles else None
    pos = (price - lo) / (hi - lo) if price and lo is not None and hi > lo else None
    entry_snap = decision.get("snapshot") or snap
    entry_pos = (
        (price - entry_snap.low) / (entry_snap.high - entry_snap.low)
        if price is not None and entry_snap.low is not None and entry_snap.high > entry_snap.low
        else None
    )
    contexts = {
        tf: {
            **asdict(s),
            "midpoint": s.midpoint,
            "role": "context" if tf in ("1w", "1d") else "range",
        }
        for tf, s in decision["contexts"].items()
    }
    return dict(
        symbol=symbol,
        timeframe=timeframe,
        strategy_id=strategy_id,
        strategy_name=name,
        ticker_last=price,
        ticker_bid=None,
        ticker_ask=None,
        ticker_timestamp_ms=ds.retrieved_at_ms,
        candles=[
            dict(
                timestamp=b.timestamp,
                open=b.open,
                high=b.high,
                low=b.low,
                close=b.close,
                volume=b.volume,
                is_closed=b.is_closed,
            )
            for b in ds.candles
        ],
        swing_failures=failures,
        range_events=range_observations(bars, timeline, cfg),
        quality_issues=issues,
        is_analysis_safe=not issues,
        range=dict(
            high=hi,
            low=lo,
            width=hi - lo if lo is not None else None,
            status=snap.state,
            confidence=min(1.0, min(snap.low_touches, snap.high_touches) / 3),
            is_tradable=snap.valid,
            mode="balanced",
            metadata=dict(
                low_touches=snap.low_touches,
                high_touches=snap.high_touches,
                reason=snap.reason,
                reclaimed=snap.reclaimed,
                structure_confirmed=bool(snap.established),
                preceding_trend=snap.preceding_trend,
                trend_context=snap.trend,
                nearby_levels=nearby_levels(bars, snap, cfg),
                range_policy=cfg["range_policy"],
                midpoint=snap.midpoint,
                atr=snap.atr,
                adx=snap.adx,
                range_timeframe=timeframe,
            ),
        ),
        regime=dict(
            value="trending_" + snap.trend if snap.trend else snap.state,
            lookback=int(cfg["lookback"]),
            threshold=cfg["adx_max"],
            efficiency_ratio=None,
        ),
        signal=dict(
            direction=decision["direction"],
            reason=decision["reason"],
            price=decision.get("entry", price),
            position_in_range=entry_pos,
            confidence=1.0 if decision.get("sfp") else 0.0,
            confirmation=decision["direction"] != "none",
            confirmation_policy="closed_candle",
            range_high=entry_snap.high,
            range_low=entry_snap.low,
            metadata=dict(
                state=decision["state"],
                grade="A+" if decision.get("sfp") else None,
                range_timeframe=decision["range_timeframe"],
                signal_timestamp=decision.get("timestamp"),
                no_fade=snap.state == "trending",
                at_extreme=(
                    snap.valid
                    and pos is not None
                    and (0 <= pos <= cfg["edge_zone"] or 1 - cfg["edge_zone"] <= pos <= 1)
                ),
                tp1=decision.get("tp1"),
                tp2=decision.get("tp2"),
            ),
        ),
        oscillator=dict(
            value=None, type=None, overbought=None, oversold=None, is_confirmation=None
        ),
        risk=plan,
        freshness=dict(
            retrieved_at_ms=ds.retrieved_at_ms or now,
            age_ms=now - (ds.retrieved_at_ms or now),
            is_stale=stale,
            has_forming_candle=any(not b.is_closed for b in ds.candles),
            last_closed_timestamp_ms=bars[-1].timestamp if bars else None,
        ),
        market_state=chart_state,
        timeframe_context=contexts,
    )
