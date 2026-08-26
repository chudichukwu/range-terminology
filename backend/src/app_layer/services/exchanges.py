"""User-owned exchange connection metadata.

Secret material flows ONLY into the Phase 4 CredentialStore under a
per-connection reference; this service and every API response handle
metadata exclusively. Nothing here can leak an API secret because it never
touches one.
"""

import time
import uuid
from collections.abc import Callable

from app_layer.errors import ForbiddenError, NotFoundError, ValidationError
from app_layer.models import ExchangeConnection, User
from app_layer.ports import ExchangeConnectionRepository
from app_layer.services.audit import AuditService
from exchange.credentials import CredentialStore


def _default_clock() -> int:
    return time.time_ns() // 1_000_000


def _new_id() -> str:
    return uuid.uuid4().hex


class ExchangeConnectionService:
    """Register/remove venue connections with credentials behind the store."""

    def __init__(
        self,
        repository: ExchangeConnectionRepository,
        credential_store: CredentialStore,
        audit: AuditService,
        *,
        clock_ms: Callable[[], int] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._repo = repository
        self._credentials = credential_store
        self._audit = audit
        self._clock_ms = clock_ms if clock_ms is not None else _default_clock
        self._id = id_factory if id_factory is not None else _new_id

    def connect(
        self,
        actor: User,
        *,
        venue_id: str,
        display_name: str,
        api_key: str,
        secret: str,
        password: str | None = None,
        sandbox: bool = False,
    ) -> ExchangeConnection:
        clean_venue = (venue_id or "").strip().lower()
        if not clean_venue or len(clean_venue) > 30:
            raise ValidationError("venue_id must be a non-empty identifier")
        display = (display_name or "").strip()
        if not 1 <= len(display) <= 60:
            raise ValidationError("display_name must be 1-60 characters")
        if not api_key or not secret:
            raise ValidationError("api_key and secret are required")
        connection_id = self._id()
        ref = f"exchange:{connection_id}"
        blob = {
            "venue_id": clean_venue,
            "api_key": api_key,
            "secret": secret,
            "password": password,
            "sandbox": sandbox,
        }
        import json

        self._credentials.store(ref, json.dumps(blob, sort_keys=True))
        now = self._clock_ms()
        connection = ExchangeConnection(
            id=connection_id,
            owner_user_id=actor.id,
            venue_id=clean_venue,
            display_name=display,
            status="registered",
            credential_ref=ref,
            sandbox=sandbox,
            created_at_ms=now,
            updated_at_ms=now,
        )
        stored = self._repo.create_connection(connection)
        self._audit.record(
            actor_user_id=actor.id,
            action="exchange.connected",
            resource_type="exchange_connection",
            resource_id=stored.id,
            metadata={"venue": stored.venue_id, "sandbox": stored.sandbox},
        )
        return stored

    def get(self, actor: User, connection_id: str) -> ExchangeConnection:
        found = self._repo.get_connection(connection_id)
        if found is None or (
            found.owner_user_id != actor.id and actor.role.value != "owner"
        ):
            raise NotFoundError("connection not found")
        return found

    def list(self, actor: User) -> tuple[ExchangeConnection, ...]:
        if actor.role.value == "owner":
            return self._repo.list_connections()
        return self._repo.list_connections(actor.id)

    def disconnect(self, actor: User, connection_id: str) -> None:
        found = self.get(actor, connection_id)
        if found.owner_user_id != actor.id:
            # Only the owner of the connection may remove it (admins view,
            # but do not delete, other users' connections).
            raise ForbiddenError("only the connection owner can disconnect it")
        try:
            self._credentials.delete(found.credential_ref)
        except Exception:  # noqa: BLE001 - removal must proceed regardless
            pass
        self._repo.delete_connection(found.id)
        self._audit.record(
            actor_user_id=actor.id,
            action="exchange.disconnected",
            resource_type="exchange_connection",
            resource_id=found.id,
            metadata={"venue": found.venue_id},
        )
