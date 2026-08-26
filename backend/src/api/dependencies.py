"""FastAPI dependency wiring: service graph + authenticated identity.

The application object graph is built ONCE per app via ``build_container``
and stored on ``app.state``; dependencies pull it from the request. The
authenticated user ALWAYS comes from the session token — never from any
client-supplied user id.
"""

from dataclasses import dataclass
from typing import Annotated, cast

from fastapi import Depends, Request

from app_layer.errors import ForbiddenError, UnauthenticatedError
from app_layer.models import Role, User
from app_layer.ports import BacktestServiceStore, UserAccountStore
from app_layer.services import (
    AuditService,
    BacktestService,
    ExchangeConnectionService,
    MarketDataFacade,
    StrategyConfigService,
    UserService,
    WatchlistService,
)
from backtesting.runner import BacktestRunner
from exchange.credentials import CredentialStore, InMemoryCredentialStore
from market_data.base import MarketDataPort
from market_data.models import Timeframe
from market_data.service import MarketDataService
from persistence.adapters.sqlite.app_repositories import SqliteAppStore


@dataclass(frozen=True)
class Container:
    """Application service graph shared by all requests."""

    store: SqliteAppStore
    users: UserService
    watchlists: WatchlistService
    strategies: StrategyConfigService
    exchanges: ExchangeConnectionService
    markets: MarketDataFacade
    backtests: BacktestService
    audit: AuditService
    credentials: CredentialStore


def build_container(
    db_path: str,
    *,
    market_data: MarketDataService | None = None,
    credential_store: CredentialStore | None = None,
    runner: BacktestRunner | None = None,
) -> Container:
    """Compose the application services over one SQLite-backed store."""
    store = SqliteAppStore(db_path)
    credentials = (
        credential_store if credential_store is not None else InMemoryCredentialStore()
    )
    audit = AuditService(store)
    account_store = cast(UserAccountStore, store)
    research_store = cast(BacktestServiceStore, store)
    users = UserService(account_store, audit)
    watchlists = WatchlistService(store)
    strategies = StrategyConfigService(store)
    exchanges = ExchangeConnectionService(store, credentials, audit)
    facade = MarketDataFacade(
        market_data if market_data is not None else MarketDataService(NullMarketDataProvider())
    )
    backtests = BacktestService(
        runner,
        candle_repository=research_store,
        run_repository=research_store,
    )
    return Container(
        store=store,
        users=users,
        watchlists=watchlists,
        strategies=strategies,
        exchanges=exchanges,
        markets=facade,
        backtests=backtests,
        audit=audit,
        credentials=credentials,
    )


def get_container(request: Request) -> Container:
    container: Container | None = getattr(request.app.state, "container", None)
    if container is None:  # pragma: no cover - app factory always sets it
        raise RuntimeError("application container not initialized")
    return container


def _resolve_user(request: Request) -> User:
    """Authenticate via the Authorization bearer token (server-side session)."""
    container = get_container(request)
    authorization = request.headers.get("Authorization", "")
    token = (
        authorization[7:].strip()
        if authorization.lower().startswith("bearer ")
        else ""
    )
    if not token:
        raise UnauthenticatedError()
    return container.users.resolve_session(token)


CurrentUser = Annotated[User, Depends(_resolve_user)]
ContainerDep = Annotated[Container, Depends(get_container)]


def require_owner(user: CurrentUser) -> User:
    """Server-side OWNER gate; route naming is NOT a security mechanism."""
    if user.role is not Role.OWNER:
        raise ForbiddenError("owner privileges required")
    return user


OwnerRequired = Annotated[User, Depends(require_owner)]


class NullMarketDataProvider(MarketDataPort):
    """Placeholder provider so the API boots without configured venues.

    Real deployments inject a :class:`MarketDataService` built on an
    ``ExchangeMarketDataProvider``; without one, market endpoints answer with
    normalized provider errors rather than crashing.
    """

    venue_id = "unconfigured"

    def get_ticker(self, symbol: str):  # type: ignore[no-untyped-def]
        from exchange.errors import ExchangeError, ExchangeErrorCode

        raise ExchangeError(
            ExchangeErrorCode.MARKET_UNAVAILABLE,
            "no market data provider configured",
            metadata={"symbol": symbol},
        )

    def fetch_candles(self, symbol, timeframe, *, limit=200, since_ms=None):  # type: ignore[no-untyped-def]
        from exchange.errors import ExchangeError, ExchangeErrorCode

        raise ExchangeError(
            ExchangeErrorCode.MARKET_UNAVAILABLE,
            "no market data provider configured",
            metadata={"symbol": symbol},
        )

    def supported_timeframes(self) -> frozenset[Timeframe]:
        return frozenset()
