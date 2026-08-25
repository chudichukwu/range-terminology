"""exchange: venue abstraction layer for the range-trading terminal.

The application depends only on :class:`exchange.base.ExchangePort` plus the
normalized models in :mod:`exchange.models`. Venue SDKs (CCXT today; DEX
SDKs/RPC/wallet signing later) live exclusively under
``exchange.adapters.*`` and are translated at that boundary.
"""

from exchange import errors
from exchange.base import ExchangePort
from exchange.capabilities import ALL_CAPABILITY_NAMES, ExchangeCapabilities
from exchange.constraints import MarketConstraints
from exchange.credentials import (
    CexCredentials,
    CredentialLookupError,
    CredentialStore,
    EncryptedFileCredentialStore,
    InMemoryCredentialStore,
    KeychainCredentialStore,
    dump_cex_credentials,
    load_cex_credentials,
    redact,
)
from exchange.errors import ExchangeError, ExchangeErrorCode, UnsupportedOperationError
from exchange.models import (
    Balance,
    Candle,
    Order,
    OrderBook,
    OrderBookLevel,
    OrderSide,
    OrderStatus,
    OrderSubmission,
    OrderType,
    Position,
    PositionDirection,
    SubmissionState,
    Ticker,
)

__version__ = "0.1.0"

__all__ = [
    "ALL_CAPABILITY_NAMES",
    "Balance",
    "Candle",
    "CexCredentials",
    "CredentialLookupError",
    "CredentialStore",
    "EncryptedFileCredentialStore",
    "ExchangeError",
    "ExchangeErrorCode",
    "ExchangeCapabilities",
    "ExchangePort",
    "InMemoryCredentialStore",
    "KeychainCredentialStore",
    "MarketConstraints",
    "Order",
    "OrderBook",
    "OrderBookLevel",
    "OrderSide",
    "OrderStatus",
    "OrderSubmission",
    "OrderType",
    "Position",
    "PositionDirection",
    "SubmissionState",
    "Ticker",
    "UnsupportedOperationError",
    "__version__",
    "dump_cex_credentials",
    "errors",
    "load_cex_credentials",
    "redact",
]
