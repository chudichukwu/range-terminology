"""Persistence-layer error types.

SQLite failures never cross the repository boundary raw: implementations wrap
them into :class:`PersistenceError` with a normalized code. Error messages are
safe for logs — the database contains no secret material by design (Phase 4
credentials never enter persistence), and messages carry column/table context
only, never parameter values.
"""

from enum import Enum


class PersistenceErrorCode(Enum):
    """Normalized persistence failure categories."""

    SCHEMA_ERROR = "schema_error"
    INTEGRITY_ERROR = "integrity_error"
    TRADE_INVALID = "trade_invalid"
    REQUEST_INVALID = "request_invalid"
    TRANSACTION_FAILED = "transaction_failed"


class PersistenceError(Exception):
    """Provider-independent persistence failure.

    Attributes:
        code: Normalized failure category.
        message: Human-readable, log-safe description.
        metadata: Extra diagnostics (table names, counts). Never credentials.
    """

    def __init__(
        self,
        code: PersistenceErrorCode,
        message: str,
        *,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.metadata: dict[str, object] = dict(metadata or {})
        super().__init__(f"[{self.code.value}] {self.message}")
