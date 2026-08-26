"""SQLite-backed implementations of the persistence ports.

One :class:`SqlitePersistence` instance implements both
:class:`~persistence.base.CandleRepository` and
:class:`~persistence.base.TradeRepository` over a single connection. All
writes are transactional; ingestion is idempotent per
``(symbol, timeframe, timestamp, source)``.
"""

import dataclasses
import json
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import cast

from exchange.models import PositionDirection
from market_data.models import (
    CandleDataset,
    DataQualityReport,
    MarketCandle,
    QualityIssue,
    Timeframe,
)
from persistence.adapters.sqlite.database import SqliteDatabase, utc_clock_ms
from persistence.base import BacktestRunRepository, CandleRepository, TradeRepository
from persistence.errors import PersistenceError, PersistenceErrorCode
from persistence.models import (
    BacktestRunRecord,
    DatasetSummary,
    IngestionResult,
    QualityStatus,
    StoredTrade,
    TradeContext,
    TradeResult,
    TradeStatus,
    TradeUpdate,
    quality_status_of,
)


def _require_source(source: str) -> None:
    if not isinstance(source, str) or not source.strip():
        raise PersistenceError(
            PersistenceErrorCode.REQUEST_INVALID,
            "source must be a non-empty string",
        )


def _issues_to_json(report: DataQualityReport) -> str:
    payload = [
        {
            "kind": issue.kind,
            "detail": issue.detail,
            "index": issue.index,
            "gap_start_ms": issue.gap_start_ms,
            "gap_end_ms": issue.gap_end_ms,
        }
        for issue in report.issues
    ]
    return json.dumps(payload, sort_keys=True)


def _report_from_json(raw: str) -> DataQualityReport:
    items = json.loads(raw)
    issues = tuple(
        QualityIssue(
            kind=str(item["kind"]),
            detail=str(item["detail"]),
            index=item.get("index"),
            gap_start_ms=item.get("gap_start_ms"),
            gap_end_ms=item.get("gap_end_ms"),
        )
        for item in items
        if isinstance(item, dict)
    )
    return DataQualityReport(issues=issues)


class SqlitePersistence(CandleRepository, TradeRepository, BacktestRunRepository):
    """SQLite store implementing both repository ports over one connection."""

    def __init__(
        self,
        path: str | Path,
        *,
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        self._db = SqliteDatabase(path)
        self._clock_ms = clock_ms if clock_ms is not None else utc_clock_ms
        self.schema_version = self._db.ensure_schema()

    # ----- plumbing -----

    @property
    def database(self) -> SqliteDatabase:
        return self._db

    def close(self) -> None:
        self._db.close()

    # ==================================================================
    # CandleRepository
    # ==================================================================

    def ingest_dataset(self, dataset: CandleDataset, *, source: str) -> IngestionResult:
        _require_source(source)
        timeframe_value = dataset.timeframe.value
        now = self._clock_ms()
        inserted = updated = unchanged = 0

        with self._db.transaction() as conn:
            for candle in dataset.candles:
                row = conn.execute(
                    """
                    SELECT open, high, low, close, volume, is_closed
                    FROM candles
                    WHERE symbol=? AND timeframe=? AND ts=? AND source=?
                    """,
                    (candle.symbol, timeframe_value, candle.timestamp, source),
                ).fetchone()
                if row is None:
                    conn.execute(
                        """
                        INSERT INTO candles
                            (symbol, timeframe, ts, open, high, low, close,
                             volume, is_closed, source, ingested_at_ms)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            candle.symbol,
                            timeframe_value,
                            candle.timestamp,
                            candle.open,
                            candle.high,
                            candle.low,
                            candle.close,
                            candle.volume,
                            int(candle.is_closed),
                            source,
                            now,
                        ),
                    )
                    inserted += 1
                    continue
                stored_facts = (row[0], row[1], row[2], row[3], row[4], bool(row[5]))
                incoming_facts = (
                    candle.open,
                    candle.high,
                    candle.low,
                    candle.close,
                    candle.volume,
                    candle.is_closed,
                )
                if stored_facts == incoming_facts:
                    unchanged += 1
                else:
                    conn.execute(
                        """
                        UPDATE candles
                        SET open=?, high=?, low=?, close=?, volume=?, is_closed=?,
                            ingested_at_ms=?
                        WHERE symbol=? AND timeframe=? AND ts=? AND source=?
                        """,
                        (
                            candle.open,
                            candle.high,
                            candle.low,
                            candle.close,
                            candle.volume,
                            int(candle.is_closed),
                            now,
                            candle.symbol,
                            timeframe_value,
                            candle.timestamp,
                            source,
                        ),
                    )
                    updated += 1

            aggregates = conn.execute(
                """
                SELECT COALESCE(MIN(ts), -1), COALESCE(MAX(ts), -1), COUNT(*)
                FROM candles
                WHERE symbol=? AND timeframe=? AND source=?
                """,
                (dataset.symbol, timeframe_value, source),
            ).fetchone()
            first_ts = int(aggregates[0]) if aggregates[0] != -1 else None
            last_ts = int(aggregates[1]) if aggregates[1] != -1 else None
            candle_count = int(aggregates[2])

            existing_dataset = conn.execute(
                """
                SELECT ingested_at_ms FROM datasets
                WHERE symbol=? AND timeframe=? AND source=?
                """,
                (dataset.symbol, timeframe_value, source),
            ).fetchone()
            first_ingested = int(existing_dataset[0]) if existing_dataset is not None else now
            status = quality_status_of(dataset.quality)
            conn.execute(
                """
                INSERT INTO datasets
                    (symbol, timeframe, source, first_ts, last_ts, candle_count,
                     quality_status, issues_json, ingested_at_ms, updated_at_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, timeframe, source) DO UPDATE SET
                    first_ts=excluded.first_ts,
                    last_ts=excluded.last_ts,
                    candle_count=excluded.candle_count,
                    quality_status=excluded.quality_status,
                    issues_json=excluded.issues_json,
                    updated_at_ms=excluded.updated_at_ms
                """,
                (
                    dataset.symbol,
                    timeframe_value,
                    source,
                    first_ts,
                    last_ts,
                    candle_count,
                    status.value,
                    _issues_to_json(dataset.quality),
                    first_ingested,
                    now,
                ),
            )

        summary = DatasetSummary(
            symbol=dataset.symbol,
            timeframe=timeframe_value,
            source=source,
            candle_count=candle_count,
            first_timestamp_ms=first_ts,
            last_timestamp_ms=last_ts,
            quality_status=status,
            ingested_at_ms=first_ingested,
            updated_at_ms=now,
        )
        return IngestionResult(
            inserted=inserted, updated=updated, unchanged=unchanged, summary=summary
        )

    def query_candles(
        self,
        symbol: str,
        timeframe: Timeframe | str,
        *,
        start_ms: int | None = None,
        end_ms: int | None = None,
        source: str | None = None,
    ) -> CandleDataset:
        tf = Timeframe.parse(timeframe)
        rows = self._select_candles(
            symbol, tf.value, start_ms=start_ms, end_ms=end_ms, source=source
        )
        candles = tuple(self._row_to_market_candle(row, symbol, tf) for row in rows)
        return CandleDataset(
            symbol=symbol,
            timeframe=tf,
            candles=candles,
            quality=DataQualityReport(issues=()),
            retrieved_at_ms=self._clock_ms(),
        )

    def load_dataset(
        self,
        symbol: str,
        timeframe: Timeframe | str,
        *,
        source: str | None = None,
    ) -> CandleDataset | None:
        tf = Timeframe.parse(timeframe)
        with self._db.transaction() as conn:
            dataset_row = self._pick_dataset_row(conn, symbol, tf.value, source)
            if dataset_row is None:
                return None
            rows = conn.execute(
                """
                SELECT ts, open, high, low, close, volume, is_closed
                FROM candles
                WHERE symbol=? AND timeframe=? AND source=?
                ORDER BY ts ASC
                """,
                (symbol, tf.value, dataset_row["source"]),
            ).fetchall()
        candles = tuple(self._row_to_market_candle(row, symbol, tf) for row in rows)
        return CandleDataset(
            symbol=symbol,
            timeframe=tf,
            candles=candles,
            quality=_report_from_json(dataset_row["issues_json"]),
            retrieved_at_ms=self._clock_ms(),
        )

    def dataset_summary(
        self, symbol: str, timeframe: Timeframe | str, *, source: str | None = None
    ) -> DatasetSummary | None:
        tf = Timeframe.parse(timeframe)
        with self._db.transaction() as conn:
            row = self._pick_dataset_row(conn, symbol, tf.value, source)
        return self._summary_from_row(row) if row is not None else None

    def list_dataset_summaries(self) -> tuple[DatasetSummary, ...]:
        with self._db.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM datasets ORDER BY symbol, timeframe, source"
            ).fetchall()
        return tuple(summary for summary in (self._summary_from_row(r) for r in rows))

    # ----- candle internals -----

    def _select_candles(
        self,
        symbol: str,
        timeframe_value: str,
        *,
        start_ms: int | None,
        end_ms: int | None,
        source: str | None,
    ) -> list[sqlite3.Row]:
        sql = """
            SELECT ts, open, high, low, close, volume, is_closed
            FROM candles
            WHERE symbol=? AND timeframe=?
        """
        params: list[object] = [symbol, timeframe_value]
        if start_ms is not None:
            sql += " AND ts >= ?"
            params.append(start_ms)
        if end_ms is not None:
            sql += " AND ts < ?"
            params.append(end_ms)
        if source is not None:
            sql += " AND source = ?"
            params.append(source)
        sql += " ORDER BY ts ASC"
        with self._db.transaction() as conn:
            return conn.execute(sql, params).fetchall()

    @staticmethod
    def _row_to_market_candle(
        row: sqlite3.Row, symbol: str, tf: Timeframe
    ) -> MarketCandle:
        volume = None if row["volume"] is None else float(row["volume"])
        return MarketCandle(
            symbol=symbol,
            timeframe=tf,
            timestamp=int(row["ts"]),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=volume,
            is_closed=bool(row["is_closed"]),
        )

    @staticmethod
    @staticmethod
    def _pick_dataset_row(
        conn: sqlite3.Connection,
        symbol: str,
        timeframe_value: str,
        source: str | None,
    ) -> sqlite3.Row | None:
        if source is not None:
            row = conn.execute(
                "SELECT * FROM datasets WHERE symbol=? AND timeframe=? AND source=?",
                (symbol, timeframe_value, source),
            ).fetchone()
            return cast("sqlite3.Row | None", row)
        newest = conn.execute(
            """
            SELECT * FROM datasets
            WHERE symbol=? AND timeframe=?
            ORDER BY updated_at_ms DESC, source ASC
            LIMIT 1
            """,
            (symbol, timeframe_value),
        ).fetchone()
        return cast("sqlite3.Row | None", newest)

    @staticmethod
    def _summary_from_row(row: sqlite3.Row) -> DatasetSummary:
        return DatasetSummary(
            symbol=str(row["symbol"]),
            timeframe=str(row["timeframe"]),
            source=str(row["source"]),
            first_timestamp_ms=None if row["first_ts"] is None else int(row["first_ts"]),
            last_timestamp_ms=None if row["last_ts"] is None else int(row["last_ts"]),
            candle_count=int(row["candle_count"]),
            quality_status=QualityStatus(str(row["quality_status"])),
            ingested_at_ms=int(row["ingested_at_ms"]),
            updated_at_ms=int(row["updated_at_ms"]),
        )

    # ==================================================================
    # TradeRepository
    # ==================================================================

    def record_trade(self, trade: StoredTrade, *, now_ms: int | None = None) -> StoredTrade:
        stamp = now_ms if now_ms is not None else self._clock_ms()
        stamped = (
            trade
            if trade.created_at_ms and trade.updated_at_ms
            else dataclasses.replace(trade, created_at_ms=stamp, updated_at_ms=stamp)
        )
        try:
            with self._db.transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO trades (
                        trade_id, execution_ref, symbol, timeframe, direction,
                        quantity, entry_price, exit_price, opened_at_ms, closed_at_ms,
                        status, realized_pnl, fees, slippage, risk_amount, realized_r,
                        result, strategy_id, config_hash, context_json,
                        created_at_ms, updated_at_ms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        stamped.trade_id,
                        stamped.execution_ref,
                        stamped.symbol,
                        stamped.timeframe,
                        stamped.direction.value,
                        stamped.quantity,
                        stamped.entry_price,
                        stamped.exit_price,
                        stamped.opened_at_ms,
                        stamped.closed_at_ms,
                        stamped.status.value,
                        stamped.realized_pnl,
                        stamped.fees,
                        stamped.slippage,
                        stamped.risk_amount,
                        stamped.realized_r,
                        stamped.result.value if stamped.result is not None else None,
                        stamped.strategy_id,
                        stamped.config_hash,
                        stamped.context.to_json() if stamped.context is not None else None,
                        stamped.created_at_ms,
                        stamped.updated_at_ms,
                    ),
                )
        except PersistenceError as exc:
            if exc.code is PersistenceErrorCode.INTEGRITY_ERROR:
                raise PersistenceError(
                    PersistenceErrorCode.INTEGRITY_ERROR,
                    f"trade {stamped.trade_id!r} already exists",
                    metadata={"trade_id": stamped.trade_id},
                ) from exc
            raise
        return stamped

    def get_trade(self, trade_id: str) -> StoredTrade | None:
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM trades WHERE trade_id=?", (trade_id,)
            ).fetchone()
        return self._trade_from_row(row) if row is not None else None

    def close_trade(
        self, trade_id: str, update: TradeUpdate, *, now_ms: int | None = None
    ) -> StoredTrade:
        stamp = now_ms if now_ms is not None else self._clock_ms()
        existing = self.get_trade(trade_id)
        if existing is None:
            raise PersistenceError(
                PersistenceErrorCode.REQUEST_INVALID,
                f"unknown trade {trade_id!r}",
                metadata={"trade_id": trade_id},
            )
        if existing.status is not TradeStatus.OPEN:
            raise PersistenceError(
                PersistenceErrorCode.TRADE_INVALID,
                f"trade {trade_id!r} is already closed",
                metadata={"trade_id": trade_id},
            )
        closed = StoredTrade(
            trade_id=existing.trade_id,
            symbol=existing.symbol,
            direction=existing.direction,
            quantity=existing.quantity,
            entry_price=existing.entry_price,
            opened_at_ms=existing.opened_at_ms,
            status=TradeStatus.CLOSED,
            execution_ref=existing.execution_ref,
            timeframe=existing.timeframe,
            exit_price=update.exit_price,
            closed_at_ms=update.closed_at_ms,
            realized_pnl=update.realized_pnl,
            fees=update.fees,
            slippage=update.slippage,
            risk_amount=existing.risk_amount if update.risk_amount is None else update.risk_amount,
            strategy_id=existing.strategy_id,
            config_hash=existing.config_hash,
            context=existing.context,
            created_at_ms=existing.created_at_ms,
            updated_at_ms=stamp,
        )
        with self._db.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE trades SET
                    exit_price=?, closed_at_ms=?, status='closed',
                    realized_pnl=?, fees=?, slippage=?, risk_amount=?, realized_r=?,
                    result=?, updated_at_ms=?
                WHERE trade_id=? AND status='open'
                """,
                (
                    closed.exit_price,
                    closed.closed_at_ms,
                    closed.realized_pnl,
                    closed.fees,
                    closed.slippage,
                    closed.risk_amount,
                    closed.realized_r,
                    closed.result.value if closed.result is not None else None,
                    stamp,
                    trade_id,
                ),
            )
            if cursor.rowcount != 1:
                raise PersistenceError(
                    PersistenceErrorCode.TRANSACTION_FAILED,
                    f"trade {trade_id!r} was modified concurrently",
                    metadata={"trade_id": trade_id},
                )
        return closed

    def list_trades(
        self,
        *,
        symbol: str | None = None,
        status: TradeStatus | None = None,
        result: TradeResult | None = None,
        strategy_id: str | None = None,
        closed_from_ms: int | None = None,
        closed_to_ms: int | None = None,
    ) -> tuple[StoredTrade, ...]:
        sql = "SELECT * FROM trades WHERE 1=1"
        params: list[object] = []
        if symbol is not None:
            sql += " AND symbol=?"
            params.append(symbol)
        if status is not None:
            sql += " AND status=?"
            params.append(status.value)
        if result is not None:
            sql += " AND result=?"
            params.append(result.value)
        if strategy_id is not None:
            sql += " AND strategy_id=?"
            params.append(strategy_id)
        if closed_from_ms is not None:
            sql += " AND closed_at_ms >= ?"
            params.append(closed_from_ms)
        if closed_to_ms is not None:
            sql += " AND closed_at_ms < ?"
            params.append(closed_to_ms)
        sql += " ORDER BY (closed_at_ms IS NULL), closed_at_ms, trade_id"
        with self._db.transaction() as conn:
            rows = conn.execute(sql, params).fetchall()
        return tuple(self._trade_from_row(row) for row in rows)

    # ----- trade internals -----

    @staticmethod
    def _trade_from_row(row: sqlite3.Row) -> StoredTrade:
        context_raw = row["context_json"]
        context = TradeContext.from_json(str(context_raw)) if context_raw is not None else None
        return StoredTrade(
            trade_id=str(row["trade_id"]),
            execution_ref=row["execution_ref"],
            symbol=str(row["symbol"]),
            timeframe=row["timeframe"],
            direction=PositionDirection(str(row["direction"])),
            quantity=float(row["quantity"]),
            entry_price=float(row["entry_price"]),
            exit_price=None if row["exit_price"] is None else float(row["exit_price"]),
            opened_at_ms=int(row["opened_at_ms"]),
            closed_at_ms=None if row["closed_at_ms"] is None else int(row["closed_at_ms"]),
            status=TradeStatus(str(row["status"])),
            realized_pnl=None if row["realized_pnl"] is None else float(row["realized_pnl"]),
            fees=None if row["fees"] is None else float(row["fees"]),
            slippage=None if row["slippage"] is None else float(row["slippage"]),
            risk_amount=None if row["risk_amount"] is None else float(row["risk_amount"]),
            realized_r=None if row["realized_r"] is None else float(row["realized_r"]),
            result=None if row["result"] is None else TradeResult(str(row["result"])),
            strategy_id=row["strategy_id"],
            config_hash=row["config_hash"],
            context=context,
            created_at_ms=int(row["created_at_ms"]),
            updated_at_ms=int(row["updated_at_ms"]),
        )


    # ==================================================================
    # BacktestRunRepository
    # ==================================================================

    def save_run(self, record: BacktestRunRecord) -> None:
        try:
            with self._db.transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO backtest_runs (
                        run_id, config_hash, symbol, timeframe,
                        period_start_ms, period_end_ms, initial_capital,
                        final_equity, peak_equity, max_drawdown, total_trades,
                        stats_json, config_json, engine_version, created_at_ms,
                        owner_user_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.run_id,
                        record.config_hash,
                        record.symbol,
                        record.timeframe,
                        record.period_start_ms,
                        record.period_end_ms,
                        record.initial_capital,
                        record.final_equity,
                        record.peak_equity,
                        record.max_drawdown,
                        record.total_trades,
                        record.stats_json,
                        record.config_json,
                        record.engine_version,
                        record.created_at_ms,
                        record.owner_user_id,
                    ),
                )
        except PersistenceError as exc:
            if exc.code is PersistenceErrorCode.INTEGRITY_ERROR:
                raise PersistenceError(
                    PersistenceErrorCode.INTEGRITY_ERROR,
                    f"backtest run {record.run_id!r} already exists",
                    metadata={"run_id": record.run_id},
                ) from exc
            raise

    def get_run(self, run_id: str) -> BacktestRunRecord | None:
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM backtest_runs WHERE run_id=?", (run_id,)
            ).fetchone()
        return self._run_from_row(row) if row is not None else None

    def list_runs(
        self,
        *,
        symbol: str | None = None,
        config_hash: str | None = None,
        owner_user_id: str | None = None,
    ) -> tuple[BacktestRunRecord, ...]:
        sql = "SELECT * FROM backtest_runs WHERE 1=1"
        params: list[object] = []
        if owner_user_id is not None:
            sql += " AND owner_user_id=?"
            params.append(owner_user_id)
        if symbol is not None:
            sql += " AND symbol=?"
            params.append(symbol)
        if config_hash is not None:
            sql += " AND config_hash=?"
            params.append(config_hash)
        sql += " ORDER BY created_at_ms DESC, run_id ASC"
        with self._db.transaction() as conn:
            rows = conn.execute(sql, params).fetchall()
        return tuple(self._run_from_row(row) for row in rows)

    @staticmethod
    def _run_from_row(row: sqlite3.Row) -> BacktestRunRecord:
        return BacktestRunRecord(
            run_id=str(row["run_id"]),
            config_hash=str(row["config_hash"]),
            symbol=str(row["symbol"]),
            timeframe=str(row["timeframe"]),
            period_start_ms=int(row["period_start_ms"]),
            period_end_ms=int(row["period_end_ms"]),
            initial_capital=float(row["initial_capital"]),
            final_equity=float(row["final_equity"]),
            peak_equity=float(row["peak_equity"]),
            max_drawdown=float(row["max_drawdown"]),
            total_trades=int(row["total_trades"]),
            stats_json=str(row["stats_json"]),
            config_json=str(row["config_json"]),
            engine_version=str(row["engine_version"]),
            created_at_ms=int(row["created_at_ms"]),
            owner_user_id=row["owner_user_id"],
        )
