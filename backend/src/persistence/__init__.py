"""persistence: durable, trustworthy data foundation for the terminal.

Two fact categories live here: validated historical candles (from Phase 6
datasets) and actual trade history (outcomes of Phase 5 executions). The
layer records authoritative facts only; win rate / expectancy / profit factor
etc. are DERIVED in :mod:`persistence.statistics` with explicit definitions.

SQLite sits behind the repository ports in :mod:`persistence.base`; domain
engines never import anything from this package.
"""

from persistence.adapters.sqlite.database import SqliteDatabase, utc_clock_ms
from persistence.adapters.sqlite.repositories import SqlitePersistence
from persistence.base import CandleRepository, TradeRepository
from persistence.errors import PersistenceError, PersistenceErrorCode
from persistence.execution_link import trade_from_execution
from persistence.migrations import MIGRATIONS, SCHEMA_VERSION, Migration
from persistence.models import (
    DEFAULT_BREAKEVEN_EPSILON,
    DatasetSummary,
    IngestionResult,
    QualityStatus,
    StoredTrade,
    TradeContext,
    TradeResult,
    TradeStatus,
    TradeUpdate,
    classify_result,
    quality_status_of,
)
from persistence.statistics import TradeStatistics, compute_trade_statistics

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_BREAKEVEN_EPSILON",
    "CandleRepository",
    "DatasetSummary",
    "IngestionResult",
    "MIGRATIONS",
    "Migration",
    "PersistenceError",
    "PersistenceErrorCode",
    "QualityStatus",
    "SCHEMA_VERSION",
    "SqliteDatabase",
    "SqlitePersistence",
    "StoredTrade",
    "TradeContext",
    "TradeRepository",
    "TradeResult",
    "TradeStatistics",
    "TradeStatus",
    "TradeUpdate",
    "TradeStatistics",
    "__version__",
    "classify_result",
    "compute_trade_statistics",
    "quality_status_of",
    "trade_from_execution",
    "utc_clock_ms",
]
