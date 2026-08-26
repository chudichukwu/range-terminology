"""SQLite implementation of the application-layer repository ports.

Extends (never modifies) :class:`~persistence.adapters.sqlite.repositories.SqlitePersistence`
so one store object serves domain AND application repositories.
"""

import json
from collections.abc import Callable
from typing import cast

from app_layer.models import (
    AuditEvent,
    ExchangeConnection,
    Role,
    Session,
    StrategyConfig,
    User,
    Watchlist,
    WatchlistItem,
)
from app_layer.ports import (
    AuditLogRepository,
    ExchangeConnectionRepository,
    SessionRepository,
    StrategyConfigRepository,
    UserRepository,
    WatchlistRepository,
)
from persistence.adapters.sqlite.database import utc_clock_ms
from persistence.adapters.sqlite.repositories import SqlitePersistence


class SqliteAppStore(
    SqlitePersistence,
    UserRepository,
    SessionRepository,
    WatchlistRepository,
    StrategyConfigRepository,
    ExchangeConnectionRepository,
    AuditLogRepository,
):
    """Full application store: Phase 7 repositories + application resources."""

    # ==================================================================
    # Users
    # ==================================================================

    def create_user(self, user: User, password_hash: str) -> User:
        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO users
                    (id, email, password_hash, role, active,
                     created_at_ms, updated_at_ms, last_login_at_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user.id, user.email.lower(), password_hash, user.role.value,
                    int(user.active), user.created_at_ms, user.updated_at_ms,
                    user.last_login_at_ms,
                ),
            )
        return user

    def get_user(self, user_id: str) -> User | None:
        with self._db.transaction() as conn:
            row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return self._user_from_row(row) if row is not None else None

    def get_user_by_email(self, email: str) -> User | None:
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE email=?", (email.strip().lower(),)
            ).fetchone()
        return self._user_from_row(row) if row is not None else None

    def get_password_hash(self, user_id: str) -> str | None:
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT password_hash FROM users WHERE id=?", (user_id,)
            ).fetchone()
        return str(row["password_hash"]) if row is not None else None

    def list_users(self) -> tuple[User, ...]:
        with self._db.transaction() as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY created_at_ms").fetchall()
        return tuple(u for u in (self._user_from_row(r) for r in rows) if u)

    def update_user(self, user: User) -> User:
        with self._db.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE users SET email=?, role=?, active=?, updated_at_ms=?,
                                 last_login_at_ms=?
                WHERE id=?
                """,
                (
                    user.email.lower(), user.role.value, int(user.active),
                    user.updated_at_ms, user.last_login_at_ms, user.id,
                ),
            )
            if cursor.rowcount != 1:
                from persistence.errors import PersistenceError, PersistenceErrorCode

                raise PersistenceError(
                    PersistenceErrorCode.REQUEST_INVALID,
                    f"unknown user {user.id!r}",
                )
        return user

    @staticmethod
    def _user_from_row(row: object) -> User | None:
        import sqlite3

        assert isinstance(row, sqlite3.Row)
        return User(
            id=str(row["id"]),
            email=str(row["email"]),
            role=Role(str(row["role"])),
            active=bool(row["active"]),
            created_at_ms=int(row["created_at_ms"]),
            updated_at_ms=int(row["updated_at_ms"]),
            last_login_at_ms=(
                None if row["last_login_at_ms"] is None else int(row["last_login_at_ms"])
            ),
        )

    # ==================================================================
    # Sessions
    # ==================================================================

    def create_session(self, session: Session) -> None:
        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO sessions
                    (id, user_id, token_digest, created_at_ms, expires_at_ms,
                     revoked_at_ms)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session.id, session.user_id, session.token_digest,
                    session.created_at_ms, session.expires_at_ms,
                    session.revoked_at_ms,
                ),
            )

    def get_session_by_digest(self, token_digest: str) -> Session | None:
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE token_digest=?", (token_digest,)
            ).fetchone()
        if row is None:
            return None
        import sqlite3

        assert isinstance(row, sqlite3.Row)
        return Session(
            id=str(row["id"]),
            user_id=str(row["user_id"]),
            token_digest=str(row["token_digest"]),
            created_at_ms=int(row["created_at_ms"]),
            expires_at_ms=int(row["expires_at_ms"]),
            revoked_at_ms=None if row["revoked_at_ms"] is None else int(row["revoked_at_ms"]),
        )

    def revoke_session(self, session_id: str, revoked_at_ms: int) -> None:
        with self._db.transaction() as conn:
            conn.execute(
                "UPDATE sessions SET revoked_at_ms=? WHERE id=?",
                (revoked_at_ms, session_id),
            )

    def revoke_sessions_for_user(self, user_id: str, revoked_at_ms: int) -> int:
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "UPDATE sessions SET revoked_at_ms=? "
                "WHERE user_id=? AND revoked_at_ms IS NULL",
                (revoked_at_ms, user_id),
            )
            return int(cursor.rowcount)

    def delete_session(self, session_id: str) -> None:
        with self._db.transaction() as conn:
            conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))

    # ==================================================================
    # Watchlists
    # ==================================================================

    def create_watchlist(self, watchlist: Watchlist) -> Watchlist:
        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO watchlists
                    (id, owner_user_id, name, created_at_ms, updated_at_ms)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    watchlist.id, watchlist.owner_user_id, watchlist.name,
                    watchlist.created_at_ms, watchlist.updated_at_ms,
                ),
            )
        return watchlist

    def get_watchlist(self, watchlist_id: str) -> Watchlist | None:
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM watchlists WHERE id=?", (watchlist_id,)
            ).fetchone()
        return self._watchlist_from_row(row) if row is not None else None

    def list_watchlists(self, owner_user_id: str) -> tuple[Watchlist, ...]:
        with self._db.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM watchlists WHERE owner_user_id=? ORDER BY name",
                (owner_user_id,),
            ).fetchall()
        return tuple(w for w in (self._watchlist_from_row(r) for r in rows) if w)

    def rename_watchlist(
        self, watchlist_id: str, name: str, updated_at_ms: int
    ) -> Watchlist | None:
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "UPDATE watchlists SET name=?, updated_at_ms=? WHERE id=?",
                (name, updated_at_ms, watchlist_id),
            )
            if cursor.rowcount != 1:
                return None
        return self.get_watchlist(watchlist_id)

    def delete_watchlist(self, watchlist_id: str) -> None:
        with self._db.transaction() as conn:
            conn.execute("DELETE FROM watchlists WHERE id=?", (watchlist_id,))

    def add_item(self, item: WatchlistItem) -> WatchlistItem:
        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO watchlist_items
                    (id, watchlist_id, symbol, venue_id, enabled, notes,
                     sort_order, created_at_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id, item.watchlist_id, item.symbol, item.venue_id,
                    int(item.enabled), item.notes, item.sort_order,
                    item.created_at_ms,
                ),
            )
        return item

    def get_item(self, item_id: str) -> WatchlistItem | None:
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM watchlist_items WHERE id=?", (item_id,)
            ).fetchone()
        return self._item_from_row(row) if row is not None else None

    def list_items(self, watchlist_id: str) -> tuple[WatchlistItem, ...]:
        with self._db.transaction() as conn:
            rows = conn.execute(
                """
                SELECT * FROM watchlist_items WHERE watchlist_id=?
                ORDER BY sort_order, created_at_ms
                """,
                (watchlist_id,),
            ).fetchall()
        return tuple(i for i in (self._item_from_row(r) for r in rows) if i)

    def delete_item(self, item_id: str) -> None:
        with self._db.transaction() as conn:
            conn.execute("DELETE FROM watchlist_items WHERE id=?", (item_id,))

    @staticmethod
    def _watchlist_from_row(row: object) -> Watchlist | None:
        import sqlite3

        assert isinstance(row, sqlite3.Row)
        return Watchlist(
            id=str(row["id"]),
            owner_user_id=str(row["owner_user_id"]),
            name=str(row["name"]),
            created_at_ms=int(row["created_at_ms"]),
            updated_at_ms=int(row["updated_at_ms"]),
        )

    @staticmethod
    def _item_from_row(row: object) -> WatchlistItem | None:
        import sqlite3

        assert isinstance(row, sqlite3.Row)
        return WatchlistItem(
            id=str(row["id"]),
            watchlist_id=str(row["watchlist_id"]),
            symbol=str(row["symbol"]),
            venue_id=str(row["venue_id"]),
            enabled=bool(row["enabled"]),
            notes=str(row["notes"]),
            sort_order=int(row["sort_order"]),
            created_at_ms=int(row["created_at_ms"]),
        )

    # ==================================================================
    # Strategy configurations
    # ==================================================================

    def create_strategy(self, strategy: StrategyConfig) -> StrategyConfig:
        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO strategy_configs
                    (id, owner_user_id, name, payload_json, schema_version,
                     active, created_at_ms, updated_at_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    strategy.id, strategy.owner_user_id, strategy.name,
                    strategy.payload_json, strategy.schema_version,
                    int(strategy.active), strategy.created_at_ms,
                    strategy.updated_at_ms,
                ),
            )
        return strategy

    def get_strategy(self, strategy_id: str) -> StrategyConfig | None:
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM strategy_configs WHERE id=?", (strategy_id,)
            ).fetchone()
        return self._strategy_from_row(row) if row is not None else None

    def list_strategies(self, owner_user_id: str) -> tuple[StrategyConfig, ...]:
        with self._db.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM strategy_configs WHERE owner_user_id=? ORDER BY name",
                (owner_user_id,),
            ).fetchall()
        return tuple(st for st in (self._strategy_from_row(r) for r in rows) if st)

    def update_strategy(self, strategy: StrategyConfig) -> StrategyConfig:
        with self._db.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE strategy_configs SET name=?, payload_json=?,
                    schema_version=?, active=?, updated_at_ms=?
                WHERE id=?
                """,
                (
                    strategy.name, strategy.payload_json, strategy.schema_version,
                    int(strategy.active), strategy.updated_at_ms, strategy.id,
                ),
            )
            if cursor.rowcount != 1:
                from persistence.errors import PersistenceError, PersistenceErrorCode

                raise PersistenceError(
                    PersistenceErrorCode.REQUEST_INVALID,
                    f"unknown strategy {strategy.id!r}",
                )
        return strategy

    @staticmethod
    def _strategy_from_row(row: object) -> StrategyConfig | None:
        import sqlite3

        assert isinstance(row, sqlite3.Row)
        return StrategyConfig(
            id=str(row["id"]),
            owner_user_id=str(row["owner_user_id"]),
            name=str(row["name"]),
            payload_json=str(row["payload_json"]),
            schema_version=str(row["schema_version"]),
            active=bool(row["active"]),
            created_at_ms=int(row["created_at_ms"]),
            updated_at_ms=int(row["updated_at_ms"]),
        )

    # ==================================================================
    # Exchange connections
    # ==================================================================

    def create_connection(self, connection: ExchangeConnection) -> ExchangeConnection:
        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO exchange_connections
                    (id, owner_user_id, venue_id, display_name, status,
                     credential_ref, sandbox, created_at_ms, updated_at_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    connection.id, connection.owner_user_id, connection.venue_id,
                    connection.display_name, connection.status,
                    connection.credential_ref, int(connection.sandbox),
                    connection.created_at_ms, connection.updated_at_ms,
                ),
            )
        return connection

    def get_connection(self, connection_id: str) -> ExchangeConnection | None:
        with self._db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM exchange_connections WHERE id=?", (connection_id,)
            ).fetchone()
        return self._connection_from_row(row) if row is not None else None

    def list_connections(
        self, owner_user_id: str | None = None
    ) -> tuple[ExchangeConnection, ...]:
        sql = "SELECT * FROM exchange_connections"
        params: list[object] = []
        if owner_user_id is not None:
            sql += " WHERE owner_user_id=?"
            params.append(owner_user_id)
        sql += " ORDER BY created_at_ms"
        with self._db.transaction() as conn:
            rows = conn.execute(sql, params).fetchall()
        return tuple(c for c in (self._connection_from_row(r) for r in rows) if c)

    def delete_connection(self, connection_id: str) -> None:
        with self._db.transaction() as conn:
            conn.execute("DELETE FROM exchange_connections WHERE id=?", (connection_id,))

    @staticmethod
    def _connection_from_row(row: object) -> ExchangeConnection | None:
        import sqlite3

        assert isinstance(row, sqlite3.Row)
        return ExchangeConnection(
            id=str(row["id"]),
            owner_user_id=str(row["owner_user_id"]),
            venue_id=str(row["venue_id"]),
            display_name=str(row["display_name"]),
            status=str(row["status"]),
            credential_ref=str(row["credential_ref"]),
            sandbox=bool(row["sandbox"]),
            created_at_ms=int(row["created_at_ms"]),
            updated_at_ms=int(row["updated_at_ms"]),
        )

    # ==================================================================
    # Audit log
    # ==================================================================

    def append_audit_event(self, event: AuditEvent) -> AuditEvent:
        with self._db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO audit_log
                    (id, actor_user_id, action, resource_type, resource_id,
                     timestamp_ms, outcome, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id, event.actor_user_id, event.action,
                    event.resource_type, event.resource_id, event.timestamp_ms,
                    event.outcome, json.dumps(event.metadata, sort_keys=True),
                ),
            )
        return event

    def list_audit_events(
        self, *, limit: int = 100, actor_user_id: str | None = None
    ) -> tuple[AuditEvent, ...]:
        sql = "SELECT * FROM audit_log"
        params: list[object] = []
        if actor_user_id is not None:
            sql += " WHERE actor_user_id=?"
            params.append(actor_user_id)
        sql += " ORDER BY timestamp_ms DESC LIMIT ?"
        params.append(limit)
        events: list[AuditEvent] = []
        with self._db.transaction() as conn:
            rows = conn.execute(sql, params).fetchall()
        for row in rows:
            metadata_raw = json.loads(str(row["metadata_json"]))
            events.append(
                AuditEvent(
                    id=str(row["id"]),
                    actor_user_id=row["actor_user_id"],
                    action=str(row["action"]),
                    resource_type=str(row["resource_type"]),
                    resource_id=row["resource_id"],
                    timestamp_ms=int(row["timestamp_ms"]),
                    outcome=str(row["outcome"]),
                    metadata=(
                        metadata_raw if isinstance(metadata_raw, dict) else {}
                    ),
                )
            )
        return tuple(events)


def build_app_store(
    path: str, *, clock_ms: Callable[[], int] | None = None
) -> SqliteAppStore:
    """Construct the full application store with a migrated database."""
    _ = cast(type, SqliteAppStore)  # explicit reference for clarity
    _ = utc_clock_ms  # noqa: F841 - documented default clock of the base class
    return SqliteAppStore(path, clock_ms=clock_ms)
