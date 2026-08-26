"""Application-layer persistence ports.

These ABCs extend the Phase 7 repository surface with the resources the
application needs (users, sessions, watchlists, strategies, exchange
connections, audit). Implementations live behind
:mod:`persistence.adapters.sqlite` — services never touch SQL.
"""

from abc import ABC, abstractmethod

from app_layer.models import (
    AuditEvent,
    ExchangeConnection,
    Session,
    StrategyConfig,
    User,
    Watchlist,
    WatchlistItem,
)
from persistence.base import (
    BacktestRunRepository,
    CandleRepository,
    TradeRepository,
)


class UserRepository(ABC):
    @abstractmethod
    def create_user(self, user: User, password_hash: str) -> User:
        """Insert a user; duplicate email raises IntegrityError-mapped error."""

    @abstractmethod
    def get_user(self, user_id: str) -> User | None: ...

    @abstractmethod
    def get_user_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    def get_password_hash(self, user_id: str) -> str | None: ...

    @abstractmethod
    def list_users(self) -> tuple[User, ...]: ...

    @abstractmethod
    def update_user(self, user: User) -> User:
        """Persist role/active/last-login changes on an existing user."""


class SessionRepository(ABC):
    @abstractmethod
    def create_session(self, session: Session) -> None: ...

    @abstractmethod
    def get_session_by_digest(self, token_digest: str) -> Session | None: ...

    @abstractmethod
    def revoke_session(self, session_id: str, revoked_at_ms: int) -> None: ...

    @abstractmethod
    def revoke_sessions_for_user(self, user_id: str, revoked_at_ms: int) -> int:
        """Revoke every active session of a user; returns count revoked."""

    @abstractmethod
    def delete_session(self, session_id: str) -> None: ...


class WatchlistRepository(ABC):
    @abstractmethod
    def create_watchlist(self, watchlist: Watchlist) -> Watchlist: ...

    @abstractmethod
    def get_watchlist(self, watchlist_id: str) -> Watchlist | None: ...

    @abstractmethod
    def list_watchlists(self, owner_user_id: str) -> tuple[Watchlist, ...]: ...

    @abstractmethod
    def rename_watchlist(
        self, watchlist_id: str, name: str, updated_at_ms: int
    ) -> Watchlist | None: ...

    @abstractmethod
    def delete_watchlist(self, watchlist_id: str) -> None: ...

    @abstractmethod
    def add_item(self, item: WatchlistItem) -> WatchlistItem: ...

    @abstractmethod
    def get_item(self, item_id: str) -> WatchlistItem | None: ...

    @abstractmethod
    def list_items(self, watchlist_id: str) -> tuple[WatchlistItem, ...]: ...

    @abstractmethod
    def delete_item(self, item_id: str) -> None: ...


class StrategyConfigRepository(ABC):
    @abstractmethod
    def create_strategy(self, strategy: StrategyConfig) -> StrategyConfig: ...

    @abstractmethod
    def get_strategy(self, strategy_id: str) -> StrategyConfig | None: ...

    @abstractmethod
    def list_strategies(self, owner_user_id: str) -> tuple[StrategyConfig, ...]: ...

    @abstractmethod
    def update_strategy(self, strategy: StrategyConfig) -> StrategyConfig: ...


class ExchangeConnectionRepository(ABC):
    @abstractmethod
    def create_connection(self, connection: ExchangeConnection) -> ExchangeConnection: ...

    @abstractmethod
    def get_connection(self, connection_id: str) -> ExchangeConnection | None: ...

    @abstractmethod
    def list_connections(
        self, owner_user_id: str | None = None
    ) -> tuple[ExchangeConnection, ...]: ...

    @abstractmethod
    def delete_connection(self, connection_id: str) -> None: ...


class AuditLogRepository(ABC):
    @abstractmethod
    def append_audit_event(self, event: AuditEvent) -> AuditEvent: ...

    @abstractmethod
    def list_audit_events(
        self, *, limit: int = 100, actor_user_id: str | None = None
    ) -> tuple[AuditEvent, ...]:
        """Newest-first audit tail."""


class UserAccountStore(
    UserRepository, SessionRepository, AuditLogRepository
):
    """Structural view of a store carrying user + session + audit repos.

    Declared as an ABC intersection so services can accept the combined
    capability; concrete stores (e.g. ``SqliteAppStore``) satisfy it.
    """

    __slots__ = ()



class BacktestServiceStore(BacktestRunRepository, CandleRepository, TradeRepository):
    """Structural view of a store able to persist runs, candles and trades."""

    __slots__ = ()
