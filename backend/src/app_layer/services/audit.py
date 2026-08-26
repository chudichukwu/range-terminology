"""Append-only audit recording for privileged / sensitive actions."""

import time
import uuid
from collections.abc import Callable

from app_layer.models import AuditEvent
from app_layer.ports import AuditLogRepository
from app_layer.security import scrub_sensitive


def _default_clock() -> int:
    return time.time_ns() // 1_000_000


def _new_id() -> str:
    return uuid.uuid4().hex


class AuditService:
    """Records and serves the audit trail; sensitive keys are redacted."""

    def __init__(
        self,
        repository: AuditLogRepository,
        *,
        clock_ms: Callable[[], int] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._repo = repository
        self._clock_ms = clock_ms if clock_ms is not None else _default_clock
        self._id = id_factory if id_factory is not None else _new_id

    def record(
        self,
        *,
        actor_user_id: str | None,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        outcome: str = "success",
        metadata: dict[str, object] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            id=self._id(),
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            timestamp_ms=self._clock_ms(),
            outcome=outcome,
            metadata=scrub_sensitive(dict(metadata or {})),
        )
        return self._repo.append_audit_event(event)

    def tail(self, *, limit: int = 100) -> tuple[AuditEvent, ...]:
        """Newest-first audit tail."""
        return self._repo.list_audit_events(limit=limit)
