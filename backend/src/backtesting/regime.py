"""Deterministic market-regime classification for research context.

This is NOT an AI/ML regime detector. It applies one explainable,
causally-safe rule over closes that were already closed at the decision
point: Kaufman's Efficiency Ratio (net move divided by total path).

    ER = (close[-1] - close[0]) / sum(|close[i] - close[i-1]|)

ER in [-1, 1]; |ER| >= threshold means directional movement dominates noise:

- TRENDING_UP     : ER >= +threshold
- TRENDING_DOWN   : ER <= -threshold
- TRANSITIONAL    : overall window flat but the most recent third already
                    trends (a trend starting or dying inside a flat window)
- RANGING         : neither window nor recent third trends
- INSUFFICIENT_DATA: fewer than ``lookback`` closed candles

Only information available at classification time is used — the window never
extends past the current candle.
"""

import math
from collections.abc import Sequence
from enum import Enum


class MarketRegime(Enum):
    """Minimal, explainable market-regime labels for research breakdowns."""

    RANGING = "ranging"
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    TRANSITIONAL = "transitional"
    INSUFFICIENT_DATA = "insufficient_data"


DEFAULT_REGIME_LOOKBACK = 20
DEFAULT_REGIME_THRESHOLD = 0.3


def efficiency_ratio(closes: Sequence[float]) -> float:
    """Kaufman Efficiency Ratio of ``closes``; 0.0 when path is zero."""
    if len(closes) < 2:
        return 0.0
    net = closes[-1] - closes[0]
    path = sum(abs(closes[i] - closes[i - 1]) for i in range(1, len(closes)))
    if path <= 0.0:
        return 0.0
    return net / path


def classify_regime(
    closes: Sequence[float],
    *,
    lookback: int = DEFAULT_REGIME_LOOKBACK,
    threshold: float = DEFAULT_REGIME_THRESHOLD,
) -> MarketRegime:
    """Classify the regime from closes available RIGHT NOW.

    Args:
        closes: Closed-candle closing prices in chronological order. Only the
            most recent ``lookback`` values are read; callers must never pass
            data extending beyond the current replay point.
        lookback: Window size; minimum 4 so a "recent third" exists.
        threshold: |ER| at or above which the window counts as trending;
            must lie within (0, 1].

    Returns:
        One deterministic :class:`MarketRegime` label.

    Raises:
        ValueError: On invalid lookback/threshold configuration.
    """
    if lookback < 4:
        raise ValueError(f"regime lookback must be >= 4, got {lookback}")
    if not 0.0 < threshold <= 1.0:
        raise ValueError(f"regime threshold must be within (0, 1], got {threshold}")
    window = list(closes[-lookback:])
    if len(window) < lookback or any(not math.isfinite(c) for c in window):
        return MarketRegime.INSUFFICIENT_DATA

    er = efficiency_ratio(window)
    if er >= threshold:
        return MarketRegime.TRENDING_UP
    if er <= -threshold:
        return MarketRegime.TRENDING_DOWN

    recent_size = max(3, lookback // 3)
    recent_er = efficiency_ratio(window[-recent_size:])
    if abs(recent_er) >= threshold:
        return MarketRegime.TRANSITIONAL
    return MarketRegime.RANGING


__all__ = [
    "DEFAULT_REGIME_LOOKBACK",
    "DEFAULT_REGIME_THRESHOLD",
    "MarketRegime",
    "classify_regime",
    "efficiency_ratio",
]
