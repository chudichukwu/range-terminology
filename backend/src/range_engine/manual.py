"""Manual range definition passed straight through from configuration."""

from collections.abc import Mapping

import pandas as pd

from range_engine.base import (
    RangeDetector,
    RangeState,
    RangeStatus,
    get_float,
)


class ManualRangeDetector(RangeDetector):
    """Returns operator-supplied bounds without any calculation.

    Useful when a trader pins a range by hand on the chart. The OHLCV frame is
    still validated structurally but its contents do not influence the result.
    """

    def detect(self, df: pd.DataFrame, config: Mapping[str, object] | None = None) -> RangeState:
        """Echo the configured bounds as a :class:`RangeState`.

        Args:
            df: OHLCV candle frame (validated but unused for calculation).
            config: Requires ``range_high`` and ``range_low``; optional
                ``confidence`` override (default 1.0).

        Returns:
            VALID state when width is positive, DEGENERATE when the operator
            supplied a zero-width range.

        Raises:
            ValueError: On missing required keys, non-numeric values, or
                ``range_low > range_high``.
        """
        cfg = dict(config or {})
        range_high = get_float(cfg, "range_high")
        range_low = get_float(cfg, "range_low")
        if range_low > range_high:
            raise ValueError(f"range_low ({range_low}) must not exceed range_high ({range_high})")
        confidence = get_float(cfg, "confidence", 1.0, minimum=0.0)
        status = RangeStatus.VALID if range_high > range_low else RangeStatus.DEGENERATE
        metadata: dict[str, object] = {"source": "manual"}
        if status is RangeStatus.DEGENERATE:
            metadata["reason"] = "zero_width"
            confidence = 0.0
        return RangeState(
            range_high=range_high,
            range_low=range_low,
            mode="manual",
            confidence=confidence,
            metadata=metadata,
            status=status,
        )
