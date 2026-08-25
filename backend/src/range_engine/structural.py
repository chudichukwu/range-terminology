"""Structural range detection from swing highs/lows (fractal pivots).

This is the default detector of the range engine.
"""

from collections.abc import Mapping

import numpy as np
import pandas as pd

from range_engine.base import (
    RangeDetector,
    RangeState,
    RangeStatus,
    get_float,
    get_int,
    validate_ohlcv,
)

_TRENDING_CONFIDENCE = 0.1
_NO_STRUCTURE_CONFIDENCE = 0.1
_CONTAINMENT_WINDOW = 20


def _find_pivot_highs(highs: np.ndarray, window: int) -> list[int]:
    """Return indices of swing-high pivots in ``highs``, one per plateau.

    A pivot requires the center high to be the local maximum over ``window``
    bars on both sides. Ties are tolerated against the outer neighborhood but
    a pivot must strictly exceed the immediately preceding bar, so a flat
    plateau yields exactly one pivot (its first bar) and constant data yields
    none.
    """
    pivots: list[int] = []
    for i in range(window, len(highs) - window):
        neighborhood_max = max(
            highs[i - window : i].max(), highs[i + 1 : i + window + 1].max()
        )
        if highs[i] >= neighborhood_max and highs[i] > highs[i - 1]:
            pivots.append(i)
    return pivots


def _find_pivot_lows(lows: np.ndarray, window: int) -> list[int]:
    """Return indices of swing-low pivots in ``lows``, one per plateau.

    Mirrors :func:`_find_pivot_highs`: the center low must be the local
    minimum over ``window`` bars on each side and strictly undercut the
    preceding bar.
    """
    pivots: list[int] = []
    for i in range(window, len(lows) - window):
        neighborhood_min = min(
            lows[i - window : i].min(), lows[i + 1 : i + window + 1].min()
        )
        if lows[i] <= neighborhood_min and lows[i] < lows[i - 1]:
            pivots.append(i)
    return pivots


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
    mode: str, reason: str, confidence: float, extra: dict[str, object]
) -> RangeState:
    """Build a DEGENERATE state with no tradable bounds."""
    return RangeState(
        range_high=float("nan"),
        range_low=float("nan"),
        mode=mode,
        confidence=confidence,
        metadata={"reason": reason, **extra},
        status=RangeStatus.DEGENERATE,
    )


class StructuralRangeDetector(RangeDetector):
    """Detects a range from recent swing highs and swing lows.

    A swing high is a bar whose high is the strict local maximum over
    ``pivot_window`` bars on each side; swing lows are mirrored. The candidate
    range spans the highest pivot high to the lowest pivot low within the
    ``lookback`` window.

    Guard rails:

    - If net price movement dominates the total path travelled (ratio above
      ``max_drift_ratio``), the market is treated as trending, not ranging:
      the result is DEGENERATE with reason ``"trending"``.
    - If no pivot structure exists at all (e.g. perfectly flat or monotonic
      data), the result is DEGENERATE with reason ``"no_swing_structure"``.
      Rolling min/max are reported only as ``metadata["reference_bounds"]``
      and never as a tradable range.

    Confidence is a heuristic combining how much recent price action stays
    inside the detected bounds with how many alternating touches support them;
    it is NOT a probability.
    """

    def detect(self, df: pd.DataFrame, config: Mapping[str, object] | None = None) -> RangeState:
        """Detect a structurally supported range.

        Args:
            df: OHLCV candle frame.
            config: Supports ``lookback`` (default 100), ``pivot_window``
                (default 2, minimum 1), ``max_drift_ratio`` (default 0.5).

        Returns:
            VALID state bounded by extreme pivots, DEGENERATE when trending or
            structureless, INSUFFICIENT_DATA when fewer than
            ``2 * pivot_window + 1`` rows are available.

        Raises:
            ValueError: On invalid config values or malformed input frames.
        """
        cfg = dict(config or {})
        lookback = get_int(cfg, "lookback", 100, minimum=1)
        pivot_window = get_int(cfg, "pivot_window", 2, minimum=1)
        max_drift_ratio = get_float(cfg, "max_drift_ratio", 0.5, minimum=0.0)
        mode = "structural"
        data = validate_ohlcv(df)
        required_rows = 2 * pivot_window + 1
        if len(data) < required_rows:
            return _insufficient_state(mode, required_rows, len(data))

        window = data.tail(lookback).reset_index(drop=True)
        highs = window["high"].to_numpy(dtype=float)
        lows = window["low"].to_numpy(dtype=float)
        closes = window["close"].to_numpy(dtype=float)

        drift_ratio = self._drift_ratio(closes)
        shared_extra: dict[str, object] = {
            "lookback": int(len(window)),
            "pivot_window": pivot_window,
            "drift_ratio": drift_ratio,
        }
        if drift_ratio > max_drift_ratio:
            shared_extra["reference_bounds"] = (float(lows.min()), float(highs.max()))
            return _degenerate_state(mode, "trending", _TRENDING_CONFIDENCE, shared_extra)

        pivot_highs = _find_pivot_highs(highs, pivot_window)
        pivot_lows = _find_pivot_lows(lows, pivot_window)
        shared_extra["pivot_high_count"] = len(pivot_highs)
        shared_extra["pivot_low_count"] = len(pivot_lows)
        if not pivot_highs or not pivot_lows:
            shared_extra["pivots_found"] = len(pivot_highs) + len(pivot_lows)
            shared_extra["reference_bounds"] = (float(lows.min()), float(highs.max()))
            return _degenerate_state(
                mode, "no_swing_structure", _NO_STRUCTURE_CONFIDENCE, shared_extra
            )

        range_high = float(max(highs[i] for i in pivot_highs))
        range_low = float(min(lows[i] for i in pivot_lows))
        containment = self._containment_share(closes, range_low, range_high)
        touch_scale = min(len(pivot_highs), len(pivot_lows)) / 3.0
        touch_scale = min(touch_scale, 1.0)
        confidence = round(min(1.0, containment**1.5 * (0.5 + 0.5 * touch_scale)), 4)
        metadata: dict[str, object] = {
            **shared_extra,
            "containment_share": containment,
            "confidence_basis": "containment_x_touches",
            "recent_pivot_highs": [float(highs[i]) for i in pivot_highs[-5:]],
            "recent_pivot_lows": [float(lows[i]) for i in pivot_lows[-5:]],
        }
        return RangeState(range_high, range_low, mode, confidence, metadata, RangeStatus.VALID)

    @staticmethod
    def _drift_ratio(closes: np.ndarray) -> float:
        """Ratio of net movement to total path length (1.0 = pure trend)."""
        steps = np.abs(np.diff(closes))
        path_length = float(steps.sum())
        if path_length <= 0.0:
            return 0.0
        return abs(float(closes[-1] - closes[0])) / path_length

    @staticmethod
    def _containment_share(closes: np.ndarray, range_low: float, range_high: float) -> float:
        """Share of the most recent closes lying inside the detected bounds."""
        recent = closes[-_CONTAINMENT_WINDOW :]
        inside = (recent >= range_low) & (recent <= range_high)
        return float(inside.mean())
