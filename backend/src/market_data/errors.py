"""Market-data-layer error types.

Provider exceptions (already normalized :class:`exchange.errors.ExchangeError`
values) never cross this boundary raw: the service wraps failures into
:class:`MarketDataError` carrying a normalized code plus sanitized metadata.
Raw provider exception text is deliberately dropped for unexpected failures so
no credential material can leak through error paths.
"""

from enum import Enum


class MarketDataErrorCode(Enum):
    """Normalized failure categories for market data requests."""

    REQUEST_INVALID = "request_invalid"
    SYMBOL_INVALID = "symbol_invalid"
    TIMEFRAME_UNSUPPORTED = "timeframe_unsupported"
    NORMALIZATION_FAILED = "normalization_failed"
    PROVIDER_ERROR = "provider_error"
    NO_DATA = "no_data"


class MarketDataError(Exception):
    """Provider-independent market data failure.

    Attributes:
        code: Normalized failure category.
        message: Human-readable description; safe for logs.
        metadata: Extra diagnostics (symbol, timeframe, ...). Never contains
            credentials or raw provider payloads.
    """

    def __init__(
        self,
        code: MarketDataErrorCode,
        message: str,
        *,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.metadata: dict[str, object] = dict(metadata or {})
        super().__init__(f"[{self.code.value}] {self.message}")
