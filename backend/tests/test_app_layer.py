"""Deterministic application-layer tests (no HTTP)."""

from collections.abc import Callable
from pathlib import Path

import pytest

from app_layer.errors import (
    AppErrorCode,
    ForbiddenError,
    NotFoundError,
    UnauthenticatedError,
)
from app_layer.models import Role, User
from app_layer.services import (
    AuditService,
    ExchangeConnectionService,
    StrategyConfigService,
    UserService,
    WatchlistService,
)
from exchange.credentials import InMemoryCredentialStore
from persistence.adapters.sqlite.app_repositories import SqliteAppStore

HOUR_MS = 3_600_000


class Clock:
    def __init__(self, now: int = 1_700_000_000_000) -> None:
        self.now = now

    def __call__(self) -> int:
        return self.now

    def advance(self, ms: int) -> None:
        self.now += ms


@pytest.fixture()
def store(tmp_path: Path) -> SqliteAppStore:
    clock = Clock()
    return SqliteAppStore(tmp_path / "app.db", clock_ms=clock)


@pytest.fixture()
def services(store: SqliteAppStore):
    audit = AuditService(store, clock_ms=Clock(), id_factory=_seq_ids())
    users = UserService(store, audit, clock_ms=Clock(), id_factory=_seq_ids())
    watchlists = WatchlistService(store, clock_ms=Clock(), id_factory=_seq_ids())
    strategies = StrategyConfigService(store, clock_ms=Clock(), id_factory=_seq_ids())
    credentials = InMemoryCredentialStore()
    exchanges = ExchangeConnectionService(
        store, credentials, audit, clock_ms=Clock(), id_factory=_seq_ids()
    )
    return {
        "store": store,
        "users": users,
        "watchlists": watchlists,
        "strategies": strategies,
        "exchanges": exchanges,
        "audit": audit,
        "credentials": credentials,
    }


def _seq_ids() -> "Callable[[], str]":
    counter = {"n": 0}

    def make_id() -> str:
        counter["n"] += 1
        return f"id-{counter['n']}"

    return make_id


def owner(services: dict) -> User:
    return services["users"].create_user("owner@example.com", "owner-pass-1")


def plain_user(services: dict, email: str = "user@example.com") -> User:
    owner_actor = owner(services) if len(services["store"].list_users()) == 0 else None
    if owner_actor is None:
        existing_owner = next(
            u for u in services["store"].list_users() if u.role is Role.OWNER
        )
        return services["users"].create_user(
            email, "user-pass-123", actor=existing_owner
        )
    return services["users"].create_user(email, "user-pass-123", actor=None or owner_actor)


class TestAuthentication:
    def test_first_user_bootstraps_as_owner(self, services: dict) -> None:
        first = services["users"].create_user("root@example.com", "root-pass-1")
        assert first.role is Role.OWNER and first.active

    def test_password_never_stored_plaintext(self, services: dict) -> None:
        services["users"].create_user("pw@example.com", "super-secret-9")
        stored_hash = services["store"].get_password_hash(
            services["store"].get_user_by_email("pw@example.com").id  # type: ignore[union-attr]
        )
        assert stored_hash is not None
        assert "super-secret-9" not in stored_hash
        assert stored_hash.startswith("scrypt$")

    def test_login_success_returns_token_and_resolves(self, services: dict) -> None:
        created = services["users"].create_user("login@example.com", "hunter2boots")
        user, token = services["users"].authenticate("login@example.com", "hunter2boots")
        assert user.id == created.id
        resolved = services["users"].resolve_session(token)
        assert resolved.id == created.id
        assert token not in (services["store"].get_password_hash(user.id) or "")

    def test_wrong_password_rejected(self, services: dict) -> None:
        services["users"].create_user("wrong@example.com", "correct-horse")
        with pytest.raises(UnauthenticatedError):
            services["users"].authenticate("wrong@example.com", "battery-staple")

    def test_unknown_email_rejected_indistinguishably(self, services: dict) -> None:
        with pytest.raises(UnauthenticatedError) as excinfo:
            services["users"].authenticate("ghost@example.com", "whatever123")
        assert excinfo.value.code is AppErrorCode.UNAUTHENTICATED

    def test_disabled_user_cannot_authenticate(self, services: dict) -> None:
        root = services["users"].create_user("root@example.com", "root-pass-1")
        target = services["users"].create_user(
            "victim@example.com", "victim-pass", actor=root
        )
        services["users"].set_user_active(root, target.id, active=False)
        with pytest.raises(UnauthenticatedError):
            services["users"].authenticate("victim@example.com", "victim-pass")

    def test_logout_invalidates_token(self, services: dict) -> None:
        services["users"].create_user("logout@example.com", "logout-pass")
        _user, token = services["users"].authenticate(
            "logout@example.com", "logout-pass"
        )
        services["users"].resolve_session(token)
        services["users"].logout(token)
        with pytest.raises(UnauthenticatedError):
            services["users"].resolve_session(token)


class TestAuthorization:
    def test_non_owner_cannot_create_users(self, services: dict) -> None:
        root = services["users"].create_user("root@example.com", "root-pass-1")
        normal = services["users"].create_user(
            "user@example.com", "user-pass-1", actor=root
        )
        with pytest.raises(ForbiddenError):
            services["users"].create_user(
                "new@example.com", "new-user-pass", actor=normal
            )

    def test_non_owner_cannot_list_users_or_administrate(self, services: dict) -> None:
        root = services["users"].create_user("root@example.com", "root-pass-1")
        normal = services["users"].create_user(
            "user@example.com", "user-pass-1", actor=root
        )
        with pytest.raises(ForbiddenError):
            services["users"].list_users(normal)
        with pytest.raises(ForbiddenError):
            services["users"].set_user_active(normal, root.id, active=False)
        with pytest.raises(ForbiddenError):
            services["users"].set_user_role(normal, root.id, Role.USER)

    def test_owner_can_manage_users_and_roles(self, services: dict) -> None:
        root = services["users"].create_user("root@example.com", "root-pass-1")
        promoted = services["users"].create_user(
            "promoted@example.com", "promoted-pass", actor=root
        )
        updated = services["users"].set_user_role(root, promoted.id, Role.OWNER)
        assert updated.role is Role.OWNER
        disabled = services["users"].set_user_active(root, promoted.id, active=False)
        assert disabled.active is False

    def test_session_revocation_is_immediate(self, services: dict) -> None:
        root = services["users"].create_user("root@example.com", "root-pass-1")
        victim = services["users"].create_user(
            "victim@example.com", "victim-pass", actor=root
        )
        _user, token = services["users"].authenticate("victim@example.com", "victim-pass")
        assert services["users"].resolve_session(token).id == victim.id
        services["users"].revoke_sessions(root, victim.id)
        with pytest.raises(UnauthenticatedError):
            services["users"].resolve_session(token)


class TestIsolation:
    def test_watchlists_are_invisible_across_users(self, services: dict) -> None:
        root = services["users"].create_user("root@example.com", "root-pass-1")
        alice = services["users"].create_user("a@example.com", "alice-pass", actor=root)
        bob = services["users"].create_user("b@example.com", "bob-passx", actor=root)
        created = services["watchlists"].create(alice, "Alice list")
        alice_lists = services["watchlists"].list(alice)
        bob_lists = services["watchlists"].list(bob)
        assert [w.id for w in alice_lists] == [created.id]
        assert bob_lists == ()
        with pytest.raises(NotFoundError):
            services["watchlists"].get(bob, created.id)

    def test_strategies_are_invisible_across_users(self, services: dict) -> None:
        root = services["users"].create_user("root@example.com", "root-pass-1")
        alice = services["users"].create_user("a@example.com", "alice-pass", actor=root)
        bob = services["users"].create_user("b@example.com", "bob-passx", actor=root)
        payload = {
            "range_config": {}, "signal_config": {}, "risk_config": {},
        }
        created = services["strategies"].create(alice, name="A strat", payload=payload)
        assert services["strategies"].get(alice, created.id).id == created.id
        from app_layer.errors import NotFoundError as _NF

        with pytest.raises(_NF):
            services["strategies"].get(bob, created.id)
        assert services["strategies"].list(bob) == ()

    def test_exchange_connections_hidden_from_other_users(self, services: dict) -> None:
        root = services["users"].create_user("root@example.com", "root-pass-1")
        alice = services["users"].create_user("a@example.com", "alice-pass", actor=root)
        bob = services["users"].create_user("b@example.com", "bob-passx", actor=root)
        connection = services["exchanges"].connect(
            alice, venue_id="binance", display_name="Binance main",
            api_key="AKIA-ALICE", secret="SECRET-ALICE",
        )
        # Alice sees her own connection; Bob gets an indistinguishable 404.
        assert services["exchanges"].get(alice, connection.id).id == connection.id
        from app_layer.errors import NotFoundError as _NF

        with pytest.raises(_NF):
            services["exchanges"].get(bob, connection.id)
        assert all(c.id != connection.id for c in services["exchanges"].list(bob))
