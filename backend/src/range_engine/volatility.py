"""Volatility-based range detection using Bollinger Bands or an ATR channel."""

import math
from collections.abc import Mapping

import numpy as np
import pandas as pd

from range_engine.base import (
    RangeDetector,
    RangeState,
    RangeStatus,
    get_choice,
    get_float,
    get_int,
    validate_ohlcv,
)


def _insufficient_state(mode: str, required_rows: int, provided_rows: int) -> RangeState:
    """Build the explicit INSUFFICIENT_DATA state."""
    return RangeState(
        range_high=float("nan"),
        range_low=float("nan"),
        mode=mode,
        confidence=0.0,
        metadata={
            "reason": "insufficient_data",
            "required_rows": required_rows,
            "provided_rows": provided_rows,
        },
        status=RangeStatus.INSUFFICIENT_DATA,
    )


def _degenerate_state(
    mode: str, center: float, reason: str, extra: dict[str, object]
) -> RangeState:
    """Build a DEGENERATE state for flat/zero-volatility inputs."""
    return RangeState(
        range_high=center,
        range_low=center,
        mode=mode,
        confidence=0.0,
        metadata={"reason": reason, "reference_bounds": (center, center), **extra},
        status=RangeStatus.DEGENERATE,
    )


_EXPANSION_CAP = 0.35
_EXPANSION_TOLERANCE = 1.10
_CONTAINMENT_WINDOW = 20
_TREND_TOLERANCE = 0.5
_TREND_CAP = 0.25


def _trend_ratio(closes: np.ndarray, span: int) -> float:
    """Net movement divided by total path length over the recent ``span`` bars."""
    segment = closes[-span:]
    steps = np.abs(np.diff(segment))
    path_length = float(steps.sum())
    if path_length <= 0.0:
        return 0.0
    return abs(float(segment[-1] - segment[0])) / path_length


def _regime_confidence(
    closes: np.ndarray, final_low: float, final_high: float, widths: pd.Series, span: int
) -> float:
    """Heuristic score combining containment, stability and trend detection.

    Containment dominates: when recent closes keep escaping the final band the
    data does not behave like a range. Independent of that, a dominant net
    movement over the recent ``span`` bars (high trend ratio, e.g. steady
    uptrends whose band widths stay deceptively stable) caps the score hard.
    """
    window = closes[-_CONTAINMENT_WINDOW:]
    containment = float(((window >= final_low) & (window <= final_high)).mean())
    if len(widths) < 4 or float(widths.mean()) <= 0.0:
        stability = 0.05
    else:
        split = len(widths) // 2
        earlier_mean = float(widths.iloc[:split].mean())
        recent = widths.iloc[split:]
        recent_mean = float(recent.mean())
        if earlier_mean <= 0.0 or recent_mean <= 0.0:
            stability = 0.05
        else:
            cv = float(recent.std(ddof=1)) / recent_mean
            stability = min(0.95, max(0.05, 1.0 - cv))
            if recent_mean > earlier_mean * _EXPANSION_TOLERANCE:
                stability = min(stability, _EXPANSION_CAP)
    score = containment**1.5 * (0.5 + 0.5 * stability)
    if _trend_ratio(closes, span) > _TREND_TOLERANCE:
        score = min(score, _TREND_CAP)
    return float(round(min(0.95, max(0.05, score)), 4))


class VolatilityRangeDetector(RangeDetector):
    """Derives a range from statistical volatility bands around price.

    Two methods are supported via the ``method`` config key:

    - ``bollinger``: SMA(close, period) +/- multiplier * stddev(close, period)
      (sample standard deviation, ddof=1).
    - ``atr``: Wilder-smoothed Average True Range channel centered on the last
      close: close +/- multiplier * ATR(period).

    Confidence is a heuristic — NOT a probability — combining how much recent
    price action stays inside the final band (containment) with how stable the
    band width has been; steadily expanding widths (trending conditions) are
    additionally capped.
    """

    def detect(self, df: pd.DataFrame, config: Mapping[str, object] | None = None) -> RangeState:
        """Detect a volatility-derived range.

        Args:
            df: OHLCV candle frame.
            config: Supports ``method`` (``"bollinger" | "atr"``, default
                ``"bollinger"``), ``period`` (default 20, minimum 2),
                ``multiplier`` (default 2.0).

        Returns:
            VALID state with band bounds, DEGENERATE on zero volatility, or
            INSUFFICIENT_DATA when fewer than ``period`` rows are available.

        Raises:
            ValueError: On invalid config values or malformed input frames.
        """
        cfg = dict(config or {})
        method = get_choice(cfg, "method", ("bollinger", "atr"))
        period = get_int(cfg, "period", 20, minimum=2)
        multiplier = get_float(cfg, "multiplier", 2.0, minimum=0.0)
        mode = f"volatility_{method}"
        data = validate_ohlcv(df)
        if len(data) < period:
            return _insufficient_state(mode, period, len(data))
        if method == "bollinger":
            return self._detect_bollinger(data, mode, period, multiplier)
        return self._detect_atr(data, mode, period, multiplier)

    def _detect_bollinger(
        self, data: pd.DataFrame, mode: str, period: int, multiplier: float
    ) -> RangeState:
        """Bollinger Band path: SMA +/- multiplier * sample stddev of closes."""
        closes = data["close"]
        window = closes.tail(period)
        center = float(window.mean())
        std = float(window.std(ddof=1))
        extra: dict[str, object] = {
            "method": "bollinger",
            "period": period,
            "multiplier": multiplier,
            "center": center,
            "std_dev": std,
        }
        if not math.isfinite(std) or std <= 0.0:
            return _degenerate_state(mode, center, "zero_volatility", extra)
        range_high = center + multiplier * std
        range_low = center - multiplier * std
        widths = (closes.rolling(period).std(ddof=1) * multiplier).dropna()
        confidence = _regime_confidence(
            closes.to_numpy(dtype=float), range_low, range_high, widths, span=2 * period
        )
        extra.update(
            {
                "band_width": range_high - range_low,
                "confidence_basis": "containment_x_stability",
            }
        )
        return RangeState(range_high, range_low, mode, confidence, extra, RangeStatus.VALID)

    def _detect_atr(
        self, data: pd.DataFrame, mode: str, period: int, multiplier: float
    ) -> RangeState:
        """ATR channel path: last close +/- multiplier * Wilder-smoothed ATR."""
        highs = data["high"].to_numpy(dtype=float)
        lows = data["low"].to_numpy(dtype=float)
        closes = data["close"].to_numpy(dtype=float)
        previous_close = np.concatenate(([closes[0]], closes[:-1]))
        true_range = np.maximum(
            highs - lows,
            np.maximum(np.abs(highs - previous_close), np.abs(lows - previous_close)),
        )
        atr_series = (
            pd.Series(true_range, index=data.index, dtype=float)
            .ewm(alpha=1.0 / period, adjust=False)
            .mean()
        )
        atr = float(atr_series.iloc[-1])
        center = float(closes[-1])
        extra: dict[str, object] = {
            "method": "atr",
            "period": period,
            "multiplier": multiplier,
            "center": center,
            "atr": atr,
        }
        if not math.isfinite(atr) or atr <= 0.0:
            return _degenerate_state(mode, center, "zero_volatility", extra)
        range_high = center + multiplier * atr
        range_low = center - multiplier * atr
        confidence = _regime_confidence(
            closes, range_low, range_high, atr_series.dropna(), span=2 * period
        )
        extra.update(
            {
                "band_width": range_high - range_low,
                "confidence_basis": "containment_x_stability",
            }
        )
        return RangeState(range_high, range_low, mode, confidence, extra, RangeStatus.VALID)
