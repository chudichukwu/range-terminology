"""Request/correlation-ID middleware.

Every request receives an ID (honoring an inbound ``X-Request-Id``), stored on
``request.state`` for dependencies/handlers and echoed back in the response
header. Error handlers embed it in the public error envelope so frontend
reports can be traced end-to-end.
"""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-Id"


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER, "").strip()
        request_id = incoming[:64] if incoming else uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def request_id_of(request: Request) -> str:
    """The correlation id attached to ``request`` (safe fallback)."""
    return str(getattr(request.state, "request_id", "unknown"))
