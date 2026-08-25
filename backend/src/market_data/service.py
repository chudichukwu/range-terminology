"""MarketDataService: retrieval, normalization, validation, quality reporting.

Coordinates provider access behind :class:`market_data.base.MarketDataPort`,
turns raw normalized rows into validated :class:`MarketCandle` sequences, and
attaches explicit :class:`DataQualityReport` diagnostics. Trading strategy
logic deliberately does NOT live here.

Closed vs current: a candle is CLOSED when its open time plus the timeframe
duration is at or before the service clock (UTC). Recent retrievals may
include the still-forming candle (flagged ``is_closed=False`` and reported as
an issue) so no data is silently dropped; analysis safety is a property
callers read explicitly via :attr:`CandleDataset.is_analysis_safe`.

Caching: an optional bounded TTL+LRU cache of immutable results. Disabled by
default; semantics are service-level only — domain models stay cache-agnostic.
"""

import math
import time
from collections import OrderedDict
from collections.abc import Callable

from exchange.models import Candle, Ticker
from market_data.adapters.ccxt.adapter import ExchangeMarketDataProvider
from market_data.base import MarketDataPort
from market_data.errors import MarketDataError, MarketDataErrorCode
from market_data.models import (
    CandleDataset,
    DataQualityReport,
    HistoricalRequest,
    MarketCandle,
    QualityIssue,
    Timeframe,
)
from market_data.validation import validate_sequence

_MAX_PAGE_LIMIT = 1000
_MAX_PAGES = 50


def _default_clock_ms() -> int:
    return time.time_ns() // 1_000_000


class _TtlCache:
    """Tiny deterministic TTL+LRU cache for immutable result objects."""

    def __init__(self, maxsize: int, ttl_ms: int, clock_ms: Callable[[], int]) -> None:
        self._maxsize = maxsize
        self._ttl_ms = ttl_ms
        self._clock_ms = clock_ms
        self._entries: OrderedDict[object, tuple[int, object]] = OrderedDict()

    def get(self, key: object) -> object | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        stored_at, value = entry
        now = self._clock_ms()
        if now - stored_at >= self._ttl_ms:
            del self._entries[key]
            return None
        self._entries.move_to_end(key)
        return value

    def put(self, key: object, value: object) -> None:
        self._entries[key] = (self._clock_ms(), value)
        self._entries.move_to_end(key)
        while len(self._entries) > self._maxsize:
            self._entries.popitem(last=False)

    def __len__(self) -> int:
        return len(self._entries)


class MarketDataService:
    """Provider-independent market data facade for engines and apps."""

    def __init__(
        self,
        port: MarketDataPort,
        *,
        clock_ms: Callable[[], int] | None = None,
        cache_ttl_ms: int = 0,
        cache_maxsize: int = 128,
    ) -> None:
        """
        Args:
            port: Any market data provider.
            clock_ms: UTC ms clock; injectable for determinism.
            cache_ttl_ms: Cache lifetime in ms; ``0`` disables caching.
            cache_maxsize: LRU bound when caching is enabled.
        """
        self._port = port
        self._clock_ms = clock_ms if clock_ms is not None else _default_clock_ms
        self._cache: _TtlCache | None = (
            _TtlCache(cache_maxsize, cache_ttl_ms, self._clock_ms)
            if cache_ttl_ms > 0
            else None
        )

    # ----- capabilities -----

    def supported_timeframes(self) -> frozenset[Timeframe]:
        """Timeframes advertised by the active provider (may be empty)."""
        return self._port.supported_timeframes()

    # ----- ticker -----

    def get_ticker(self, symbol: str) -> Ticker:
        """Validated latest quote for ``symbol``."""
        _require_symbol(symbol)
        try:
            return self._port.get_ticker(symbol)
        except MarketDataError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalized below by design
            raise self._wrap_provider_failure("get_ticker", type(exc).__name__) from exc

    # ----- recent candles -----

    def get_recent_candles(
        self,
        symbol: str,
        timeframe: Timeframe | str,
        limit: int = 200,
        *,
        include_current: bool = True,
    ) -> CandleDataset:
        """Most recent candles for ``symbol`` at canonical ``timeframe``.

        Args:
            symbol: Instrument to fetch.
            timeframe: Canonical timeframe (enum or parseable string).
            limit: Max candles requested from the provider.
            include_current: When True (default), a still-forming last candle
                may be included but is flagged and quality-reported; when
                False it is excluded up front. Either way nothing is silent.
        """
        tf = Timeframe.parse(timeframe)
        _require_symbol(symbol)
        _require_limit(limit)
        self._check_timeframe_advertised(tf)
        cache_key = ("recent", symbol, tf.value, limit, include_current)
        cached = self._cache_get(cache_key)
        if isinstance(cached, CandleDataset):
            return cached
        rows = self._fetch_rows(symbol, tf, limit=limit, since_ms=None)
        now_ms = self._clock_ms()
        dataset = self._build_dataset(
            symbol, tf, rows, now_ms=now_ms, window_start_ms=None, window_end_ms=None
        )
        if not include_current and dataset.candles:
            dataset = CandleDataset(
                symbol=symbol,
                timeframe=tf,
                candles=tuple(c for c in dataset.candles if c.is_closed),
                quality=dataset.quality,
                retrieved_at_ms=dataset.retrieved_at_ms,
            )
        self._cache_put(cache_key, dataset)
        return dataset

    # ----- historical candles -----

    def get_historical(self, request: HistoricalRequest) -> CandleDataset:
        """Windowed historical OHLCV with explicit gap/quality diagnostics.

        Pages forward through the provider from ``start_ms`` until the window
        end, the caller's limit, or provider exhaustion. Gaps are never
        filled and never dropped: they appear in the report.
        """
        request = _coerce_request(request)
        self._check_timeframe_advertised(request.resolved_timeframe)
        cache_key = (
            "history",
            request.symbol,
            request.resolved_timeframe.value,
            request.start_ms,
            request.end_ms,
            request.limit,
        )
        cached = self._cache_get(cache_key)
        if isinstance(cached, CandleDataset):
            return cached
        duration = request.resolved_timeframe.duration_ms
        collected: list[Candle] = []
        seen_timestamps: set[int] = set()
        duplicates = 0
        cursor: int = request.start_ms if request.start_ms is not None else 0
        remaining = request.limit
        pages = 0
        while remaining > 0 and pages < _MAX_PAGES:
            page_limit = min(_MAX_PAGE_LIMIT, remaining)
            page = self._fetch_rows(
                request.symbol, request.resolved_timeframe, limit=page_limit, since_ms=cursor
            )
            pages += 1
            if not page:
                break
            for row in page:
                if row.timestamp < cursor:
                    continue
                if request.end_ms is not None and row.timestamp >= request.end_ms:
                    remaining = 0
                    break
                if row.timestamp in seen_timestamps:
                    duplicates += 1
                    continue
                seen_timestamps.add(row.timestamp)
                collected.append(row)
                remaining -= 1
            oldest = page[-1].timestamp
            next_cursor = oldest + duration
            if next_cursor <= cursor:
                break  # provider made no forward progress; never loop forever
            cursor = next_cursor
            if request.end_ms is not None and cursor >= request.end_ms:
                break
        now_ms = self._clock_ms()
        dataset = self._build_dataset(
            request.symbol,
            request.resolved_timeframe,
            tuple(collected),
            now_ms=now_ms,
            window_start_ms=request.start_ms,
            window_end_ms=request.end_ms,
            duplicate_count=duplicates,
        )
        self._cache_put(cache_key, dataset)
        return dataset

    # ----- internals -----

    def _check_timeframe_advertised(self, timeframe: Timeframe) -> None:
        if isinstance(self._port, ExchangeMarketDataProvider):
            self._port.require_timeframe(timeframe)

    def _fetch_rows(
        self, symbol: str, timeframe: Timeframe, *, limit: int, since_ms: int | None
    ) -> tuple[Candle, ...]:
        try:
            return self._port.fetch_candles(symbol, timeframe, limit=limit, since_ms=since_ms)
        except MarketDataError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalized below by design
            raise self._wrap_provider_failure("fetch_candles", type(exc).__name__) from exc

    def _build_dataset(
        self,
        symbol: str,
        timeframe: Timeframe,
        rows: tuple[Candle, ...],
        *,
        now_ms: int,
        window_start_ms: int | None,
        window_end_ms: int | None,
        duplicate_count: int = 0,
    ) -> CandleDataset:
        """Normalize rows to MarketCandles and attach the quality verdict."""
        candles: list[MarketCandle] = []
        for index, row in enumerate(rows):
            try:
                candles.append(self._to_market_candle(symbol, timeframe, row, now_ms))
            except ValueError as exc:
                raise MarketDataError(
                    MarketDataErrorCode.NORMALIZATION_FAILED,
                    f"Malformed candle at index {index}: {exc}",
                    metadata={"symbol": symbol, "timeframe": timeframe.value},
                ) from exc
        validation = validate_sequence(symbol, timeframe, tuple(candles))
        issues = list(validation.report.issues)
        if duplicate_count > 0:
            issues.append(
                QualityIssue(
                    kind="duplicate_timestamp",
                    detail=f"{duplicate_count} duplicate row(s) collapsed during pagination",
                )
            )
        if window_start_ms is not None and window_end_ms is not None:
            grid = timeframe.duration_ms
            expected_first = math.ceil(window_start_ms / grid) * grid
            if not candles:
                issues.append(
                    QualityIssue(
                        kind="missing_interval",
                        detail=(
                            f"provider returned no data for window "
                            f"[{expected_first}, {window_end_ms})"
                        ),
                        gap_start_ms=expected_first,
                        gap_end_ms=window_end_ms,
                    )
                )
            else:
                if candles[0].timestamp > expected_first:
                    issues.append(
                        QualityIssue(
                            kind="missing_interval",
                            detail=(
                                f"provider returned no data between {expected_first} and "
                                f"{candles[0].timestamp}"
                            ),
                            gap_start_ms=expected_first,
                            gap_end_ms=candles[0].timestamp,
                        )
                    )
                trailing_start = candles[-1].timestamp + timeframe.duration_ms
                if trailing_start < window_end_ms:
                    issues.append(
                        QualityIssue(
                            kind="missing_interval",
                            detail=(
                                f"provider data ends before window end: nothing between "
                                f"{trailing_start} and {window_end_ms}"
                            ),
                            gap_start_ms=trailing_start,
                            gap_end_ms=window_end_ms,
                        )
                    )
        report = DataQualityReport(issues=tuple(issues))
        return CandleDataset(
            symbol=symbol,
            timeframe=timeframe,
            candles=tuple(validation.sorted_candles),
            quality=report,
            retrieved_at_ms=now_ms,
        )

    @staticmethod
    def _to_market_candle(
        symbol: str, timeframe: Timeframe, row: Candle, now_ms: int
    ) -> MarketCandle:
        """Project one normalized exchange row onto the market data model.

        Closedness is computed against UTC now: a candle is closed once its
        open time + duration <= now. Provider facts are otherwise passed
        through untouched; missing volume stays None.
        """
        return MarketCandle(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=row.timestamp,
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
            volume=row.volume,
            is_closed=row.timestamp + timeframe.duration_ms <= now_ms,
        )

    @staticmethod
    def _wrap_provider_failure(operation: str, venue_error_type: str) -> MarketDataError:
        """Normalize unexpected provider failures without leaking payloads."""
        return MarketDataError(
            MarketDataErrorCode.PROVIDER_ERROR,
            "provider request failed",
            metadata={"operation": operation, "venue_error_type": venue_error_type},
        )

    def _cache_get(self, key: object) -> object | None:
        return self._cache.get(key) if self._cache is not None else None

    def _cache_put(self, key: object, value: object) -> None:
        if self._cache is not None:
            self._cache.put(key, value)


def _coerce_request(request: HistoricalRequest) -> HistoricalRequest:
    if not isinstance(request, HistoricalRequest):
        raise ValueError("request must be a HistoricalRequest")
    return request


def _require_symbol(symbol: str) -> None:
    if not isinstance(symbol, str) or not symbol.strip():
        raise MarketDataError(
            MarketDataErrorCode.SYMBOL_INVALID,
            "symbol must be a non-empty string",
        )


def _require_limit(limit: int) -> None:
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0 or limit > 10_000:
        raise MarketDataError(
            MarketDataErrorCode.REQUEST_INVALID,
            f"limit must be a positive integer <= 10000, got {limit!r}",
        )
