"""User registration, authentication and account administration."""

import time
import uuid
from collections.abc import Callable

from app_layer.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthenticatedError,
    ValidationError,
)
from app_layer.models import Role, Session, User
from app_layer.ports import UserAccountStore
from app_layer.security import (
    generate_session_token,
    hash_password,
    token_digest,
    verify_password,
)
from app_layer.services.audit import AuditService

_SESSION_TTL_MS = 7 * 24 * 3_600_000


def _default_clock() -> int:
    return time.time_ns() // 1_000_000


def _new_id() -> str:
    return uuid.uuid4().hex


class UserService:
    """Registration, login/logout, session resolution and admin operations."""

    def __init__(
        self,
        store: UserAccountStore,
        audit: AuditService,
        *,
        clock_ms: Callable[[], int] | None = None,
        id_factory: Callable[[], str] | None = None,
        session_ttl_ms: int = _SESSION_TTL_MS,
    ) -> None:
        self._store = store
        self._audit = audit
        self._clock_ms = clock_ms if clock_ms is not None else _default_clock
        self._id = id_factory if id_factory is not None else _new_id
        self._session_ttl_ms = session_ttl_ms

    # ----- registration & authentication -----

    def create_user(
        self,
        email: str,
        password: str,
        *,
        role: Role = Role.USER,
        actor: User | None = None,
    ) -> User:
        """Register a user.

        The FIRST account bootstraps as OWNER without an actor; afterwards
        only an OWNER actor may create accounts.
        """
        now = self._clock_ms()
        normalized = email.strip().lower()
        if "@" not in normalized or len(normalized) < 5 or " " in normalized:
            raise ValidationError("a valid email address is required")
        existing_count = len(self._store.list_users())
        if existing_count > 0:
            if actor is None:
                raise UnauthenticatedError("authentication required to create users")
            if actor.role is not Role.OWNER:
                raise ForbiddenError("only the owner can create users")
        effective_role = role
        if existing_count == 0:
            effective_role = Role.OWNER
        if len(password) < 8:
            raise ValidationError("password must be at least 8 characters")
        if self._store.get_user_by_email(normalized) is not None:
            raise ConflictError("an account with this email already exists")
        user = User(
            id=self._id(),
            email=normalized,
            role=effective_role,
            active=True,
            created_at_ms=now,
            updated_at_ms=now,
        )
        stored = self._store.create_user(user, hash_password(password))
        self._audit.record(
            actor_user_id=actor.id if actor else None,
            action="user.created",
            resource_type="user",
            resource_id=stored.id,
            metadata={"email_domain": stored.email.split("@")[-1],
                      "role": stored.role.value},
        )
        return stored

    def authenticate(self, email: str, password: str) -> tuple[User, str]:
        """Verify credentials and start a session; returns (user, token)."""
        user = self._store.get_user_by_email(email)
        if user is None:
            raise UnauthenticatedError("invalid credentials")
        stored_hash = self._store.get_password_hash(user.id)
        if stored_hash is None or not verify_password(password, stored_hash):
            raise UnauthenticatedError("invalid credentials")
        if not user.active:
            self._audit.record(
                actor_user_id=user.id,
                action="user.login_blocked",
                resource_type="user",
                resource_id=user.id,
                outcome="rejected",
                metadata={"reason": "inactive"},
            )
            raise UnauthenticatedError("account is disabled")
        now = self._clock_ms()
        token = generate_session_token()
        self._store.create_session(
            Session(
                id=self._id(),
                user_id=user.id,
                token_digest=token_digest(token),
                created_at_ms=now,
                expires_at_ms=now + self._session_ttl_ms,
            )
        )
        logged_in = User(
            id=user.id,
            email=user.email,
            role=user.role,
            active=user.active,
            created_at_ms=user.created_at_ms,
            updated_at_ms=now,
            last_login_at_ms=now,
        )
        self._store.update_user(logged_in)
        return logged_in, token

    def resolve_session(self, token: str | None) -> User:
        """Active user behind ``token``, or unauthenticated."""
        if not token:
            raise UnauthenticatedError()
        session = self._store.get_session_by_digest(token_digest(token))
        if session is None or session.revoked_at_ms is not None:
            raise UnauthenticatedError()
        if session.expires_at_ms <= self._clock_ms():
            raise UnauthenticatedError()
        user = self._store.get_user(session.user_id)
        if user is None or not user.active:
            raise UnauthenticatedError()
        return user

    def logout(self, token: str) -> None:
        session = self._store.get_session_by_digest(token_digest(token))
        if session is not None and session.revoked_at_ms is None:
            self._store.revoke_session(session.id, self._clock_ms())

    def get_user(self, actor: User, user_id: str) -> User:
        """Users may read themselves; OWNER may read anyone."""
        if actor.role is not Role.OWNER and actor.id != user_id:
            raise NotFoundError("user not found")
        target = self._store.get_user(user_id)
        if target is None:
            raise NotFoundError("user not found")
        return target

    # ----- admin operations (OWNER enforced server-side) -----

    def require_owner(self, actor: User | None) -> User:
        if actor is None:
            raise UnauthenticatedError()
        if actor.role is not Role.OWNER:
            raise ForbiddenError("owner privileges required")
        return actor

    def list_users(self, actor: User) -> tuple[User, ...]:
        self.require_owner(actor)
        return self._store.list_users()

    def set_user_active(self, actor: User, target_user_id: str, *, active: bool) -> User:
        owner = self.require_owner(actor)
        target = self._store.get_user(target_user_id)
        if target is None:
            raise NotFoundError("user not found")
        if target.id == owner.id and not active:
            raise ValidationError("the owner cannot deactivate their own account")
        updated = User(
            id=target.id,
            email=target.email,
            role=target.role,
            active=active,
            created_at_ms=target.created_at_ms,
            updated_at_ms=self._clock_ms(),
            last_login_at_ms=target.last_login_at_ms,
        )
        self._store.update_user(updated)
        revoked = 0
        if not active:
            revoked = self._store.revoke_sessions_for_user(target.id, self._clock_ms())
        self._audit.record(
            actor_user_id=owner.id,
            action="user.enabled" if active else "user.disabled",
            resource_type="user",
            resource_id=target.id,
            metadata={"sessions_revoked": revoked},
        )
        return updated

    def set_user_role(self, actor: User, target_user_id: str, role: Role) -> User:
        owner = self.require_owner(actor)
        target = self._store.get_user(target_user_id)
        if target is None:
            raise NotFoundError("user not found")
        if target.id == owner.id and role is not Role.OWNER:
            raise ValidationError("the owner cannot demote their own account")
        updated = User(
            id=target.id,
            email=target.email,
            role=role,
            active=target.active,
            created_at_ms=target.created_at_ms,
            updated_at_ms=self._clock_ms(),
            last_login_at_ms=target.last_login_at_ms,
        )
        self._store.update_user(updated)
        self._audit.record(
            actor_user_id=owner.id,
            action="user.role_changed",
            resource_type="user",
            resource_id=target.id,
            metadata={"new_role": role.value},
        )
        return updated

    def revoke_sessions(self, actor: User, target_user_id: str) -> int:
        owner = self.require_owner(actor)
        if self._store.get_user(target_user_id) is None:
            raise NotFoundError("user not found")
        revoked = self._store.revoke_sessions_for_user(target_user_id, self._clock_ms())
        self._audit.record(
            actor_user_id=owner.id,
            action="user.sessions_revoked",
            resource_type="user",
            resource_id=target_user_id,
            metadata={"sessions_revoked": revoked},
        )
        return revoked
