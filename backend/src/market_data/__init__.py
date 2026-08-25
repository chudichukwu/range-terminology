"""market_data: provider-independent market data for the trading terminal.

Pipeline: provider adapter -> :class:`MarketDataService` -> validated
:class:`MarketCandle` datasets with explicit quality reports -> Range/Signal/
future consumers. CCXT stays behind the Phase 4 exchange layer; this package
speaks only project-normalized models.
"""

from market_data.adapters.ccxt.adapter import ExchangeMarketDataProvider
from market_data.base import MarketDataPort
from market_data.errors import MarketDataError, MarketDataErrorCode
from market_data.models import (
    CandleDataset,
    CandleSeries,
    DataQualityReport,
    HistoricalRequest,
    MarketCandle,
    QualityIssue,
    Ticker,
    Timeframe,
)
from market_data.service import MarketDataService
from market_data.validation import (
    ISSUE_DUPLICATE_TIMESTAMP,
    ISSUE_EMPTY_SERIES,
    ISSUE_MEMBER_MISMATCH,
    ISSUE_MISSING_INTERVAL,
    ISSUE_OUT_OF_ORDER_TIMESTAMP,
    ISSUE_UNCLOSED_CANDLE,
    SequenceValidation,
    validate_sequence,
)

__version__ = "0.1.0"

__all__ = [
    "ISSUE_DUPLICATE_TIMESTAMP",
    "ISSUE_EMPTY_SERIES",
    "ISSUE_MISSING_INTERVAL",
    "ISSUE_MEMBER_MISMATCH",
    "ISSUE_OUT_OF_ORDER_TIMESTAMP",
    "ISSUE_UNCLOSED_CANDLE",
    "CandleDataset",
    "CandleSeries",
    "DataQualityReport",
    "ExchangeMarketDataProvider",
    "HistoricalRequest",
    "MarketCandle",
    "MarketDataError",
    "MarketDataErrorCode",
    "MarketDataPort",
    "MarketDataService",
    "QualityIssue",
    "SequenceValidation",
    "Ticker",
    "Timeframe",
    "__version__",
    "validate_sequence",
]
