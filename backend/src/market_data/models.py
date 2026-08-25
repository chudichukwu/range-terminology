"""Normalized market data value types.

All models are frozen dataclasses in the style of :mod:`exchange.models` and
:mod:`execution_engine.models`: validation runs eagerly in ``__post_init__``,
unknown provider facts stay ``None``, nothing is invented. Timestamps are UTC
milliseconds everywhere; local-time conversion is a presentation concern that
belongs to a later layer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

import pandas as pd

from exchange.models import Ticker  # noqa: F401  (re-exported for consumers)

_REQUIRED: object = object()


def _set(instance: object, name: str, value: object) -> None:
    """Assign to a frozen dataclass field from within __post_init__."""
    object.__setattr__(instance, name, value)


def _finite_positive(value: object, name: str) -> float:
    """Require a finite, strictly positive number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a real number, got {type(value).__name__}")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive, got {result}")
    return result


def _finite_non_negative(value: object, name: str) -> float | None:
    """Accept None or a finite non-negative number; reject everything else."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a real number, got {type(value).__name__}")
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and non-negative, got {result}")
    return result


class Timeframe(Enum):
    """Canonical timeframes; consumers never see provider-specific strings.

    ``duration_ms`` is the deterministic candle grid used for gap detection.
    Providers may support any subset — availability is capability information
    reported by :class:`~market_data.base.MarketDataPort`, never assumed.
    """

    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"

    @property
    def duration_ms(self) -> int:
        """Candle period length in milliseconds."""
        return _DURATIONS[self]

    @classmethod
    def parse(cls, value: object) -> Timeframe:
        """Normalize a raw timeframe string onto the canonical enum.

        Case-insensitive for unambiguous suffixes (``"1H"`` -> ``H1``);
        anything outside the supported set raises ``ValueError`` rather than
        being silently mapped to something else.

        Raises:
            ValueError: When ``value`` is not a supported timeframe string
                or is already a :class:`Timeframe` of unsupported kind.
        """
        if isinstance(value, cls):
            return value
        if isinstance(value, bool) or not isinstance(value, str) or not value:
            raise ValueError(
                f"timeframe must be one of {_canonical_list()}, got {value!r}"
            )
        candidate = value.strip().lower()
        for member in cls:
            if member.value == candidate:
                return member
        raise ValueError(
            f"Unsupported timeframe {value!r}; supported: {_canonical_list()}"
        )


_DURATIONS: dict[Timeframe, int] = {
    Timeframe.M1: 60_000,
    Timeframe.M5: 300_000,
    Timeframe.M15: 900_000,
    Timeframe.M30: 1_800_000,
    Timeframe.H1: 3_600_000,
    Timeframe.H4: 14_400_000,
    Timeframe.D1: 86_400_000,
}


def _canonical_list() -> str:
    return ", ".join(member.value for member in Timeframe)


@dataclass(frozen=True)
class MarketCandle:
    """One normalized OHLCV bar bound to a symbol/timeframe pair.

    Attributes:
        symbol: Instrument identifier, e.g. ``"BTC/USDT"``.
        timeframe: Canonical :class:`Timeframe` this candle belongs to.
        timestamp: Candle OPEN time as UTC milliseconds since epoch.
        open/high/low/close: Finite positive prices with coherent OHLC
            relationships (``low <= min(o,c,h)``, ``high >= max(o,c,l)``).
        volume: Traded volume; never negative. ``None`` when the provider
            does not report it — never fabricated.
        is_closed: False while the candle is still forming. Analysis code
            must exclude unclosed candles from historical truth.
    """

    symbol: str
    timeframe: Timeframe
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
    is_closed: bool = True

    def __post_init__(self) -> None:
        if not self.symbol or not isinstance(self.symbol, str):
            raise ValueError("MarketCandle.symbol must be a non-empty string")
        _set(self, "timeframe", Timeframe.parse(self.timeframe))
        if isinstance(self.timestamp, bool) or not isinstance(self.timestamp, int):
            raise ValueError("MarketCandle.timestamp must be an integer ms epoch value")
        if self.timestamp <= 0:
            raise ValueError(f"MarketCandle.timestamp must be positive, got {self.timestamp}")
        _set(self, "open", _finite_positive(self.open, "MarketCandle.open"))
        _set(self, "high", _finite_positive(self.high, "MarketCandle.high"))
        _set(self, "low", _finite_positive(self.low, "MarketCandle.low"))
        _set(self, "close", _finite_positive(self.close, "MarketCandle.close"))
        _set(self, "volume", _finite_non_negative(self.volume, "MarketCandle.volume"))
        body_high = max(self.open, self.close)
        body_low = min(self.open, self.close)
        if self.high < body_high or self.low > body_low:
            raise ValueError(
                f"MarketCandle OHLC incoherent: high {self.high}, low {self.low}, "
                f"open {self.open}, close {self.close}"
            )

    @property
    def close_time_ms(self) -> int:
        """UTC ms of the candle's closing boundary (exclusive)."""
        return self.timestamp + self.timeframe.duration_ms


@dataclass(frozen=True)
class CandleSeries:
    """Immutable sequence of candles for exactly one symbol+timeframe.

    Construction does NOT require sortedness — data-quality problems are
    reported by :mod:`market_data.validation`, never hidden. All candles must
    share symbol and timeframe.
    """

    symbol: str
    timeframe: Timeframe
    candles: tuple[MarketCandle, ...] = ()

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("CandleSeries.symbol must be non-empty")
        _set(self, "timeframe", Timeframe.parse(self.timeframe))
        for candle in self.candles:
            if candle.symbol != self.symbol or candle.timeframe is not self.timeframe:
                raise ValueError(
                    f"CandleSeries member mismatch: expected {self.symbol}/"
                    f"{self.timeframe.value}, got {candle.symbol}/{candle.timeframe.value}"
                )

    @property
    def timestamps(self) -> tuple[int, ...]:
        """Open timestamps in stored order."""
        return tuple(candle.timestamp for candle in self.candles)

    @property
    def first_timestamp_ms(self) -> int | None:
        return self.candles[0].timestamp if self.candles else None

    @property
    def last_timestamp_ms(self) -> int | None:
        return self.candles[-1].timestamp if self.candles else None

    @property
    def contains_unclosed(self) -> bool:
        """True when any candle is still forming."""
        return any(not candle.is_closed for candle in self.candles)

    def closed_candles(self) -> tuple[MarketCandle, ...]:
        """Only CLOSED candles — the subset safe for strategy analysis."""
        return tuple(candle for candle in self.candles if candle.is_closed)

    def closed_series(self) -> CandleSeries:
        """A new series containing only closed candles."""
        return CandleSeries(
            symbol=self.symbol,
            timeframe=self.timeframe,
            candles=self.closed_candles(),
        )


@dataclass(frozen=True)
class HistoricalRequest:
    """Validated request for historical OHLCV data.

    Attributes:
        symbol: Instrument to fetch; must be non-empty.
        timeframe: Canonical timeframe for the grid.
        start_ms: Inclusive window start (UTC ms); ``None`` means unbounded
            toward the past, bounded only by ``limit``.
        end_ms: Exclusive window end (UTC ms); ``None`` means "up to now".
        limit: Maximum candles the caller accepts across all pages.
    """

    symbol: str
    timeframe: Timeframe | str
    start_ms: int | None = None
    end_ms: int | None = None
    limit: int = 1000

    def __post_init__(self) -> None:
        if not self.symbol or not isinstance(self.symbol, str):
            raise ValueError("HistoricalRequest.symbol must be a non-empty string")
        _set(self, "timeframe", Timeframe.parse(self.timeframe))
        for name in ("start_ms", "end_ms"):
            value = getattr(self, name)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"HistoricalRequest.{name} must be a positive integer ms value")
        if self.start_ms is not None and self.end_ms is not None:
            if self.start_ms >= self.end_ms:
                raise ValueError(
                    f"HistoricalRequest.start_ms ({self.start_ms}) must be before "
                    f"end_ms ({self.end_ms})"
                )
        if isinstance(self.limit, bool) or not isinstance(self.limit, int) or self.limit <= 0:
            raise ValueError(
                f"HistoricalRequest.limit must be a positive integer, got {self.limit!r}"
            )

    @property
    def resolved_timeframe(self) -> Timeframe:
        """The canonical timeframe enum."""
        return Timeframe.parse(self.timeframe)


@dataclass(frozen=True)
class QualityIssue:
    """One explicit data-quality problem in a candle dataset."""

    kind: str
    detail: str
    index: int | None = None
    gap_start_ms: int | None = None
    gap_end_ms: int | None = None

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("QualityIssue.kind must be non-empty")
        if not self.detail:
            raise ValueError("QualityIssue.detail must be non-empty")


@dataclass(frozen=True)
class DataQualityReport:
    """Explicit quality verdict for one candle dataset.

    Consumers decide policy: ``is_analysis_safe`` answers whether strategy
    code may treat the data as complete historical truth.
    """

    issues: tuple[QualityIssue, ...] = ()

    @property
    def is_clean(self) -> bool:
        return not self.issues

    @property
    def has_gaps(self) -> bool:
        return any(issue.gap_start_ms is not None for issue in self.issues)

    @property
    def gap_ranges(self) -> tuple[tuple[int, int], ...]:
        """Missing intervals as ``(gap_start_ms, gap_end_ms)`` pairs."""
        return tuple(
            (issue.gap_start_ms, issue.gap_end_ms)
            for issue in self.issues
            if issue.gap_start_ms is not None and issue.gap_end_ms is not None
        )

    @property
    def issue_kinds(self) -> frozenset[str]:
        return frozenset(issue.kind for issue in self.issues)

    def with_issues(self, extra: tuple[QualityIssue, ...]) -> DataQualityReport:
        return DataQualityReport(issues=self.issues + extra)


EMPTY_QUALITY_REPORT = DataQualityReport()


@dataclass(frozen=True)
class CandleDataset:
    """Result of a market data retrieval: series + explicit quality verdict.

    This is the shape consumed by the Range/Signal engines and future
    backtesting; it is provider-independent by construction.
    """

    symbol: str
    timeframe: Timeframe
    candles: tuple[MarketCandle, ...]
    quality: DataQualityReport = EMPTY_QUALITY_REPORT
    retrieved_at_ms: int = 0

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("CandleDataset.symbol must be non-empty")
        _set(self, "timeframe", Timeframe.parse(self.timeframe))

    @property
    def is_analysis_safe(self) -> bool:
        """True when clean AND every candle is closed — safe historical truth."""
        return self.quality.is_clean and not any(not c.is_closed for c in self.candles)

    @property
    def closed_candles(self) -> tuple[MarketCandle, ...]:
        return tuple(candle for candle in self.candles if candle.is_closed)

    def to_series(self) -> CandleSeries:
        return CandleSeries(symbol=self.symbol, timeframe=self.timeframe, candles=self.candles)

    def to_dataframe(self) -> pd.DataFrame:
        """Project onto the OHLCV frame layout the Range Engine consumes.

        Columns are exactly ``range_engine.base.REQUIRED_OHLCV_COLUMNS``;
        timestamps stay integer UTC milliseconds.
        """
        rows = [
            {
                "timestamp": candle.timestamp,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": 0.0 if candle.volume is None else candle.volume,
            }
            for candle in self.candles
        ]
        return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])


__all__ = [
    "CandleDataset",
    "CandleSeries",
    "DataQualityReport",
    "EMPTY_QUALITY_REPORT",
    "HistoricalRequest",
    "MarketCandle",
    "QualityIssue",
    "Ticker",
    "Timeframe",
]
