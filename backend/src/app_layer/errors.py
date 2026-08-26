"""Application-layer error types.

These are the vocabulary application services speak; the HTTP layer maps them
onto status codes. Internal exception types stay separate from public API
error schemas.
"""

from enum import Enum


class AppErrorCode(Enum):
    """Normalized application failure categories."""

    VALIDATION = "validation_error"
    UNAUTHENTICATED = "unauthenticated"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"


class AppError(Exception):
    """Application-level failure with a stable machine-readable code."""

    def __init__(
        self,
        code: AppErrorCode,
        message: str,
        *,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.metadata: dict[str, object] = dict(metadata or {})
        super().__init__(message)


class ValidationError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(AppErrorCode.VALIDATION, message)


class UnauthenticatedError(AppError):
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(AppErrorCode.UNAUTHENTICATED, message)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Not permitted") -> None:
        super().__init__(AppErrorCode.FORBIDDEN, message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(AppErrorCode.NOT_FOUND, message)


class ConflictError(AppError):
    def __init__(self, message: str = "Resource conflict") -> None:
        super().__init__(AppErrorCode.CONFLICT, message)
