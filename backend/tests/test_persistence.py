"""Deterministic tests for the persistence layer.

Real SQLite files under ``tmp_path`` — still fully offline: no network, no
ccxt, no credentials.
"""

import dataclasses
from pathlib import Path

import pytest

from exchange.models import PositionDirection
from execution_engine.base import ExecutionStatus
from execution_engine.models import ExecutionResult
from market_data.models import (
    CandleDataset,
    DataQualityReport,
    MarketCandle,
    QualityIssue,
    Timeframe,
)
from persistence import (
    SCHEMA_VERSION,
    CandleRepository,
    DatasetSummary,
    PersistenceError,
    StoredTrade,
    TradeContext,
    TradeRepository,
    TradeResult,
    TradeStatus,
    TradeUpdate,
    classify_result,
    compute_trade_statistics,
    quality_status_of,
    trade_from_execution,
)

# ---------------------------------------------------------------------------
# Fakes / builders
# ---------------------------------------------------------------------------

HOUR_MS = 3_600_000
BASE_TS = 1_700_000_000_000


def make_store(tmp_path: Path, now_ms: int = 1_000):
    from persistence import SqlitePersistence

    clock = {"now": now_ms}

    def tick() -> int:
        return clock["now"]

    return SqlitePersistence(tmp_path / "test.db", clock_ms=tick), clock


def make_candles(symbol: str, count: int, *, start_ts: int = BASE_TS) -> tuple[MarketCandle, ...]:
    return tuple(
        MarketCandle(
            symbol=symbol,
            timeframe=Timeframe.H1,
            timestamp=start_ts + index * HOUR_MS,
            open=99.0 + index,
            high=103.0 + index,
            low=97.0 + index,
            close=101.0 + index,
            volume=float(index),
        )
        for index in range(count)
    )


def make_dataset(
    symbol: str = "BTC/USDT",
    count: int = 5,
    *,
    issues: tuple[QualityIssue, ...] = (),
    start_ts: int = BASE_TS,
) -> CandleDataset:
    report = DataQualityReport(issues=issues)
    return CandleDataset(
        symbol=symbol,
        timeframe=Timeframe.H1,
        candles=make_candles(symbol, count, start_ts=start_ts),
        quality=report,
        retrieved_at_ms=900,
    )


def make_open_trade(
    trade_id: str = "T-1",
    symbol: str = "BTC/USDT",
    **overrides: object,
) -> StoredTrade:
    values: dict[str, object] = {
        "trade_id": trade_id,
        "symbol": symbol,
        "direction": PositionDirection.LONG,
        "quantity": 2.0,
        "entry_price": 100.0,
        "opened_at_ms": BASE_TS,
        "status": TradeStatus.OPEN,
        "risk_amount": 50.0,
        "strategy_id": "range-v1",
        "config_hash": "cfg-abc123",
        "context": TradeContext(
            range_mode="structural",
            range_high=110.0,
            range_low=90.0,
            range_width=20.0,
            range_confidence=0.8,
            signal_direction="long",
            signal_reason="support_edge_setup",
            position_in_range=0.08,
            confirmation=True,
            stop_distance=5.0,
            target_distance=10.0,
            risk_percent=0.01,
            timeframe="1h",
            strategy_config_version="range-v1@2026-01",
            extra={"rsi_value": 28.5},
        ),
    }
    values.update(overrides)
    return StoredTrade(**values)  # type: ignore[arg-type]


def make_execution_result(**overrides: object) -> ExecutionResult:
    values: dict[str, object] = {
        "execution_id": "exec-req-9-entry",
        "symbol": "ETH/USDT",
        "status": ExecutionStatus.FILLED,
        "requested_quantity": 2.0,
        "filled_quantity": 2.0,
        "average_fill_price": 2000.0,
        "direction": PositionDirection.SHORT,
        "created_at_ms": BASE_TS,
        "completed_at_ms": BASE_TS + 5,
    }
    values.update(overrides)
    return ExecutionResult(**values)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Database: creation, schema versioning, migrations
# ---------------------------------------------------------------------------


class TestDatabaseLifecycle:
    def test_fresh_database_initializes_to_current_version(self, tmp_path: Path) -> None:
        store, _clock = make_store(tmp_path)
        assert store.schema_version == SCHEMA_VERSION == 1
        store.close()

    def test_ensure_schema_is_idempotent(self, tmp_path: Path) -> None:
        store, _clock = make_store(tmp_path)
        assert store.database.ensure_schema() == SCHEMA_VERSION
        assert store.database.schema_version() == SCHEMA_VERSION
        store.close()

    def test_schema_persists_across_reopen(self, tmp_path: Path) -> None:
        store, _clock = make_store(tmp_path)
        store.close()
        reopened, _clock2 = make_store(tmp_path)
        assert reopened.schema_version == SCHEMA_VERSION
        reopened.close()

    def test_future_schema_version_rejected(self, tmp_path: Path) -> None:
        store, _clock = make_store(tmp_path)
        with store.database.transaction() as conn:
            conn.execute("INSERT INTO schema_migrations VALUES (?, ?)", (99, 1))
        with pytest.raises(PersistenceError, match="newer than supported"):
            store.database.ensure_schema()
        store.close()

    def test_migration_history_is_contiguous(self) -> None:
        from persistence import MIGRATIONS

        versions = [migration.version for migration in MIGRATIONS]
        assert versions == list(range(1, len(versions) + 1))


# ---------------------------------------------------------------------------
# Candles: insertion, querying, idempotency, multi-pair/timeframe/source
# ---------------------------------------------------------------------------


class TestCandlePersistence:
    def test_ingest_and_query_chronological(self, tmp_path: Path) -> None:
        store, _clock = make_store(tmp_path)
        result = store.ingest_dataset(make_dataset(), source="binance")
        assert result.inserted == 5
        queried = store.query_candles("BTC/USDT", Timeframe.H1, source="binance")
        stamps = [candle.timestamp for candle in queried.candles]
        assert stamps == sorted(stamps)
        assert stamps[0] == BASE_TS
        assert queried.candles[4].close == pytest.approx(105.0)
        store.close()

    def test_repeated_ingestion_is_idempotent(self, tmp_path: Path) -> None:
        store, _clock = make_store(tmp_path)
        dataset = make_dataset()
        first = store.ingest_dataset(dataset, source="binance")
        second = store.ingest_dataset(dataset, source="binance")
        third = store.ingest_dataset(dataset, source="binance")
        assert (first.inserted, first.updated, first.unchanged) == (5, 0, 0)
        assert (second.inserted, second.updated, second.unchanged) == (0, 0, 5)
        assert (third.inserted, third.updated, third.unchanged) == (0, 0, 5)
        assert second.summary == first.summary
        queried = store.query_candles("BTC/USDT", Timeframe.H1)
        assert len(queried.candles) == 5
        store.close()

    def test_forming_candle_refresh_updates_not_duplicates(self, tmp_path: Path) -> None:
        store, _clock = make_store(tmp_path)
        forming_ts = BASE_TS + 5 * HOUR_MS
        initial = make_dataset(count=5)
        forming = MarketCandle(
            symbol="BTC/USDT", timeframe=Timeframe.H1, timestamp=forming_ts,
            open=104.0, high=106.0, low=100.0, close=105.0,
            volume=1.0, is_closed=False,
        )
        with_forming = CandleDataset(
            symbol="BTC/USDT", timeframe=Timeframe.H1,
            candles=initial.candles + (forming,),
            quality=DataQualityReport(issues=(
                QualityIssue(kind="unclosed_candle_present", detail="forming"),
            )),
        )
        store.ingest_dataset(with_forming, source="binance")
        closed_later = MarketCandle(
            symbol="BTC/USDT", timeframe=Timeframe.H1, timestamp=forming_ts,
            open=104.0, high=107.0, low=100.0, close=106.5, volume=9.0, is_closed=True,
        )
        refreshed = CandleDataset(
            symbol="BTC/USDT", timeframe=Timeframe.H1,
            candles=initial.candles + (closed_later,),
            quality=DataQualityReport(),
        )
        result = store.ingest_dataset(refreshed, source="binance")
        assert result.inserted == 0 and result.updated == 1 and result.unchanged == 5
        queried = store.query_candles("BTC/USDT", Timeframe.H1)
        assert len(queried.candles) == 6
        last = queried.candles[-1]
        assert last.is_closed is True and last.close == pytest.approx(106.5)
        store.close()

    def test_multiple_symbols_isolated(self, tmp_path: Path) -> None:
        store, _clock = make_store(tmp_path)
        for symbol in ("BTC/USDT", "ETH/USDT", "SOL/USDT"):
            store.ingest_dataset(make_dataset(symbol=symbol, count=3), source="binance")
        btc = store.query_candles("BTC/USDT", Timeframe.H1)
        eth = store.query_candles("ETH/USDT", Timeframe.H1)
        sol = store.query_candles("SOL/USDT", Timeframe.H1)
        assert len(btc.candles) == len(eth.candles) == len(sol.candles) == 3
        assert all(candle.symbol == "BTC/USDT" for candle in btc.candles)
        summaries = store.list_dataset_summaries()
        assert {summary.symbol for summary in summaries} == {
            "BTC/USDT", "ETH/USDT", "SOL/USDT"}
        store.close()

    def test_multiple_timeframes_and_sources_coexist(self, tmp_path: Path) -> None:
        store, clock = make_store(tmp_path)
        h1 = make_dataset(count=3)
        h4 = CandleDataset(
            symbol="BTC/USDT", timeframe=Timeframe.H4,
            candles=tuple(
                MarketCandle("BTC/USDT", Timeframe.H4, BASE_TS + i * 4 * HOUR_MS,
                             99., 103., 97., 101., volume=1.)
                for i in range(3)
            ),
            quality=DataQualityReport(),
        )
        store.ingest_dataset(h1, source="binance")
        store.ingest_dataset(h4, source="binance")
        clock["now"] = 5_000  # bybit ingestion is strictly newer
        store.ingest_dataset(h1, source="bybit")
        by_source = [
            store.query_candles("BTC/USDT", Timeframe.H1, source=name)
            for name in ("binance", "bybit")
        ]
        assert all(len(dataset.candles) == 3 for dataset in by_source)
        assert store.dataset_summary("BTC/USDT", Timeframe.H1).source == "bybit"
        explicit = store.dataset_summary(
            "BTC/USDT", Timeframe.H1, source="binance"
        )
        assert explicit is not None and explicit.updated_at_ms == 1_000
        assert len(store.list_dataset_summaries()) == 3
        store.close()

    def test_window_query_bounds(self, tmp_path: Path) -> None:
        store, _clock = make_store(tmp_path)
        store.ingest_dataset(make_dataset(count=10), source="binance")
        windowed = store.query_candles(
            "BTC/USDT", Timeframe.H1,
            start_ms=BASE_TS + 2 * HOUR_MS,
            end_ms=BASE_TS + 6 * HOUR_MS,
            source="binance",
        )
        stamps = [candle.timestamp for candle in windowed.candles]
        assert stamps[0] == BASE_TS + 2 * HOUR_MS
        assert stamps[-1] < BASE_TS + 6 * HOUR_MS
        assert len(stamps) == 4
        store.close()

    def test_empty_symbol_rejected(self, tmp_path: Path) -> None:
        store, _clock = make_store(tmp_path)
        with pytest.raises(PersistenceError, match="source"):
            store.ingest_dataset(make_dataset(), source="   ")
        store.close()

# ---------------------------------------------------------------------------
# Data-quality persistence
# ---------------------------------------------------------------------------


class TestQualityPersistence:
    def test_clean_report_stored_as_clean(self, tmp_path: Path) -> None:
        store, _clock = make_store(tmp_path)
        result = store.ingest_dataset(make_dataset(), source="binance")
        assert result.summary.quality_status is quality_status_of(DataQualityReport())
        loaded = store.load_dataset("BTC/USDT", Timeframe.H1)
        assert loaded is not None and loaded.quality.is_clean
        store.close()

    def test_gap_metadata_roundtrips(self, tmp_path: Path) -> None:
        issues = (
            QualityIssue(
                kind="missing_interval",
                detail="missing 2 x 1h candle(s)",
                gap_start_ms=BASE_TS + HOUR_MS,
                gap_end_ms=BASE_TS + 3 * HOUR_MS,
            ),
            QualityIssue(kind="duplicate_timestamp", detail="dupe at index 4", index=4),
        )
        store, _clock = make_store(tmp_path)
        store.ingest_dataset(make_dataset(issues=issues), source="binance")
        loaded = store.load_dataset("BTC/USDT", Timeframe.H1, source="binance")
        assert loaded is not None
        assert not loaded.quality.is_clean
        assert loaded.quality.issue_kinds == {"missing_interval", "duplicate_timestamp"}
        assert loaded.quality.gap_ranges == ((BASE_TS + HOUR_MS, BASE_TS + 3 * HOUR_MS),)
        summary = store.dataset_summary("BTC/USDT", Timeframe.H1, source="binance")
        assert summary is not None and summary.quality_status.value == "warnings"
        store.close()

    def test_forming_candle_persisted_with_closed_flag(self, tmp_path: Path) -> None:
        forming = MarketCandle(
            symbol="BTC/USDT", timeframe=Timeframe.H1, timestamp=BASE_TS,
            open=99., high=103., low=97., close=101., volume=2., is_closed=False,
        )
        dataset = CandleDataset(
            symbol="BTC/USDT", timeframe=Timeframe.H1, candles=(forming,),
            quality=DataQualityReport(issues=(
                QualityIssue(kind="unclosed_candle_present", detail="forming"),
            )),
        )
        store, _clock = make_store(tmp_path)
        store.ingest_dataset(dataset, source="binance")
        queried = store.query_candles("BTC/USDT", Timeframe.H1)
        assert queried.candles[0].is_closed is False
        assert queried.is_analysis_safe is False
        store.close()


# ---------------------------------------------------------------------------
# Dataset metadata
# ---------------------------------------------------------------------------


class TestDatasetMetadata:
    def test_summary_fields_after_ingestion(self, tmp_path: Path) -> None:
        store, _clock = make_store(tmp_path)
        result = store.ingest_dataset(make_dataset(count=5), source="binance")
        summary = result.summary
        assert isinstance(summary, DatasetSummary)
        assert summary.symbol == "BTC/USDT"
        assert summary.timeframe == "1h"
        assert summary.source == "binance"
        assert summary.first_timestamp_ms == BASE_TS
        assert summary.last_timestamp_ms == BASE_TS + 4 * HOUR_MS
        assert summary.candle_count == 5
        store.close()

    def test_summary_updates_on_new_window(self, tmp_path: Path) -> None:
        store, clock = make_store(tmp_path)
        store.ingest_dataset(make_dataset(count=3), source="binance")
        clock["now"] = 5_000
        extended = CandleDataset(
            symbol="BTC/USDT", timeframe=Timeframe.H1,
            candles=make_candles("BTC/USDT", 6),
            quality=DataQualityReport(),
        )
        result = store.ingest_dataset(extended, source="binance")
        assert result.inserted == 3 and result.summary.candle_count == 6
        assert result.summary.last_timestamp_ms == BASE_TS + 5 * HOUR_MS
        assert result.summary.updated_at_ms == 5_000
        assert result.summary.ingested_at_ms == 1_000  # original ingestion kept
        store.close()

    def test_missing_summary_is_none(self, tmp_path: Path) -> None:
        store, _clock = make_store(tmp_path)
        assert store.dataset_summary("DOGE/USDT", "1h") is None
        assert store.load_dataset("DOGE/USDT", "1h") is None
        store.close()


# ---------------------------------------------------------------------------
# Trades
# ---------------------------------------------------------------------------


class TestTradePersistence:
    def test_record_and_retrieve_open_trade(self, tmp_path: Path) -> None:
        store, _clock = make_store(tmp_path)
        stored = store.record_trade(make_open_trade(), now_ms=1_500)
        assert stored.created_at_ms == 1_500 and stored.updated_at_ms == 1_500
        fetched = store.get_trade("T-1")
        assert fetched is not None and fetched.status is TradeStatus.OPEN
        assert fetched.result is None and fetched.exit_price is None
        assert fetched.context.signal_reason == "support_edge_setup"
        assert fetched.config_hash == "cfg-abc123"
        store.close()

    def test_close_trade_computes_result_and_r(self, tmp_path: Path) -> None:
        store, _clock = make_store(tmp_path)
        store.record_trade(make_open_trade(), now_ms=1_000)
        closed = store.close_trade(
            "T-1",
            TradeUpdate(exit_price=110.0, closed_at_ms=BASE_TS + HOUR_MS, realized_pnl=100.0),
            now_ms=2_000,
        )
        assert closed.status is TradeStatus.CLOSED
        assert closed.exit_price == pytest.approx(110.0)
        assert closed.result is TradeResult.WIN
        assert closed.realized_r == pytest.approx(2.0)  # +100 P&L / $50 risk
        store.close()

    @pytest.mark.parametrize(("pnl", "expected"), [
        (100.0, TradeResult.WIN),
        (-100.0, TradeResult.LOSS),
        (0.0, TradeResult.BREAKEVEN),
        (1e-12, TradeResult.BREAKEVEN),
    ])
    def test_result_classification(self, tmp_path: Path, pnl: float, expected: TradeResult) -> None:
        assert classify_result(pnl) is expected

    def test_loss_and_breakeven_trades(self, tmp_path: Path) -> None:
        store, _clock = make_store(tmp_path)
        for trade_id, pnl in (("L-1", -50.0), ("B-1", 0.0)):
            store.record_trade(
                make_open_trade(trade_id=trade_id, symbol="ETH/USDT"), now_ms=1_000
            )
            store.close_trade(
                trade_id,
                TradeUpdate(exit_price=90.0, closed_at_ms=BASE_TS + HOUR_MS, realized_pnl=pnl),
                now_ms=2_000,
            )
        loss = store.get_trade("L-1")
        breakeven = store.get_trade("B-1")
        assert loss is not None and loss.result is TradeResult.LOSS
        assert loss.realized_r == pytest.approx(-1.0)
        assert breakeven is not None and breakeven.result is TradeResult.BREAKEVEN
        store.close()

    def test_fees_slippage_and_gross_pnl(self, tmp_path: Path) -> None:
        store, _clock = make_store(tmp_path)
        store.record_trade(make_open_trade(), now_ms=1_000)
        closed = store.close_trade(
            "T-1",
            TradeUpdate(exit_price=105.0, closed_at_ms=BASE_TS + HOUR_MS,
                        realized_pnl=100.0, fees=2.5, slippage=0.5),
            now_ms=2_000,
        )
        assert closed.fees == pytest.approx(2.5) and closed.slippage == pytest.approx(0.5)
        assert closed.gross_pnl == pytest.approx(97.5)
        store.close()

    def test_duplicate_trade_id_rejected(self, tmp_path: Path) -> None:
        store, _clock = make_store(tmp_path)
        store.record_trade(make_open_trade(trade_id="DUP"), now_ms=1_000)
        with pytest.raises(PersistenceError, match="already exists"):
            store.record_trade(make_open_trade(trade_id="DUP"), now_ms=2_000)
        store.close()

    def test_open_trade_invariants_enforced_by_model(self) -> None:
        with pytest.raises(ValueError, match="cannot carry"):
            dataclasses.replace(
                make_open_trade(trade_id="X"), realized_pnl=10.0
            )
        with pytest.raises(ValueError, match="result"):
            dataclasses.replace(
                make_open_trade(trade_id="Y"),
                status=TradeStatus.OPEN, result=TradeResult.WIN,
            )

    def test_close_unknown_or_already_closed_rejected(self, tmp_path: Path) -> None:
        store, _clock = make_store(tmp_path)
        with pytest.raises(PersistenceError, match="unknown trade"):
            store.close_trade(
                "GHOST", TradeUpdate(exit_price=1.0, closed_at_ms=BASE_TS), now_ms=9_999
            )
        store.record_trade(make_open_trade(trade_id="C-1"), now_ms=1_000)
        store.close_trade(
            "C-1",
            TradeUpdate(exit_price=101.0, closed_at_ms=BASE_TS + HOUR_MS, realized_pnl=2.0),
            now_ms=2_000,
        )
        with pytest.raises(PersistenceError, match="already closed"):
            store.close_trade(
                "C-1",
                TradeUpdate(exit_price=102.0, closed_at_ms=BASE_TS + 2 * HOUR_MS,
                            realized_pnl=4.0),
                now_ms=3_000,
            )
        store.close()

    def test_list_trades_filters(self, tmp_path: Path) -> None:
        store, _clock = make_store(tmp_path)
        store.record_trade(make_open_trade(trade_id="W", symbol="BTC/USDT"), now_ms=1)
        store.record_trade(make_open_trade(trade_id="L", symbol="ETH/USDT"), now_ms=1)
        store.record_trade(
            make_open_trade(trade_id="O", symbol="BTC/USDT", strategy_id="range-v2"), now_ms=1
        )
        store.close_trade(
            "W", TradeUpdate(exit_price=110., closed_at_ms=BASE_TS + HOUR_MS,
                             realized_pnl=100.), now_ms=2)
        store.close_trade(
            "L", TradeUpdate(exit_price=95., closed_at_ms=BASE_TS + 2 * HOUR_MS,
                             realized_pnl=-50.), now_ms=2)
        all_trades = store.list_trades()
        assert len(all_trades) == 3
        assert [t.trade_id for t in store.list_trades(symbol="BTC/USDT")] == ["W", "O"]
        wins = store.list_trades(result=TradeResult.WIN)
        assert [t.trade_id for t in wins] == ["W"]
        open_only = store.list_trades(status=TradeStatus.OPEN)
        assert [t.trade_id for t in open_only] == ["O"]
        by_strategy = store.list_trades(strategy_id="range-v2")
        assert [t.trade_id for t in by_strategy] == ["O"]
        windowed = store.list_trades(closed_from_ms=BASE_TS + 2 * HOUR_MS)
        assert [t.trade_id for t in windowed] == ["L"]
        store.close()

    def test_context_json_roundtrip_with_extra(self, tmp_path: Path) -> None:
        store, _clock = make_store(tmp_path)
        context = TradeContext(
            range_mode="volatility_bollinger", range_high=105.0,
            extra={"rsi_value": 27.1, "note": "clean setup"},
        )
        store.record_trade(make_open_trade(trade_id="CTX", context=context), now_ms=1)
        fetched = store.get_trade("CTX")
        assert fetched is not None and fetched.context is not None
        assert fetched.context.extra["rsi_value"] == pytest.approx(27.1)
        assert fetched.context.range_high == pytest.approx(105.0)
        assert fetched.context.range_mode == "volatility_bollinger"
        assert fetched.context.range_low is None  # absent facts stay None
        store.close()


# ---------------------------------------------------------------------------
# Execution -> trade boundary (Phase 5 composition; no lifecycle changes)
# ---------------------------------------------------------------------------


class TestExecutionLink:
    def test_filled_execution_becomes_open_trade(self) -> None:
        trade = trade_from_execution(
            make_execution_result(),
            trade_id="EX-1",
            risk_amount=25.0,
            timeframe="1h",
            strategy_id="range-v1",
            created_at_ms=7_000,
        )
        assert trade.status is TradeStatus.OPEN
        assert trade.direction is PositionDirection.SHORT
        assert trade.quantity == pytest.approx(2.0)
        assert trade.entry_price == pytest.approx(2000.0)
        assert trade.execution_ref == "exec-req-9-entry"
        assert trade.risk_amount == pytest.approx(25.0)

    def test_non_filled_execution_rejected(self) -> None:
        for status in (
            ExecutionStatus.REJECTED,
            ExecutionStatus.UNKNOWN,
            ExecutionStatus.SUBMITTED,
            ExecutionStatus.PENDING,
        ):
            with pytest.raises(PersistenceError, match="only filled"):
                trade_from_execution(
                    make_execution_result(status=status), trade_id="X"
                )

    def test_execution_without_direction_or_price_rejected(self) -> None:
        with pytest.raises(PersistenceError, match="no direction"):
            trade_from_execution(
                make_execution_result(direction=None), trade_id="X"
            )
        with pytest.raises(PersistenceError, match="fill price"):
            trade_from_execution(
                make_execution_result(average_fill_price=None), trade_id="X"
            )

    def test_zero_fill_rejected(self) -> None:
        with pytest.raises(PersistenceError, match="no filled quantity"):
            trade_from_execution(
                make_execution_result(filled_quantity=0.0), trade_id="X"
            )

    def test_full_lifecycle_through_persistence(self, tmp_path: Path) -> None:
        store, _clock = make_store(tmp_path)
        execution = make_execution_result()
        trade = trade_from_execution(execution, trade_id="LC-1", risk_amount=40.0)
        store.record_trade(trade, now_ms=1_000)
        closed = store.close_trade(
            "LC-1",
            TradeUpdate(exit_price=1900.0, closed_at_ms=BASE_TS + HOUR_MS,
                        realized_pnl=-40.0),
            now_ms=2_000,
        )
        # Short from 2000 covered at 1900 => profit; here P&L given as loss of
        # one risk unit => LOSS with exactly -1R.
        assert closed.result is TradeResult.LOSS
        assert closed.realized_r == pytest.approx(-1.0)
        store.close()


# ---------------------------------------------------------------------------
# Trade statistics (derived, explicit definitions)
# ---------------------------------------------------------------------------


def closed_trade(trade_id: str, pnl: float, *, r: float | None = None,
                 closed_at: int | None = None) -> StoredTrade:
    opened = BASE_TS
    closed_ts = closed_at if closed_at is not None else opened + HOUR_MS
    risk = 50.0
    return StoredTrade(
        trade_id=trade_id,
        symbol="BTC/USDT",
        direction=PositionDirection.LONG,
        quantity=1.0,
        entry_price=100.0,
        opened_at_ms=opened,
        status=TradeStatus.CLOSED,
        exit_price=101.0,
        closed_at_ms=closed_ts,
        realized_pnl=pnl,
        risk_amount=risk if r is not None else None,
        realized_r=r,
    )


class TestTradeStatistics:
    def test_counts_and_win_rate_excludes_breakevens(self) -> None:
        trades = [
            closed_trade("W1", 100.0),
            closed_trade("W2", 40.0),
            closed_trade("L1", -60.0),
            closed_trade("B1", 0.0),
            make_open_trade(trade_id="OPEN"),
        ]
        stats = compute_trade_statistics(trades)
        assert stats.total_trades == 5 and stats.open_trades == 1
        assert stats.completed_trades == 4
        assert (stats.wins, stats.losses, stats.breakevens) == (2, 1, 1)
        # Definition: wins / (wins + losses); breakeven excluded.
        assert stats.win_rate == pytest.approx(2 / 3)

    def test_averages_and_totals(self) -> None:
        trades = [
            closed_trade("W1", 100.0),
            closed_trade("L1", -60.0),
            closed_trade("B1", 0.0),
        ]
        stats = compute_trade_statistics(trades)
        assert stats.average_win == pytest.approx(100.0)
        assert stats.average_loss == pytest.approx(-60.0)
        assert stats.total_realized_pnl == pytest.approx(40.0)
        assert stats.expectancy == pytest.approx(40.0 / 3)

    def test_average_r_over_r_bearing_trades(self) -> None:
        trades = [
            closed_trade("R1", 100.0, r=2.0),
            closed_trade("R2", -50.0, r=-1.0),
            closed_trade("NR", 10.0),  # no R recorded; excluded from average
        ]
        stats = compute_trade_statistics(trades)
        assert stats.average_r == pytest.approx(0.5)

    def test_profit_factor_none_without_losses(self) -> None:
        stats = compute_trade_statistics([closed_trade("W", 10.0)])
        assert stats.profit_factor is None  # undefined, never infinity

    def test_profit_factor_computed_with_losses(self) -> None:
        trades = [closed_trade("W1", 150.0), closed_trade("W2", 50.0),
                  closed_trade("L1", -80.0)]
        stats = compute_trade_statistics(trades)
        assert stats.profit_factor == pytest.approx(200.0 / 80.0)

    def test_max_drawdown_from_cumulative_curve(self) -> None:
        trades = [
            closed_trade("T1", +100.0, closed_at=BASE_TS + HOUR_MS),
            closed_trade("T2", -30.0, closed_at=BASE_TS + 2 * HOUR_MS),
            closed_trade("T3", -50.0, closed_at=BASE_TS + 3 * HOUR_MS),
            closed_trade("T4", +20.0, closed_at=BASE_TS + 4 * HOUR_MS),
        ]
        stats = compute_trade_statistics(trades)
        # Curve: 100, 70, 20, 40 => peak 100, trough 20 => drawdown 80.
        assert stats.max_drawdown == pytest.approx(80.0)

    def test_max_drawdown_none_without_history(self) -> None:
        stats = compute_trade_statistics([closed_trade("ONLY", 5.0)])
        assert stats.max_drawdown is None

    def test_empty_input(self) -> None:
        stats = compute_trade_statistics([])
        assert stats.win_rate is None and stats.total_trades == 0


# ---------------------------------------------------------------------------
# Transactions: commit / rollback semantics
# ---------------------------------------------------------------------------


class TestTransactions:
    def test_successful_ingestion_commits_atomically(self, tmp_path: Path) -> None:
        store, _clock = make_store(tmp_path)
        store.ingest_dataset(make_dataset(count=4), source="binance")
        reopened, _c2 = make_store(tmp_path)
        queried = reopened.query_candles("BTC/USDT", Timeframe.H1)
        assert len(queried.candles) == 4
        reopened.close()
        store.close()

    def test_failed_batch_leaves_no_partial_writes(self, tmp_path: Path) -> None:
        """A failure inside one transaction scope rolls back everything."""
        store, _clock = make_store(tmp_path)
        valid_row = (
            "BTC/USDT", "1h", BASE_TS, 99.0, 103.0, 97.0, 101.0, 2.0, 1, "binance", 1
        )
        with pytest.raises(PersistenceError, match="IntegrityError"):
            with store.database.transaction() as conn:  # noqa: SLF001 - fault injection
                conn.execute(
                    "INSERT INTO candles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    valid_row,
                )
                # Second statement violates the schema mid-"batch".
                conn.execute(
                    "INSERT INTO candles VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("BTC/USDT", "1h", 101.0, 103.0, 97.0, 101.0, 2.0, 1, "binance", 1),
                )
        queried = store.query_candles("BTC/USDT", Timeframe.H1)
        assert queried.candles == ()  # first insert was rolled back too
        assert store.list_dataset_summaries() == ()
        store.close()

    def test_ingestion_failure_via_bad_source_never_touches_db(self, tmp_path: Path) -> None:
        store, _clock = make_store(tmp_path)
        store.ingest_dataset(make_dataset(count=2), source="binance")
        with pytest.raises(PersistenceError):
            store.ingest_dataset(make_dataset(count=9), source="")
        assert len(store.query_candles("BTC/USDT", Timeframe.H1).candles) == 2
        store.close()

    def test_explicit_rollback_on_python_exception(self, tmp_path: Path) -> None:
        store, _clock = make_store(tmp_path)
        with pytest.raises(RuntimeError):
            with store.database.transaction() as conn:
                conn.execute(
                    "INSERT INTO trades VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                    "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    ("TX", None, "BTC/USDT", None, "long", 1.0, 100.0, None,
                     BASE_TS, None, "open", None, None, None, None, None, None,
                     None, None, None, 1, 1),
                )
                raise RuntimeError("application error mid-transaction")
        assert store.get_trade("TX") is None
        store.close()


# ---------------------------------------------------------------------------
# Pipeline compatibility + architectural isolation
# ---------------------------------------------------------------------------


class TestPipelineAndIsolation:
    def test_queried_data_feeds_range_engine(self, tmp_path: Path) -> None:
        from range_engine import RangeEngineFactory

        store, _clock = make_store(tmp_path)
        store.ingest_dataset(make_dataset(count=30), source="binance")
        dataset = store.query_candles("BTC/USDT", Timeframe.H1, source="binance")
        frame = dataset.to_dataframe()
        state = RangeEngineFactory.detect(frame, {"mode": "manual", "params": {
            "range_high": float(frame["high"].max()),
            "range_low": float(frame["low"].min()),
        }})
        assert state.mode == "manual"
        store.close()

    def test_repositories_satisfy_ports(self, tmp_path: Path) -> None:
        store, _clock = make_store(tmp_path)
        assert isinstance(store, CandleRepository)
        assert isinstance(store, TradeRepository)
        store.close()

    def test_domain_engines_never_import_sqlite_or_persistence(self) -> None:
        domain_packages = [
            "range_engine",
            "signal_engine",
            "risk_engine",
            "execution_engine",
            "market_data",
            "exchange",
        ]
        src_root = Path(__file__).resolve().parents[1] / "src"
        violations: list[str] = []
        for package in domain_packages:
            for module_file in (src_root / package).rglob("*.py"):
                text = module_file.read_text(encoding="utf-8")
                if "import sqlite3" in text or "from persistence" in text:
                    violations.append(str(module_file.relative_to(src_root)))
        assert violations == []

    def test_no_secrets_written_to_database(self, tmp_path: Path) -> None:
        store, _clock = make_store(tmp_path)
        store.record_trade(
            make_open_trade(trade_id="SEC", context=TradeContext(extra={"api_key": "leaked"})),
            now_ms=1,
        )
        raw_bytes = (tmp_path / "test.db").read_bytes()
        assert b"leaked" in raw_bytes  # context extra is user diagnostics...
        # ...but credential-style top-level fields never exist on trades.
        columns = [
            row["name"]
            for row in store.database._conn.execute(  # noqa: SLF001
                "PRAGMA table_info(trades)"
            ).fetchall()
        ]
        forbidden = {"api_key", "secret", "password", "token"}
        assert not forbidden & set(columns)
        store.close()
