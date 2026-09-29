"""Closed-candle swing failures and touch entries against already-known ranges."""

from collections.abc import Mapping
from dataclasses import replace

import pandas as pd

from range_engine.base import RangeState
from range_engine.structural import _find_pivot_highs, _find_pivot_lows
from signal_engine.base import SignalDirection, SignalReason
from signal_engine.engine import RangeSignalEngine


def swing_failures(
    df: pd.DataFrame, *, pivot_window: int = 2, lookback: int = 100, recent: int = 30
) -> list[dict[str, object]]:
    """A strict sweep and close back through a previously confirmed swing.

    Each event uses only the prefix preceding its candle. The event candle
    cannot confirm the pivot it sweeps. No future candle can alter an event.
    """
    events: list[dict[str, object]] = []
    for i in range(max(2 * pivot_window + 1, len(df) - recent), len(df)):
        prior = df.iloc[max(0, i - lookback) : i]
        candle = df.iloc[i]
        for side, column, finder in (
            ("bearish", "high", _find_pivot_highs),
            ("bullish", "low", _find_pivot_lows),
        ):
            values = prior[column].to_numpy(dtype=float)
            pivots = finder(values, pivot_window)
            if not pivots:
                continue
            pivot = pivots[-1]
            level = float(values[pivot])
            # A previously breached swing is spent, not fresh liquidity.
            after = prior.iloc[pivot + 1:]
            if (side == "bearish" and (after.high > level).any()) or (
                side == "bullish" and (after.low < level).any()
            ):
                continue
            swept = (
                (candle.high > level and candle.close < level)
                if side == "bearish"
                else (candle.low < level and candle.close > level)
            )
            if swept:
                events.append(
                    {
                        "direction": side,
                        "level": level,
                        "timestamp": int(candle.timestamp),
                        "swing_timestamp": int(prior.iloc[pivots[-1]].timestamp),
                    }
                )
    return events


def touch_signal(
    candle: Mapping[str, float], state: RangeState, config: Mapping[str, object] | None = None
):
    """Touch setup using a range fixed before this candle opened.

    If both edges are touched, bar data cannot identify the first entry; skip.
    A gap opening outside the range is not a fresh inside-to-edge touch.
    """
    engine = RangeSignalEngine(config)
    fallback = engine.evaluate(float(candle["close"]), state)
    if not state.is_tradable:
        return fallback
    low, high = state.range_low, state.range_high
    lower = candle["low"] <= low <= candle["high"]
    upper = candle["low"] <= high <= candle["high"]
    if lower == upper or not low <= candle["open"] <= high:
        return replace(
            fallback,
            direction=SignalDirection.NONE,
            reason=SignalReason.PRICE_MID_RANGE,
            confidence=0.0,
            metadata={
                **fallback.metadata,
                "entry_mode": "touch",
                "touch_status": "ambiguous" if lower and upper else "waiting",
            },
        )
    signal = engine.evaluate(low if lower else high, state)
    return replace(
        signal, metadata={**signal.metadata, "entry_mode": "touch", "touch_status": "touched"}
    )
