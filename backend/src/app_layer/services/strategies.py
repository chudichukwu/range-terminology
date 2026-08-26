"""Named strategy configurations: reproducible engine configuration sets."""

import json
import time
import uuid
from collections.abc import Callable

from app_layer.errors import NotFoundError, ValidationError
from app_layer.models import StrategyConfig, User, validate_strategy_payload
from app_layer.ports import StrategyConfigRepository


def _default_clock() -> int:
    return time.time_ns() // 1_000_000


def _new_id() -> str:
    return uuid.uuid4().hex


def _canonical(payload: dict[str, object]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


class StrategyConfigService:
    """CRUD over user-owned strategy payloads with boundary validation."""

    def __init__(
        self,
        repository: StrategyConfigRepository,
        *,
        clock_ms: Callable[[], int] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._repo = repository
        self._clock_ms = clock_ms if clock_ms is not None else _default_clock
        self._id = id_factory if id_factory is not None else _new_id

    def _owned(self, actor: User, strategy_id: str) -> StrategyConfig | None:
        found = self._repo.get_strategy(strategy_id)
        if found is None or (
            found.owner_user_id != actor.id and actor.role.value != "owner"
        ):
            # Not owned => indistinguishable from nonexistent.
            return None
        return found

    def create(self, actor: User, *, name: str, payload: dict[str, object],
               active: bool = True) -> StrategyConfig:
        clean = (name or "").strip()
        if not 1 <= len(clean) <= 80:
            raise ValidationError("strategy name must be 1-80 characters")
        validate_strategy_payload(payload)
        now = self._clock_ms()
        return self._repo.create_strategy(
            StrategyConfig(
                id=self._id(),
                owner_user_id=actor.id,
                name=clean,
                payload_json=_canonical(payload),
                schema_version="1",
                active=active,
                created_at_ms=now,
                updated_at_ms=now,
            )
        )

    def get(self, actor: User, strategy_id: str) -> StrategyConfig:
        found = self._owned(actor, strategy_id)
        if found is None:
            raise NotFoundError("strategy not found")
        return found

    def list(self, actor: User) -> tuple[StrategyConfig, ...]:
        return self._repo.list_strategies(actor.id)

    def update(
        self,
        actor: User,
        strategy_id: str,
        *,
        name: str | None = None,
        payload: dict[str, object] | None = None,
        active: bool | None = None,
    ) -> StrategyConfig:
        existing = self.get(actor, strategy_id)
        new_name = (name or "").strip() if name is not None else existing.name
        if not 1 <= len(new_name) <= 80:
            raise ValidationError("strategy name must be 1-80 characters")
        new_payload = dict(payload) if payload is not None else existing.payload()
        validate_strategy_payload(new_payload)
        updated = StrategyConfig(
            id=existing.id,
            owner_user_id=existing.owner_user_id,
            name=new_name,
            payload_json=_canonical(new_payload),
            schema_version=existing.schema_version,
            active=existing.active if active is None else active,
            created_at_ms=existing.created_at_ms,
            updated_at_ms=self._clock_ms(),
        )
        return self._repo.update_strategy(updated)

    def delete(self, actor: User, strategy_id: str) -> None:
        """Strategies are deactivated rather than hard-deleted when referenced;
        Phase 9 keeps deletion simple and ownership-checked."""
        existing = self.get(actor, strategy_id)
        self.update(actor, existing.id, active=False)


def canonical_payload_json(payload: dict[str, object]) -> str:
    """Public helper reused by the backtest service for reproducibility."""
    return _canonical(payload)
