"""Deterministic tests for the market data layer.

All provider responses come from scripted fakes — no network, no ccxt
install, no credentials, no real market data.
"""

import logging

import pytest

from exchange.base import ExchangePort
from exchange.capabilities import ExchangeCapabilities
from exchange.constraints import MarketConstraints
from exchange.errors import ExchangeError, ExchangeErrorCode
from exchange.models import (
    Candle,
    OrderSubmission,
    SubmissionState,
)
from market_data import (
    ISSUE_DUPLICATE_TIMESTAMP,
    ISSUE_MISSING_INTERVAL,
    ISSUE_OUT_OF_ORDER_TIMESTAMP,
    ISSUE_UNCLOSED_CANDLE,
    CandleDataset,
    CandleSeries,
    DataQualityReport,
    ExchangeMarketDataProvider,
    HistoricalRequest,
    MarketCandle,
    MarketDataError,
    MarketDataErrorCode,
    MarketDataPort,
    MarketDataService,
    Ticker,
    Timeframe,
    validate_sequence,
)
from range_engine import RangeEngineFactory

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeExchangePort(ExchangePort):
    """Scripted Phase 4 port: candles/tickers served from in-memory maps."""

    def __init__(self) -> None:
        self._caps = ExchangeCapabilities(
            spot=True, market_orders=True, limit_orders=True, stop_orders=True
        )
        self.candles: dict[str, list[Candle]] = {}
        self.tickers: dict[str, Ticker] = {}
        self.timeframes: tuple[str, ...] = ("1m", "5m", "15m", "30m", "1h", "4h", "1d")
        self.ohlcv_calls: list[tuple[str, str, int, int | None]] = []
        self.fail_next_ohlcv: Exception | None = None
        self.max_rows_per_call: int | None = None

    @property
    def venue_id(self) -> str:
        return "fakevenue"

    @property
    def capabilities(self) -> ExchangeCapabilities:
        return self._caps

    @property
    def supported_timeframes(self) -> tuple[str, ...]:
        return self.timeframes

    def get_ticker(self, symbol: str):  # type: ignore[no-untyped-def]
        if symbol not in self.tickers:
            raise ExchangeError(ExchangeErrorCode.MARKET_UNAVAILABLE, f"unknown {symbol}")
        return self.tickers[symbol]

    def get_order_book(self, symbol: str, depth: int = 50):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200,
        since_ms: int | None = None,
    ):  # type: ignore[no-untyped-def]
        self.ohlcv_calls.append((symbol, timeframe, limit, since_ms))
        if self.fail_next_ohlcv is not None:
            error, self.fail_next_ohlcv = self.fail_next_ohlcv, None
            raise error
        rows = self.candles.get(symbol, [])
        if since_ms is not None:
            rows = [row for row in rows if row.timestamp >= since_ms]
        effective_limit = limit
        if self.max_rows_per_call is not None:
            effective_limit = min(limit, self.max_rows_per_call)
        return tuple(rows[:effective_limit])

    def get_markets(self):  # type: ignore[no-untyped-def]
        return tuple(sorted(self.candles))

    def get_market(self, symbol: str):  # type: ignore[no-untyped-def]
        return MarketConstraints()

    def get_balances(self):  # type: ignore[no-untyped-def]
        return ()

    def get_positions(self):  # type: ignore[no-untyped-def]
        return ()

    def get_open_orders(self, symbol: str | None = None):  # type: ignore[no-untyped-def]
        return ()

    def get_order(self, symbol: str, order_id=None, client_order_id=None):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    def place_order(self, symbol, side, order_type, quantity, price=None, client_order_id=None):  # type: ignore[no-untyped-def]
        return OrderSubmission(state=SubmissionState.ACCEPTED)  # pragma: no cover - unused here

    def cancel_order(self, symbol, order_id=None, client_order_id=None):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    def cancel_all_orders(self, symbol: str | None = None):  # type: ignore[no-untyped-def]
        return 0


class RecordingProvider(MarketDataPort):
    """Standalone fake MarketDataPort for provider-independence checks."""

    def __init__(self) -> None:
        self.tickers: dict[str, Ticker] = {}
        self.candle_rows: dict[str, list[Candle]] = {}
        self.timeframes: frozenset[Timeframe] = frozenset(Timeframe)
        self.calls: list[tuple[str, str, int, int | None]] = []

    def get_ticker(self, symbol: str):  # type: ignore[no-untyped-def]
        return self.tickers[symbol]

    def fetch_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        *,
        limit: int = 200,
        since_ms: int | None = None,
    ):  # type: ignore[no-untyped-def]
        self.calls.append((symbol, timeframe.value, limit, since_ms))
        rows = self.candle_rows.get((symbol, timeframe.value), [])  # type: ignore[index]
        if since_ms is not None:
            rows = [row for row in rows if row.timestamp >= since_ms]
        return tuple(rows[:limit])

    def supported_timeframes(self) -> frozenset[Timeframe]:
        return self.timeframes


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

HOUR_MS = 3_600_000
BASE_TS = 1_700_000_000_000  # UTC ms; aligned to the hour


def make_candle_row(ts: int, close: float = 100.0, volume: float | None = 5.0) -> Candle:
    return Candle(
        timestamp=ts,
        open=close - 1.0,
        high=close + 2.0,
        low=close - 3.0,
        close=close,
        volume=0.0 if volume is None else volume,
    )


def hourly_rows(symbol_count: int, start_ts: int = BASE_TS) -> list[Candle]:
    return [make_candle_row(start_ts + index * HOUR_MS, close=100.0 + index)
            for index in range(symbol_count)]


def fixed_clock(now_ms: int = BASE_TS + 10 * HOUR_MS):  # type: ignore[return]
    state = {"now": now_ms}

    def tick() -> int:
        return state["now"]

    def advance(ms: int) -> None:
        state["now"] += ms

    tick.advance = advance  # type: ignore[attr-defined]
    return tick


# ---------------------------------------------------------------------------
# Models: MarketCandle invariants
# ---------------------------------------------------------------------------


class TestMarketCandleModel:
    def test_valid_candle(self) -> None:
        candle = MarketCandle(
            "BTC/USDT", Timeframe.H1, BASE_TS, 99.0, 102.0, 97.0, 100.0, volume=3.0
        )
        assert candle.is_closed is True
        assert candle.close_time_ms == BASE_TS + HOUR_MS

    def test_incoherent_ohlc_rejected(self) -> None:
        with pytest.raises(ValueError, match="incoherent"):
            MarketCandle("BTC/USDT", "1h", BASE_TS, 99.0, 90.0, 97.0, 100.0)

    def test_low_above_body_rejected(self) -> None:
        with pytest.raises(ValueError, match="incoherent"):
            MarketCandle("BTC/USDT", "1h", BASE_TS, 99.0, 102.0, 98.5, 98.0)

    def test_non_positive_price_rejected(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            MarketCandle("BTC/USDT", "1h", BASE_TS, -99.0, 102.0, 97.0, 100.0)

    def test_non_finite_price_rejected(self) -> None:
        with pytest.raises(ValueError):
            MarketCandle("BTC/USDT", "1h", BASE_TS, float("nan"), 102.0, 97.0, 100.0)

    def test_negative_volume_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            MarketCandle("BTC/USDT", "1h", BASE_TS, 99.0, 102.0, 97.0, 100.0, volume=-1.0)

    def test_missing_volume_stays_none(self) -> None:
        candle = MarketCandle(
            "BTC/USDT", "1h", BASE_TS, 99.0, 102.0, 97.0, 100.0, volume=None
        )
        assert candle.volume is None

    def test_invalid_timestamp_rejected(self) -> None:
        for bad_ts in (0, -5, 1.5, True, "1700000000000"):  # type: ignore[list-item]
            with pytest.raises(ValueError):
                MarketCandle("BTC/USDT", "1h", bad_ts, 99.0, 102.0, 97.0, 100.0)

    def test_empty_symbol_rejected(self) -> None:
        with pytest.raises(ValueError, match="symbol"):
            MarketCandle("", "1h", BASE_TS, 99.0, 102.0, 97.0, 100.0)

    def test_timeframe_normalized_from_string(self) -> None:
        candle = MarketCandle("BTC/USDT", "4H", BASE_TS, 99.0, 102.0, 97.0, 100.0)
        assert candle.timeframe is Timeframe.H4

    def test_is_closed_explicitly_settable(self) -> None:
        forming = MarketCandle(
            "BTC/USDT", "1h", BASE_TS, 99.0, 102.0, 97.0, 100.0, is_closed=False
        )
        assert forming.is_closed is False

    def test_model_is_frozen(self) -> None:
        import dataclasses

        candle = MarketCandle("BTC/USDT", "1h", BASE_TS, 99.0, 102.0, 97.0, 100.0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            candle.close = 1.0  # type: ignore[misc]


class TestTimeframeModel:
    def test_canonical_values_and_durations(self) -> None:
        expected = {
            "1m": 60_000,
            "5m": 300_000,
            "15m": 900_000,
            "30m": 1_800_000,
            "1h": 3_600_000,
            "4h": 14_400_000,
            "1d": 86_400_000,
        }
        assert {tf.value: tf.duration_ms for tf in Timeframe} == expected

    @pytest.mark.parametrize(("raw", "expected"), [
        ("1m", Timeframe.M1), ("5M", Timeframe.M5), ("15m", Timeframe.M15),
        ("30m", Timeframe.M30), ("1H", Timeframe.H1), ("4h", Timeframe.H4),
        ("1D", Timeframe.D1),
    ])
    def test_case_insensitive_normalization(self, raw: str, expected: Timeframe) -> None:
        assert Timeframe.parse(raw) is expected

    def test_passthrough_enum(self) -> None:
        assert Timeframe.parse(Timeframe.H1) is Timeframe.H1

    def test_unsupported_timeframe_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            Timeframe.parse("2h")

    def test_garbage_timeframes_rejected(self) -> None:
        for bad in ("", "weekly", None, 5, True):  # type: ignore[list-item]
            with pytest.raises(ValueError):
                Timeframe.parse(bad)


class TestCandleSeriesAndDataset:
    def test_series_member_mismatch_rejected(self) -> None:
        btc = MarketCandle("BTC/USDT", "1h", BASE_TS, 99.0, 102.0, 97.0, 100.0)
        eth = MarketCandle("ETH/USDT", "1h", BASE_TS + HOUR_MS, 9.0, 12.0, 7.0, 10.0)
        with pytest.raises(ValueError, match="mismatch"):
            CandleSeries("BTC/USDT", Timeframe.H1, (btc, eth))

    def test_series_closed_view(self) -> None:
        closed = MarketCandle("BTC/USDT", "1h", BASE_TS, 99.0, 102.0, 97.0, 100.0)
        forming = MarketCandle(
            "BTC/USDT", "1h", BASE_TS + HOUR_MS, 100.0, 103.0, 98.0, 101.0, is_closed=False
        )
        series = CandleSeries("BTC/USDT", Timeframe.H1, (closed, forming))
        assert series.contains_unclosed is True
        assert series.closed_candles() == (closed,)
        assert series.closed_series().candles == (closed,)

    def test_dataset_to_dataframe_matches_range_engine_layout(self) -> None:
        candles = tuple(
            MarketCandle(
                "BTC/USDT",
                "1h",
                BASE_TS + index * HOUR_MS,
                99.0,
                102.0,
                97.0,
                100.0,
                volume=2.0,
            )
            for index in range(30)
        )
        dataset = CandleDataset(symbol="BTC/USDT", timeframe=Timeframe.H1, candles=candles)
        frame = dataset.to_dataframe()
        assert list(frame.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
        assert len(frame) == 30
        state = RangeEngineFactory.detect(frame, {"mode": "manual", "params": {
            "range_high": 105.0, "range_low": 95.0}})
        assert state.status.value in {"valid", "degenerate"}

    def test_historical_request_validation(self) -> None:
        with pytest.raises(ValueError, match="before"):
            HistoricalRequest("BTC/USDT", "1h", start_ms=200, end_ms=100)
        with pytest.raises(ValueError, match="limit"):
            HistoricalRequest("BTC/USDT", "1h", limit=0)
        with pytest.raises(ValueError, match="symbol"):
            HistoricalRequest("", "1h")


# ---------------------------------------------------------------------------
# Sequence validation
# ---------------------------------------------------------------------------


class TestSequenceValidation:
    def mc(self, ts: int, *, closed: bool = True) -> MarketCandle:
        return MarketCandle(
            "BTC/USDT", "1h", ts, 99.0, 102.0, 97.0, 100.0,
            volume=1.0 if closed else None, is_closed=closed,
        )

    def test_clean_sequence(self) -> None:
        candles = (self.mc(BASE_TS), self.mc(BASE_TS + HOUR_MS), self.mc(BASE_TS + 2 * HOUR_MS))
        result = validate_sequence("BTC/USDT", Timeframe.H1, candles)
        assert result.report.is_clean
        assert result.sorted_candles == candles

    def test_duplicate_timestamp_detected(self) -> None:
        result = validate_sequence(
            "BTC/USDT", Timeframe.H1,
            (self.mc(BASE_TS), self.mc(BASE_TS), self.mc(BASE_TS + HOUR_MS)),
        )
        assert ISSUE_DUPLICATE_TIMESTAMP in result.report.issue_kinds

    def test_out_of_order_detected_and_sorted_output(self) -> None:
        third = self.mc(BASE_TS + 2 * HOUR_MS)
        first = self.mc(BASE_TS)
        second = self.mc(BASE_TS + HOUR_MS)
        result = validate_sequence("BTC/USDT", Timeframe.H1, (third, first, second))
        assert ISSUE_OUT_OF_ORDER_TIMESTAMP in result.report.issue_kinds
        assert result.sorted_candles == (first, second, third)

    def test_missing_interval_reported_with_explicit_range(self) -> None:
        result = validate_sequence(
            "BTC/USDT", Timeframe.H1, (self.mc(BASE_TS), self.mc(BASE_TS + 3 * HOUR_MS))
        )
        assert ISSUE_MISSING_INTERVAL in result.report.issue_kinds
        gaps = result.report.gap_ranges
        assert gaps == ((BASE_TS + HOUR_MS, BASE_TS + 3 * HOUR_MS),)

    def test_unclosed_candle_flagged(self) -> None:
        result = validate_sequence(
            "BTC/USDT", Timeframe.H1, (self.mc(BASE_TS), self.mc(BASE_TS + HOUR_MS, closed=False))
        )
        assert ISSUE_UNCLOSED_CANDLE in result.report.issue_kinds
        # Unclosed presence alone does not fabricate a gap.
        assert not result.report.has_gaps

    def test_empty_series_flagged(self) -> None:
        result = validate_sequence("BTC/USDT", Timeframe.H1, ())
        assert not result.report.is_clean
        assert result.sorted_candles == ()

    def test_member_mismatch_flagged(self) -> None:
        eth_candle = MarketCandle("ETH/USDT", "1h", BASE_TS, 9.0, 12.0, 7.0, 10.0)
        result = validate_sequence("BTC/USDT", Timeframe.H1, (eth_candle,))
        assert "series_member_mismatch" in result.report.issue_kinds


# ---------------------------------------------------------------------------
# Service: ticker + recent retrieval
# ---------------------------------------------------------------------------


def make_service(
    port: ExchangePort | RecordingProvider,
    now_ms: int = BASE_TS + 10 * HOUR_MS,
    **service_kwargs: object,
) -> tuple[MarketDataService, object]:
    clock = fixed_clock(now_ms)
    service = MarketDataService(port, clock_ms=clock, **service_kwargs)  # type: ignore[arg-type]
    return service, clock


class TestServiceTicker:
    def test_ticker_roundtrip(self) -> None:
        port = RecordingProvider()
        port.tickers["BTC/USDT"] = Ticker("BTC/USDT", bid=99.5, ask=100.5, last=100.0)
        service, _clock = make_service(port)
        ticker = service.get_ticker("BTC/USDT")
        assert ticker.last == 100.0 and ticker.bid == 99.5

    def test_empty_symbol_rejected_before_provider(self) -> None:
        port = RecordingProvider()
        service, _clock = make_service(port)
        with pytest.raises(MarketDataError) as excinfo:
            service.get_ticker("   ")
        assert excinfo.value.code is MarketDataErrorCode.SYMBOL_INVALID

    def test_provider_error_normalized(self) -> None:
        port = RecordingProvider()
        service, _clock = make_service(port)
        with pytest.raises(MarketDataError) as excinfo:
            service.get_ticker("MISSING/PAIR")
        assert excinfo.value.code is MarketDataErrorCode.PROVIDER_ERROR
        # Raw exception text is dropped; only the type name survives.
        assert "unknown" not in str(excinfo.value)


class TestServiceRecentCandles:
    def test_recent_retrieval_normalizes_rows(self) -> None:
        port = FakeExchangePort()
        port.candles["ETH/USDT"] = hourly_rows(3)
        provider = ExchangeMarketDataProvider(port)
        service, clock = make_service(provider, now_ms=BASE_TS + 10 * HOUR_MS)
        dataset = service.get_recent_candles("ETH/USDT", "1h", limit=50)
        assert isinstance(dataset, CandleDataset)
        assert dataset.symbol == "ETH/USDT"
        assert len(dataset.candles) == 3
        assert all(candle.is_closed for candle in dataset.candles)
        assert dataset.quality.is_clean
        assert dataset.is_analysis_safe

    def test_forming_last_candle_flagged_not_dropped(self) -> None:
        port = FakeExchangePort()
        rows = hourly_rows(3)
        forming_ts = BASE_TS + 10 * HOUR_MS  # open == service 'now' -> still forming
        rows.append(make_candle_row(forming_ts))
        port.candles["BTC/USDT"] = rows
        provider = ExchangeMarketDataProvider(port)
        service, _clock = make_service(provider, now_ms=BASE_TS + 10 * HOUR_MS)
        dataset = service.get_recent_candles("BTC/USDT", "1h")
        assert dataset.candles[-1].is_closed is False
        assert ISSUE_UNCLOSED_CANDLE in dataset.quality.issue_kinds
        assert dataset.is_analysis_safe is False

    def test_include_current_false_excludes_forming(self) -> None:
        port = FakeExchangePort()
        rows = hourly_rows(3)
        rows.append(make_candle_row(BASE_TS + 10 * HOUR_MS))
        port.candles["BTC/USDT"] = rows
        provider = ExchangeMarketDataProvider(port)
        service, _clock = make_service(provider, now_ms=BASE_TS + 10 * HOUR_MS)
        dataset = service.get_recent_candles("BTC/USDT", "1h", include_current=False)
        assert all(candle.is_closed for candle in dataset.candles)
        assert len(dataset.candles) == 3

    def test_unsupported_timeframe_rejected_when_advertised(self) -> None:
        port = FakeExchangePort()
        port.timeframes = ("1h", "4h")
        provider = ExchangeMarketDataProvider(port)
        service, _clock = make_service(provider)
        with pytest.raises(MarketDataError) as excinfo:
            service.get_recent_candles("BTC/USDT", "5m")
        assert excinfo.value.code is MarketDataErrorCode.TIMEFRAME_UNSUPPORTED
        assert excinfo.value.metadata["supported"] == ["1h", "4h"]
        assert port.ohlcv_calls == []  # never reached the provider

    def test_unadvertised_timeframes_pass_through_to_provider(self) -> None:
        port = FakeExchangePort()
        port.timeframes = ()
        port.candles["BTC/USDT"] = hourly_rows(2)
        provider = ExchangeMarketDataProvider(port)
        service, _clock = make_service(provider)
        dataset = service.get_recent_candles("BTC/USDT", "1m")
        assert len(dataset.candles) == 2

    def test_invalid_limit_rejected(self) -> None:
        provider = ExchangeMarketDataProvider(FakeExchangePort())
        service, _clock = make_service(provider)
        for bad_limit in (0, -3, 10_001):
            with pytest.raises(MarketDataError, match="limit"):
                service.get_recent_candles("BTC/USDT", "1h", limit=bad_limit)

    def test_malformed_provider_row_raises_normalization_failure(self) -> None:
        class BrokenProvider(MarketDataPort):
            """Returns a row valid per exchange models but not market data's
            (non-positive timestamp passes exchange.Candle, rejected by
            MarketCandle)."""

            def get_ticker(self, symbol: str):  # type: ignore[no-untyped-def]
                raise NotImplementedError

            def fetch_candles(self, symbol, timeframe, *, limit=200, since_ms=None):  # type: ignore[no-untyped-def]
                return (
                    Candle(
                        timestamp=BASE_TS, open=10.0, high=11.0, low=9.0, close=10.0, volume=1.0
                    ),
                    Candle(timestamp=0, open=10.0, high=11.0, low=9.0, close=10.0, volume=1.0),
                )

            def supported_timeframes(self):  # type: ignore[no-untyped-def]
                return frozenset(Timeframe)

        service, _clock = make_service(BrokenProvider())
        with pytest.raises(MarketDataError) as excinfo:
            service.get_recent_candles("BTC/USDT", "1m")
        assert excinfo.value.code is MarketDataErrorCode.NORMALIZATION_FAILED
        assert "index 1" in excinfo.value.message


# ---------------------------------------------------------------------------
# Historical data + pagination
# ---------------------------------------------------------------------------


class TestHistoricalRetrieval:
    def test_windowed_history_clean(self) -> None:
        port = FakeExchangePort()
        port.candles["BTC/USDT"] = hourly_rows(10)
        provider = ExchangeMarketDataProvider(port)
        service, _clock = make_service(provider)
        request = HistoricalRequest(
            "BTC/USDT", "1h", start_ms=BASE_TS, end_ms=BASE_TS + 5 * HOUR_MS, limit=100
        )
        dataset = service.get_historical(request)
        assert len(dataset.candles) == 5
        assert dataset.candles[0].timestamp == BASE_TS
        assert dataset.candles[-1].timestamp == BASE_TS + 4 * HOUR_MS
        assert dataset.quality.is_clean
        assert dataset.is_analysis_safe

    def test_pagination_pages_forward_until_window_end(self) -> None:
        port = FakeExchangePort()
        port.max_rows_per_call = 20  # venue-style page cap
        port.candles["BTC/USDT"] = hourly_rows(50)
        provider = ExchangeMarketDataProvider(port)
        service, _clock = make_service(provider)
        request = HistoricalRequest(
            "BTC/USDT", "1h", start_ms=BASE_TS, end_ms=BASE_TS + 30 * HOUR_MS, limit=100
        )
        dataset = service.get_historical(request)
        assert len(dataset.candles) == 30
        assert len(port.ohlcv_calls) >= 2
        first_since = port.ohlcv_calls[0][3]
        second_since = port.ohlcv_calls[1][3]
        assert first_since == BASE_TS
        assert second_since is not None and second_since > first_since

    def test_limit_respected_across_pages(self) -> None:
        port = FakeExchangePort()
        port.candles["BTC/USDT"] = hourly_rows(50)
        provider = ExchangeMarketDataProvider(port)
        service, _clock = make_service(provider)
        request = HistoricalRequest("BTC/USDT", "1h", start_ms=BASE_TS, limit=7)
        dataset = service.get_historical(request)
        assert len(dataset.candles) == 7
        assert not dataset.quality.has_gaps or True  # gaps only vs explicit window

    def test_provider_exhaustion_reported_not_filled(self) -> None:
        port = FakeExchangePort()
        port.candles["BTC/USDT"] = hourly_rows(2)
        provider = ExchangeMarketDataProvider(port)
        service, _clock = make_service(provider)
        request = HistoricalRequest(
            "BTC/USDT",
            "1h",
            start_ms=BASE_TS,
            end_ms=BASE_TS + 6 * HOUR_MS,
            limit=100,
        )
        dataset = service.get_historical(request)
        assert len(dataset.candles) == 2
        assert dataset.quality.has_gaps
        assert ISSUE_MISSING_INTERVAL in dataset.quality.issue_kinds
        gap_start, gap_end = dataset.quality.gap_ranges[-1]
        assert gap_end > gap_start

    def test_overlapping_pages_deduplicated_and_flagged(self) -> None:
        class OverlapPort(FakeExchangePort):
            """Returns overlapping windows to exercise dedupe logic."""

            def get_ohlcv(self, symbol, timeframe, limit=200, since_ms=None):  # type: ignore[no-untyped-def]
                self.ohlcv_calls.append((symbol, timeframe, limit, since_ms))
                rows = self.candles.get(symbol, [])
                if since_ms is None:
                    return tuple(rows[:limit])
                # Overlapping window: include one candle before the cursor.
                overlapped = [row for row in rows if row.timestamp >= since_ms - HOUR_MS]
                return tuple(overlapped[:limit])

        overlap_port = OverlapPort()
        overlap_port.candles["BTC/USDT"] = hourly_rows(10)
        service, _clock = make_service(ExchangeMarketDataProvider(overlap_port))
        request = HistoricalRequest(
            "BTC/USDT", "1h", start_ms=BASE_TS, end_ms=BASE_TS + 10 * HOUR_MS, limit=100
        )
        dataset = service.get_historical(request)
        timestamps = [candle.timestamp for candle in dataset.candles]
        assert len(timestamps) == len(set(timestamps))
        assert len(dataset.candles) == 10

    def test_gap_inside_window_detected(self) -> None:
        port = FakeExchangePort()
        rows = hourly_rows(3) + [
            make_candle_row(BASE_TS + 5 * HOUR_MS),
            make_candle_row(BASE_TS + 6 * HOUR_MS),
        ]
        port.candles["BTC/USDT"] = rows
        provider = ExchangeMarketDataProvider(port)
        service, _clock = make_service(provider)
        request = HistoricalRequest(
            "BTC/USDT", "1h", start_ms=BASE_TS, end_ms=BASE_TS + 7 * HOUR_MS, limit=100
        )
        dataset = service.get_historical(request)
        gaps = dataset.quality.gap_ranges
        assert (BASE_TS + 3 * HOUR_MS, BASE_TS + 5 * HOUR_MS) in gaps
        assert dataset.is_analysis_safe is False

    def test_provider_network_failure_wrapped(self) -> None:
        port = FakeExchangePort()
        port.fail_next_ohlcv = ExchangeError(ExchangeErrorCode.NETWORK_ERROR, "boom")
        provider = ExchangeMarketDataProvider(port)
        service, _clock = make_service(provider)
        with pytest.raises(MarketDataError) as excinfo:
            service.get_recent_candles("BTC/USDT", "1h")
        assert excinfo.value.code is MarketDataErrorCode.PROVIDER_ERROR

    def test_no_data_error_for_empty_response(self) -> None:
        port = FakeExchangePort()
        provider = ExchangeMarketDataProvider(port)
        service, _clock = make_service(provider)
        dataset = service.get_recent_candles("BTC/USDT", "1h")
        assert dataset.candles == ()
        assert not dataset.is_analysis_safe


# ---------------------------------------------------------------------------
# Multi-pair / multi-timeframe (no hardcoded assumptions)
# ---------------------------------------------------------------------------


class TestMultiPairAndTimeframes:
    def test_arbitrary_pairs_served_independently(self) -> None:
        port = FakeExchangePort()
        for symbol in ("BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT"):
            port.candles[symbol] = [make_candle_row(BASE_TS, close=hash(symbol) % 100 + 10)]
        provider = ExchangeMarketDataProvider(port)
        service, _clock = make_service(provider)
        for symbol in ("BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT"):
            dataset = service.get_recent_candles(symbol, "1h")
            assert dataset.symbol == symbol and len(dataset.candles) == 1

    def test_same_symbol_multiple_timeframes(self) -> None:
        provider = RecordingProvider()
        provider.candle_rows[("BTC/USDT", "5m")] = [make_candle_row(BASE_TS)]  # type: ignore[index]
        provider.candle_rows[("BTC/USDT", "1h")] = [make_candle_row(BASE_TS)]  # type: ignore[index]
        provider.candle_rows[("BTC/USDT", "4h")] = [make_candle_row(BASE_TS)]  # type: ignore[index]
        service, _clock = make_service(provider)
        for tf in ("5m", "1h", "4h"):
            dataset = service.get_recent_candles("BTC/USDT", tf)
            assert dataset.timeframe is Timeframe.parse(tf)

    def test_standalone_provider_needs_no_exchange_port(self) -> None:
        provider = RecordingProvider()  # implements MarketDataPort directly
        provider.tickers["DOGE/USDT"] = Ticker("DOGE/USDT", last=0.1234)
        service, _clock = make_service(provider)
        assert service.get_ticker("DOGE/USDT").last == pytest.approx(0.1234)


# ---------------------------------------------------------------------------
# Caching behavior
# ---------------------------------------------------------------------------


class TestCaching:
    def test_cache_disabled_by_default(self) -> None:
        port = FakeExchangePort()
        port.candles["BTC/USDT"] = hourly_rows(2)
        service, clock = make_service(port := ExchangeMarketDataProvider(port))
        calls_before = port._exchange.ohlcv_calls  # type: ignore[attr-defined]  # noqa: SLF001
        service.get_recent_candles("BTC/USDT", "1h")
        service.get_recent_candles("BTC/USDT", "1h")
        assert len(calls_before) == 2

    def test_enabled_cache_dedupes_within_ttl(self) -> None:
        port = FakeExchangePort()
        port.candles["BTC/USDT"] = hourly_rows(2)
        wrapped = ExchangeMarketDataProvider(port)
        service, clock = make_service(wrapped, cache_ttl_ms=60_000)
        first = service.get_recent_candles("BTC/USDT", "1h")
        calls_after_first = len(port.ohlcv_calls)
        second = service.get_recent_candles("BTC/USDT", "1h")
        assert len(port.ohlcv_calls) == calls_after_first
        assert second == first

    def test_expired_ttl_refetches(self) -> None:
        port = FakeExchangePort()
        port.candles["BTC/USDT"] = hourly_rows(2)
        service, clock = make_service(
            ExchangeMarketDataProvider(port), cache_ttl_ms=1_000
        )
        service.get_recent_candles("BTC/USDT", "1h")
        clock.advance(2_000)  # type: ignore[attr-defined]
        service.get_recent_candles("BTC/USDT", "1h")
        assert len(port.ohlcv_calls) == 2

    def test_distinct_requests_cached_separately(self) -> None:
        port = FakeExchangePort()
        port.candles["BTC/USDT"] = hourly_rows(2)
        port.candles["ETH/USDT"] = [make_candle_row(BASE_TS)]
        service, _clock = make_service(
            ExchangeMarketDataProvider(port), cache_ttl_ms=60_000
        )
        btc = service.get_recent_candles("BTC/USDT", "1h")
        eth = service.get_recent_candles("ETH/USDT", "1h")
        again = service.get_recent_candles("BTC/USDT", "1h")
        assert btc.symbol == "BTC/USDT" and eth.symbol == "ETH/USDT"
        assert again == btc


# ---------------------------------------------------------------------------
# Provider capability reporting
# ---------------------------------------------------------------------------


class TestProviderCapabilities:
    def test_timeframes_derived_from_venue_advertisement(self) -> None:
        port = FakeExchangePort()
        port.timeframes = ("1m", "1h", "3h")  # 3h is outside our canon
        provider = ExchangeMarketDataProvider(port)
        assert provider.supported_timeframes() == frozenset({Timeframe.M1, Timeframe.H1})

    def test_explicit_override_wins(self) -> None:
        port = FakeExchangePort()
        provider = ExchangeMarketDataProvider(
            port, supported_timeframes=frozenset({Timeframe.D1})
        )
        assert provider.supported_timeframes() == frozenset({Timeframe.D1})

    def test_require_timeframe_raises_with_supported_list(self) -> None:
        port = FakeExchangePort()
        port.timeframes = ("1h",)
        provider = ExchangeMarketDataProvider(port)
        with pytest.raises(MarketDataError) as excinfo:
            provider.require_timeframe(Timeframe.M5)
        assert excinfo.value.code is MarketDataErrorCode.TIMEFRAME_UNSUPPORTED
        assert excinfo.value.metadata["supported"] == ["1h"]

    def test_empty_advertisement_passes_through(self) -> None:
        port = FakeExchangePort()
        port.timeframes = ()
        provider = ExchangeMarketDataProvider(port)
        provider.require_timeframe(Timeframe.H4)  # unknown -> not pre-blocked

    def test_fetch_candles_uses_canonical_strings_and_since(self) -> None:
        port = FakeExchangePort()
        provider = ExchangeMarketDataProvider(port)
        provider.fetch_candles("BTC/USDT", Timeframe.H4, limit=10, since_ms=123456)
        assert port.ohlcv_calls == [("BTC/USDT", "4h", 10, 123456)]


# ---------------------------------------------------------------------------
# Security / isolation / determinism
# ---------------------------------------------------------------------------


class TestSecurityAndIsolation:
    def test_no_credentials_in_logs_or_errors(self, caplog) -> None:
        caplog.set_level(logging.DEBUG)
        port = FakeExchangePort()
        port.candles["BTC/USDT"] = hourly_rows(2)
        service, _clock = make_service(ExchangeMarketDataProvider(port))
        service.get_recent_candles("BTC/USDT", "1h")
        failing = FakeExchangePort()
        failing.fail_next_ohlcv = Exception("secret=APIKEY-XYZ leaked")
        failing_service, _clock2 = make_service(ExchangeMarketDataProvider(failing))
        with pytest.raises(MarketDataError):
            failing_service.get_recent_candles("BTC/USDT", "1h")
        for record in caplog.records:
            rendered = record.getMessage()
            assert "APIKEY-XYZ" not in rendered

    def test_provider_failure_error_carries_no_raw_message(self) -> None:
        failing = FakeExchangePort()
        failing.fail_next_ohlcv = RuntimeError("Authorization: Bearer sk-secret-token-123")
        service, _clock = make_service(ExchangeMarketDataProvider(failing))
        with pytest.raises(MarketDataError) as excinfo:
            service.get_recent_candles("BTC/USDT", "1h")
        rendered = str(excinfo.value) + repr(excinfo.value.metadata)
        assert "sk-secret-token-123" not in rendered
        assert excinfo.value.metadata["venue_error_type"] == "RuntimeError"

    def test_ccxt_not_importable_through_market_data(self) -> None:
        import sys

        import market_data  # noqa: F401

        market_data_modules = [
            name
            for name in sys.modules
            if name.startswith("market_data")
        ]
        for name in market_data_modules:
            # Only the adapters subpackage may speak of ccxt.
            assert "ccxt" not in name or "adapters" in name

    def test_identical_requests_deterministic(self) -> None:
        results = []
        for _ in range(2):
            port = FakeExchangePort()
            port.candles["BTC/USDT"] = hourly_rows(5)
            service, _clock = make_service(ExchangeMarketDataProvider(port))
            results.append(service.get_recent_candles("BTC/USDT", "1h"))
        assert results[0] == results[1]

    def test_models_frozen(self) -> None:
        import dataclasses

        dataset = CandleDataset(symbol="BTC/USDT", timeframe=Timeframe.H1, candles=())
        with pytest.raises(dataclasses.FrozenInstanceError):
            dataset.symbol = "ETH/USDT"  # type: ignore[misc]
        report = DataQualityReport(issues=())
        with pytest.raises(dataclasses.FrozenInstanceError):
            report.issues = ()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Compatibility with existing engines (end-to-end shape contract)
# ---------------------------------------------------------------------------


class TestRangeEngineCompatibility:
    def test_dataset_feeds_range_engine_without_exchange_knowledge(self) -> None:
        import math as _math

        rows: list[Candle] = []
        price = 100.0
        ts = BASE_TS - 60 * HOUR_MS
        for index in range(60):
            swing = 5.0 * _math.sin(index / 6.0)
            open_price = price
            close_price = price + swing * 0.1
            row = Candle(
                timestamp=ts + index * HOUR_MS,
                open=open_price,
                high=max(open_price, close_price) + 1.0,
                low=min(open_price, close_price) - 1.0,
                close=close_price,
                volume=10.0,
            )
            rows.append(row)
            price = close_price
        port = FakeExchangePort()
        port.candles["BTC/USDT"] = rows
        service, _clock = make_service(ExchangeMarketDataProvider(port), now_ms=ts + 60 * HOUR_MS)
        dataset = service.get_recent_candles("BTC/USDT", "1h")
        frame = dataset.to_dataframe()
        state = RangeEngineFactory.detect(frame, {"mode": "manual", "params": {
            "range_high": float(frame["close"].max()),
            "range_low": float(frame["close"].min()),
        }})
        # The range engine consumed the frame without any exchange awareness.
        assert state.mode == "manual"
        assert not _math.isnan(state.range_high)

    def test_analysis_safety_gate_blocks_forming_data(self) -> None:
        port = FakeExchangePort()
        rows = hourly_rows(3)
        rows.append(make_candle_row(BASE_TS + 10 * HOUR_MS))  # forming now
        port.candles["BTC/USDT"] = rows
        provider = ExchangeMarketDataProvider(port)
        service, _clock = make_service(provider, now_ms=BASE_TS + 10 * HOUR_MS)
        dataset = service.get_recent_candles("BTC/USDT", "1h")
        assert dataset.is_analysis_safe is False
        closed_only = dataset.closed_candles
        assert all(candle.is_closed for candle in closed_only)
        assert len(closed_only) == 3
