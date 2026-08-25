"""Core primitives for the range-detection domain.

This module defines the public contract every detector implements
(``RangeDetector``), the result value type (``RangeState`` with an explicit
:class:`RangeStatus`), shared OHLCV input validation, and typed config-access
helpers used by the concrete detectors.

The domain is pure: no network, no filesystem, no exchange SDKs. Pandas is the
input boundary format; all math below it operates on numpy values extracted
from validated frames.
"""

import math
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Final

import pandas as pd

REQUIRED_OHLCV_COLUMNS: Final[tuple[str, ...]] = (
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
)

_NUMERIC_OHLCV_COLUMNS: Final[tuple[str, ...]] = ("open", "high", "low", "close", "volume")

_REQUIRED: Final[object] = object()


class RangeStatus(Enum):
    """Quality status of a detected range.

    - ``VALID``: bounds are meaningful and may be traded against.
    - ``DEGENERATE``: detection ran but produced no tradable structure
      (flat data, trending market, zero volatility). Bounds must not be
      treated as a tradable range; ``metadata["reason"]`` explains why.
    - ``INSUFFICIENT_DATA``: too few rows to run the algorithm at all.
    """

    VALID = "valid"
    DEGENERATE = "degenerate"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class RangeState:
    """Immutable result of a range detection run.

    Attributes:
        range_high: Upper bound of the detected range. ``nan`` when there are
            no meaningful bounds (see ``status``).
        range_low: Lower bound of the detected range. ``nan`` when there are
            no meaningful bounds.
        mode: Detector mode identifier, e.g. ``"structural"`` or
            ``"volatility_bollinger"``.
        confidence: Heuristic score in ``[0, 1]`` expressing how strongly the
            data supports a ranging regime. This is NOT a probability.
        metadata: Mode-specific extras (reasons, pivot counts, thresholds).
        status: Explicit quality status; consumers must check this before
            using the bounds.
    """

    range_high: float
    range_low: float
    mode: str
    confidence: float
    metadata: dict[str, object] = field(default_factory=dict)
    status: RangeStatus = RangeStatus.VALID

    def __post_init__(self) -> None:
        if self.range_low > self.range_high:
            raise ValueError(
                f"range_low ({self.range_low}) must not exceed range_high ({self.range_high})"
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be within [0, 1], got {self.confidence}")

    @property
    def range_width(self) -> float:
        """Distance between the upper and lower bounds."""
        return self.range_high - self.range_low

    @property
    def is_tradable(self) -> bool:
        """True only for positive-width ranges with explicit VALID status."""
        return (
            self.status is RangeStatus.VALID
            and self.range_width > 0.0
            and not math.isnan(self.range_high)
            and not math.isnan(self.range_low)
        )


def validate_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Validate OHLCV input and return a normalized copy.

    Checks that the frame has all required columns and numeric price/volume
    dtypes, coerces the numeric columns to ``float``, orders columns canonically
    and sorts rows by timestamp when needed.

    Structural violations raise ``ValueError``; data-quantity problems (too few
    rows) are NOT raised here — detectors report those via
    :class:`RangeStatus.INSUFFICIENT_DATA`.

    Args:
        df: Candidate OHLCV frame.

    Returns:
        Normalized DataFrame containing exactly ``REQUIRED_OHLCV_COLUMNS``.

    Raises:
        ValueError: If input is not a DataFrame, misses required columns, or
            carries non-numeric price/volume columns.
    """
    if not isinstance(df, pd.DataFrame):
        raise ValueError(f"OHLCV input must be a pandas DataFrame, got {type(df).__name__}")
    missing = [column for column in REQUIRED_OHLCV_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"OHLCV frame is missing required columns: {missing}")
    non_numeric = [
        column for column in _NUMERIC_OHLCV_COLUMNS if not pd.api.types.is_numeric_dtype(df[column])
    ]
    if non_numeric:
        raise ValueError(f"OHLCV columns must be numeric, offending columns: {non_numeric}")
    out = df.loc[:, list(REQUIRED_OHLCV_COLUMNS)].copy()
    numeric = list(_NUMERIC_OHLCV_COLUMNS)
    out[numeric] = out[numeric].astype(float)
    if not out["timestamp"].is_monotonic_increasing:
        out = out.sort_values("timestamp", kind="stable").reset_index(drop=True)
    return out.reset_index(drop=True)


def get_float(
    config: Mapping[str, object],
    key: str,
    default: object = _REQUIRED,
    *,
    minimum: float | None = None,
) -> float:
    """Read a numeric config entry as ``float``.

    Args:
        config: Config mapping.
        key: Key to read.
        default: Fallback value; omit to make the key mandatory.
        minimum: Optional inclusive lower bound.

    Returns:
        The config value as ``float``.

    Raises:
        ValueError: If the key is missing without default, holds a non-numeric
            value, or violates ``minimum``.
    """
    value = config.get(key)
    if value is None:
        if default is _REQUIRED:
            raise ValueError(f"Missing required config key {key!r} (expected a number)")
        value = default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(
            f"Config key {key!r} must be a real number, got {type(value).__name__}"
        )
    result = float(value)
    if minimum is not None and result < minimum:
        raise ValueError(f"Config key {key!r} must be >= {minimum}, got {result}")
    return result


def get_int(
    config: Mapping[str, object],
    key: str,
    default: object = _REQUIRED,
    *,
    minimum: int | None = None,
) -> int:
    """Read a config entry as ``int`` (integral floats accepted).

    Args:
        config: Config mapping.
        key: Key to read.
        default: Fallback value; omit to make the key mandatory.
        minimum: Optional inclusive lower bound.

    Returns:
        The config value as ``int``.

    Raises:
        ValueError: If the key is missing without default, holds a
            non-integral value, or violates ``minimum``.
    """
    value = config.get(key)
    if value is None:
        if default is _REQUIRED:
            raise ValueError(f"Missing required config key {key!r} (expected an integer)")
        value = default
    if isinstance(value, bool):
        raise ValueError(f"Config key {key!r} must be an integer, got bool")
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError(f"Config key {key!r} must be an integer, got {value}")
        value = int(value)
    if not isinstance(value, int):
        raise ValueError(
            f"Config key {key!r} must be an integer, got {type(value).__name__}"
        )
    result = int(value)
    if minimum is not None and result < minimum:
        raise ValueError(f"Config key {key!r} must be >= {minimum}, got {result}")
    return result


def get_choice(
    config: Mapping[str, object],
    key: str,
    choices: Sequence[str],
    default: str | None = None,
) -> str:
    """Read a string config entry restricted to a fixed set of options.

    Args:
        config: Config mapping.
        key: Key to read.
        choices: Allowed values; first element is used when neither the key
            nor ``default`` is present.
        default: Optional fallback distinct from ``choices[0]``.

    Returns:
        The selected option.

    Raises:
        ValueError: If the value is missing without any default or is not one
            of ``choices``.
    """
    value = config.get(key)
    if value is None:
        value = default if default is not None else choices[0]
    if not isinstance(value, str) or value not in choices:
        allowed = ", ".join(repr(choice) for choice in choices)
        raise ValueError(f"Config key {key!r} must be one of: {allowed}; got {value!r}")
    return value


class RangeDetector(ABC):
    """Abstract base class for range-detection algorithms.

    Implementations receive a validated OHLCV DataFrame plus a per-call config
    mapping and return a single :class:`RangeState`. They must be side-effect
    free and deterministic for identical inputs.
    """

    @abstractmethod
    def detect(self, df: pd.DataFrame, config: Mapping[str, object] | None = None) -> RangeState:
        """Detect the current range from OHLCV candles.

        Args:
            df: OHLCV candle frame (columns per ``REQUIRED_OHLCV_COLUMNS``).
            config: Mode-specific parameters; ``None`` means defaults.

        Returns:
            The detected :class:`RangeState`, never ``None``. Data-quality
            problems surface through ``RangeState.status`` rather than
            exceptions; only structural input violations raise.
        """
