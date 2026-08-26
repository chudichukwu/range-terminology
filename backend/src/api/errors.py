"""Consistent API error contract.

Public envelope (internal exception types never cross it):

    {"error": {"code": "...", "message": "...", "request_id": "..."}}

Stack traces and provider messages are never returned; unexpected failures
collapse into a generic 500 with a correlation id.
"""

from starlette.requests import Request
from starlette.responses import JSONResponse

from api.middleware import request_id_of
from app_layer.errors import AppError, AppErrorCode

_STATUS_BY_CODE = {
    AppErrorCode.VALIDATION: 400,
    AppErrorCode.UNAUTHENTICATED: 401,
    AppErrorCode.FORBIDDEN: 403,
    AppErrorCode.NOT_FOUND: 404,
    AppErrorCode.CONFLICT: 409,
}


def error_envelope(code: str, message: str, request_id: str) -> dict[str, object]:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
        }
    }


async def app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    status = _STATUS_BY_CODE.get(exc.code, 400)
    return JSONResponse(
        status_code=status,
        content=error_envelope(exc.code.value, exc.message, request_id_of(request)),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Deliberately opaque: no stack traces, no provider text.
    return JSONResponse(
        status_code=500,
        content=error_envelope(
            "internal_error", "unexpected server error", request_id_of(request)
        ),
    )


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """FastAPI/pydantic request validation -> uniform envelope."""
    from fastapi.exceptions import RequestValidationError

    assert isinstance(exc, RequestValidationError)
    first = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(part) for part in first.get("loc", []) if part != "body")
    message = f"invalid request: {location or 'body'}"
    return JSONResponse(
        status_code=400,
        content=error_envelope("validation_error", message, request_id_of(request)),
    )


__all__ = [
    "app_error_handler",
    "error_envelope",
    "unhandled_error_handler",
    "validation_error_handler",
]
