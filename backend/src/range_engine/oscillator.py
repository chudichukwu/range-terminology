"""Oscillator-confirmed range detection.

This detector NEVER defines range boundaries itself. It wraps a base
:class:`~range_engine.base.RangeDetector` (composition, not inheritance),
delegates boundary detection to it, and layers an RSI or Stochastic
confirmation reading on top via metadata.
"""

import math
from collections.abc import Mapping

import numpy as np
import pandas as pd

from range_engine.base import (
    RangeDetector,
    RangeState,
    get_choice,
    get_float,
    get_int,
    validate_ohlcv,
)
from range_engine.structural import StructuralRangeDetector


def _rsi_series(closes: pd.Series, period: int) -> pd.Series:
    """Compute Wilder-smoothed RSI; undefined regions resolve to neutral 50."""
    delta = closes.diff()
    gains = delta.clip(lower=0.0)
    losses = -delta.clip(upper=0.0)
    avg_gain = gains.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = losses.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100.0 - 100.0 / (1.0 + rs)
    return rsi.fillna(50.0)


def _stochastic_k_series(
    highs: pd.Series, lows: pd.Series, closes: pd.Series, period: int
) -> pd.Series:
    """Compute raw Stochastic %K; flat windows resolve to neutral 50."""
    lowest_low = lows.rolling(period).min()
    highest_high = highs.rolling(period).max()
    denominator = (highest_high - lowest_low).replace(0.0, np.nan)
    percent_k = 100.0 * (closes - lowest_low) / denominator
    return percent_k.fillna(50.0)


class OscillatorConfirmedRangeDetector(RangeDetector):
    """Decorates another detector's result with oscillator confirmation.

    The wrapped base detector owns the boundaries untouched. This wrapper only
    computes the latest RSI or Stochastic %K value and records whether it sits
    in overbought/oversold territory while price trades at the corresponding
    range edge. Results are exposed as:

    - ``metadata["confirmation"]``: bool
    - ``metadata["oscillator_value"]``: float (nan when not computable)

    plus the full oscillator context (thresholds, position within range).
    """

    _RESERVED_KEYS = frozenset(
        {"oscillator", "osc_period", "oversold", "overbought", "edge_proximity", "base"}
    )

    def __init__(
        self,
        base: RangeDetector | None = None,
        base_config: Mapping[str, object] | None = None,
    ) -> None:
        """Create the wrapper around an optional base detector.

        Args:
            base: Detector providing the range boundaries; defaults to
                :class:`StructuralRangeDetector`.
            base_config: Default config forwarded to the base detector on every
                call (typically a factory-flattened nested ``params`` mapping);
                keys other than these are overridden by each call's config.
        """
        self._base: RangeDetector = base if base is not None else StructuralRangeDetector()
        self._base_config: dict[str, object] = dict(base_config or {})

    @property
    def base_detector(self) -> RangeDetector:
        """The wrapped detector responsible for the boundaries."""
        return self._base

    def detect(self, df: pd.DataFrame, config: Mapping[str, object] | None = None) -> RangeState:
        """Run the base detector and attach oscillator confirmation metadata.

        Args:
            df: OHLCV candle frame.
            config: Forwarded to the base detector; this wrapper additionally
                reads ``oscillator`` (``"rsi" | "stoch"``, default ``"rsi"``),
                ``osc_period`` (default 14, minimum 2), ``oversold`` (default
                30), ``overbought`` (default 70) and ``edge_proximity``
                (fraction of the width counted as "at the edge", default 0.25).

        Returns:
            A new :class:`RangeState` with the base state's bounds, mode,
            confidence and status preserved, extended by confirmation keys in
            ``metadata``.

        Raises:
            ValueError: On invalid config values or malformed input frames.
        """
        cfg = dict(config or {})
        oscillator_name = get_choice(cfg, "oscillator", ("rsi", "stoch"))
        period = get_int(cfg, "osc_period", 14, minimum=2)
        oversold = get_float(cfg, "oversold", 30.0)
        overbought = get_float(cfg, "overbought", 70.0)
        edge_proximity = get_float(cfg, "edge_proximity", 0.25, minimum=0.0)

        forwarded: dict[str, object] = dict(self._base_config)
        forwarded.update(
            {key: value for key, value in cfg.items() if key not in self._RESERVED_KEYS}
        )
        state = self._base.detect(df, forwarded)
        data = validate_ohlcv(df)
        oscillator_value, value_note = self._latest_oscillator_value(data, oscillator_name, period)
        position = self._position_in_range(state.range_low, state.range_high, data)
        confirmed = self._is_confirmed(
            position, oscillator_value, oversold, overbought, edge_proximity
        )
        metadata: dict[str, object] = {
            **state.metadata,
            "confirmation": confirmed,
            "oscillator": oscillator_name,
            "oscillator_value": (
                round(oscillator_value, 4) if not math.isnan(oscillator_value) else oscillator_value
            ),
            "osc_period": period,
            "oversold_threshold": oversold,
            "overbought_threshold": overbought,
            "edge_proximity": edge_proximity,
            "confirmed_by": f"{state.mode}+{oscillator_name}",
        }
        if value_note is not None:
            metadata["oscillator_note"] = value_note
        if position is not None:
            metadata["position_in_range"] = round(position, 4)
        return RangeState(
            range_high=state.range_high,
            range_low=state.range_low,
            mode=state.mode,
            confidence=state.confidence,
            metadata=metadata,
            status=state.status,
        )

    @staticmethod
    def _latest_oscillator_value(
        data: pd.DataFrame, oscillator_name: str, period: int
    ) -> tuple[float, str | None]:
        """Latest oscillator reading plus an optional explanatory note."""
        if len(data) < period + 1:
            return float("nan"), "insufficient_rows_for_oscillator"
        if oscillator_name == "rsi":
            series = _rsi_series(data["close"], period)
        else:
            series = _stochastic_k_series(data["high"], data["low"], data["close"], period)
        return float(series.iloc[-1]), None

    @staticmethod
    def _position_in_range(range_low: float, range_high: float, data: pd.DataFrame) -> float | None:
        """Normalized position of the last close inside [low, high]; None if undefined."""
        width = range_high - range_low
        if width <= 0.0 or math.isnan(range_low) or math.isnan(range_high):
            return None
        last_close = float(data["close"].iloc[-1])
        return min(1.0, max(0.0, (last_close - range_low) / width))

    @staticmethod
    def _is_confirmed(
        position: float | None,
        oscillator_value: float,
        oversold: float,
        overbought: float,
        edge_proximity: float,
    ) -> bool:
        """True when price is at a range edge AND the oscillator agrees there."""
        if position is None or math.isnan(oscillator_value):
            return False
        at_lower_edge = position <= edge_proximity
        at_upper_edge = position >= 1.0 - edge_proximity
        return (at_lower_edge and oscillator_value <= oversold) or (
            at_upper_edge and oscillator_value >= overbought
        )
