"""Repository ports: the only surface applications use for persistence.

Domain engines never import anything from this package; the application layer
depends on these ABCs, keeping SQLite (or any future store) an implementation
detail behind :mod:`persistence.adapters`.
"""
from abc import ABC, abstractmethod

from market_data.models import CandleDataset, Timeframe
from persistence.models import (
    BacktestRunRecord,
    DatasetSummary,
    IngestionResult,
    StoredTrade,
    TradeResult,
    TradeStatus,
    TradeUpdate,
)


class CandleRepository(ABC):
    """Idempotent storage and chronological retrieval of validated candles."""

    @abstractmethod
    def ingest_dataset(self, dataset: CandleDataset, *, source: str) -> IngestionResult:
        """Ingest one validated Phase 6 dataset idempotently.

        The same logical candle (symbol + timeframe + timestamp + source) is
        stored exactly once; re-ingestion refreshes changed facts and counts
        unchanged rows instead of duplicating them.
        """

    @abstractmethod
    def query_candles(
        self,
        symbol: str,
        timeframe: Timeframe | str,
        *,
        start_ms: int | None = None,
        end_ms: int | None = None,
        source: str | None = None,
    ) -> CandleDataset:
        """Chronological candle slice as a pipeline-compatible dataset."""

    @abstractmethod
    def load_dataset(
        self,
        symbol: str,
        timeframe: Timeframe | str,
        *,
        source: str | None = None,
    ) -> CandleDataset | None:
        """Full stored series for a symbol/timeframe(/source), with the
        quality report captured at ingestion time; ``None`` when absent."""

    @abstractmethod
    def dataset_summary(
        self, symbol: str, timeframe: Timeframe | str, *, source: str | None = None
    ) -> DatasetSummary | None:
        """Stored window metadata, preferring the newest source when omitted."""

    @abstractmethod
    def list_dataset_summaries(self) -> tuple[DatasetSummary, ...]:
        """All known dataset windows."""


class TradeRepository(ABC):
    """Fact-level storage for actual completed/open trades."""

    @abstractmethod
    def record_trade(self, trade: StoredTrade, *, now_ms: int | None = None) -> StoredTrade:
        """Persist a new trade; duplicate ``trade_id`` is rejected loudly."""

    @abstractmethod
    def get_trade(self, trade_id: str) -> StoredTrade | None:
        """Fetch one trade by id."""

    @abstractmethod
    def close_trade(
        self, trade_id: str, update: TradeUpdate, *, now_ms: int | None = None
    ) -> StoredTrade:
        """Close an open trade with authoritative exit facts."""

    @abstractmethod
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
        """Filtered trades ordered by close time then id."""


class BacktestRunRepository(ABC):
    """Persistence for completed backtest runs (identity + headline facts)."""

    @abstractmethod
    def save_run(self, record: BacktestRunRecord) -> None:
        """Store one run; the same ``run_id`` is rejected loudly."""

    @abstractmethod
    def get_run(self, run_id: str) -> BacktestRunRecord | None:
        """Fetch one run by id."""

    @abstractmethod
    def list_runs(
        self,
        *,
        symbol: str | None = None,
        config_hash: str | None = None,
    ) -> tuple[BacktestRunRecord, ...]:
        """Runs newest-first, optionally filtered."""
