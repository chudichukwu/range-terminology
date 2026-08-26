"""FastAPI application factory.

Wires middleware (request IDs), error handlers (uniform envelope), routers
and the application-service container. The API layer holds zero business
logic: every route validates input, delegates to :mod:`app_layer` and maps
application errors onto HTTP.

Execution-mode posture for Phase 9: the system is PAPER/READ-ONLY. There is
deliberately NO endpoint that can reach an exchange order path; when live
trading arrives it must pass Authentication -> Authorization -> ExecutionMode
-> RiskEngine -> ExecutionEngine, never HTTP -> Exchange.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.dependencies import Container, build_container
from api.errors import (
    app_error_handler,
    error_envelope,
    unhandled_error_handler,
    validation_error_handler,
)
from api.middleware import RequestIdMiddleware, request_id_of
from api.routers import (
    admin as admin_router_module,
)
from api.routers import (
    analysis as analysis_router,
)
from api.routers import (
    auth as auth_router,
)
from api.routers import (
    backtests as backtests_router,
)
from api.routers import (
    exchanges as exchanges_router,
)
from api.routers import (
    markets as markets_router,
)
from api.routers import (
    strategies as strategies_router,
)
from api.routers import (
    trades as trades_router,
)
from api.routers import (
    watchlists as watchlists_router,
)
from exchange.credentials import CredentialStore
from market_data.service import MarketDataService


def create_app(
    db_path: str,
    *,
    market_data: MarketDataService | None = None,
    credential_store: CredentialStore | None = None,
) -> FastAPI:
    """Build the API application over ``db_path``."""

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        yield
        container: Container | None = getattr(
            application.state, "container", None
        )
        if container is not None:
            container.store.close()

    application = FastAPI(
        title="Range Trading Terminal API",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(RequestIdMiddleware)

    container = build_container(
        db_path,
        market_data=market_data,
        credential_store=credential_store,
    )
    application.state.container = container

    from exchange.errors import ExchangeError
    from market_data.errors import MarketDataError

    def provider_error_handler(request: Request, exc: Exception) -> JSONResponse:
        message = (
            exc.message
            if isinstance(exc, (ExchangeError, MarketDataError))
            else "provider request failed"
        )
        return JSONResponse(
            status_code=502,
            content=error_envelope(
                "provider_error", message, request_id_of(request)
            ),
        )

    application.add_exception_handler(ExchangeError, provider_error_handler)
    application.add_exception_handler(MarketDataError, provider_error_handler)
    application.add_exception_handler(Exception, unhandled_error_handler)
    from fastapi.exceptions import RequestValidationError

    application.add_exception_handler(RequestValidationError, validation_error_handler)
    from app_layer.errors import AppError

    application.add_exception_handler(AppError, app_error_handler)

    application.include_router(auth_router.router)
    application.include_router(watchlists_router.router)
    application.include_router(strategies_router.router)
    application.include_router(markets_router.router)
    application.include_router(backtests_router.router)
    application.include_router(trades_router.router)
    application.include_router(exchanges_router.router)
    application.include_router(admin_router_module.router)
    application.include_router(analysis_router.router)

    @application.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application
