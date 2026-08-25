"""Exchange-independent error types for the exchange layer.

Raw venue exceptions (including CCXT's hierarchy) must never cross the port
boundary; adapters translate them into :class:`ExchangeError` carrying a
normalized :class:`ExchangeErrorCode` plus diagnostic metadata. Diagnostic
payloads are expected to be pre-sanitized by adapters (no credentials).
"""

from enum import Enum


class ExchangeErrorCode(Enum):
    """Normalized failure categories across all venue kinds."""

    AUTHENTICATION_FAILED = "authentication_failed"
    INVALID_ORDER = "invalid_order"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    RATE_LIMITED = "rate_limited"
    MARKET_UNAVAILABLE = "market_unavailable"
    ORDER_NOT_FOUND = "order_not_found"
    NETWORK_ERROR = "network_error"
    EXCHANGE_UNAVAILABLE = "exchange_unavailable"
    UNSUPPORTED_OPERATION = "unsupported_operation"
    UNKNOWN = "unknown"


class ExchangeError(Exception):
    """Venue-agnostic exchange failure.

    Attributes:
        code: Normalized failure category.
        message: Human-readable, already-sanitized description.
        venue_error_type: Original exception class name (string only — never
            the exception object itself), preserved for diagnostics.
        metadata: Extra sanitized diagnostics (venue id, symbol, ...).
    """

    def __init__(
        self,
        code: ExchangeErrorCode,
        message: str,
        *,
        venue_error_type: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.venue_error_type = venue_error_type
        self.metadata: dict[str, object] = dict(metadata or {})
        super().__init__(self._format())

    def _format(self) -> str:
        parts = [f"[{self.code.value}] {self.message}"]
        if self.venue_error_type is not None:
            parts.append(f"(venue_error_type={self.venue_error_type})")
        return " ".join(parts)


class UnsupportedOperationError(ExchangeError):
    """Raised when a venue lacks a capability the caller requested."""

    def __init__(self, capability: str, message: str | None = None) -> None:
        text = message or f"Venue does not support capability {capability!r}"
        super().__init__(
            ExchangeErrorCode.UNSUPPORTED_OPERATION,
            text,
            metadata={"capability": capability},
        )
