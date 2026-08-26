"""Application-layer value types (users, watchlists, strategies, audit).

These are the shapes services consume and produce; HTTP DTOs are defined
separately in :mod:`api.schemas` so the API contract never accidentally
becomes the domain model.
"""

import json
from dataclasses import dataclass, field
from enum import Enum

from app_layer.security import scrub_sensitive


class Role(Enum):
    """Authorization roles; OWNER is the administrative role."""

    USER = "user"
    OWNER = "owner"


@dataclass(frozen=True)
class User:
    """An authenticated identity. Never carries password material."""

    id: str
    email: str
    role: Role
    active: bool
    created_at_ms: int
    updated_at_ms: int
    last_login_at_ms: int | None = None


@dataclass(frozen=True)
class Session:
    """A server-side session; ``token_digest`` is stored, tokens are not."""

    id: str
    user_id: str
    token_digest: str
    created_at_ms: int
    expires_at_ms: int
    revoked_at_ms: int | None = None


@dataclass(frozen=True)
class Watchlist:
    id: str
    owner_user_id: str
    name: str
    created_at_ms: int
    updated_at_ms: int


@dataclass(frozen=True)
class WatchlistItem:
    id: str
    watchlist_id: str
    symbol: str
    venue_id: str
    enabled: bool = True
    notes: str = ""
    sort_order: int = 0
    created_at_ms: int = 0


@dataclass(frozen=True)
class StrategyConfig:
    """A named, reproducible strategy configuration owned by a user.

    The payload mirrors the declarative configs consumed by the existing
    engines (``range_config``/``signal_config``/``risk_config`` plus optional
    simulation economics) so the SAME configuration drives backtesting now
    and future live/paper trading later — no duplicated engine models.
    """

    id: str
    owner_user_id: str
    name: str
    payload_json: str
    schema_version: str
    active: bool
    created_at_ms: int
    updated_at_ms: int

    def payload(self) -> dict[str, object]:
        data = json.loads(self.payload_json)
        if not isinstance(data, dict):
            raise ValueError("strategy payload must be a JSON object")
        return data


REQUIRED_STRATEGY_KEYS = ("range_config", "signal_config", "risk_config")
STRATEGY_SCHEMA_VERSION = "1"


def validate_strategy_payload(payload: dict[str, object]) -> None:
    """Typed boundary validation for strategy payloads.

    Ensures the three engine configuration mappings exist and are mappings;
    deeper validation happens when engines consume them (single source of
    truth stays with the engines).
    """
    for key in REQUIRED_STRATEGY_KEYS:
        value = payload.get(key)
        if not isinstance(value, dict):
            raise ValueError(
                f"strategy payload requires {key!r} to be an object"
            )


@dataclass(frozen=True)
class ExchangeConnection:
    """User-owned venue connection METADATA.

    Secrets live only inside the Phase 4 :class:`~exchange.credentials.CredentialStore`,
    referenced here indirectly by ``credential_ref``. This record can safely
    cross the API: it cannot carry secret material.
    """

    id: str
    owner_user_id: str
    venue_id: str
    display_name: str
    status: str
    credential_ref: str
    sandbox: bool
    created_at_ms: int
    updated_at_ms: int


@dataclass(frozen=True)
class AuditEvent:
    """Append-only record of a privileged or security-sensitive action."""

    id: str
    actor_user_id: str | None
    action: str
    resource_type: str
    resource_id: str | None
    timestamp_ms: int
    outcome: str
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Defense-in-depth: sensitive-looking keys are redacted on entry.
        object.__setattr__(self, "metadata", scrub_sensitive(dict(self.metadata)))
