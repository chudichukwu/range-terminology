"""Admin/operations endpoints — every route gated by OWNER server-side."""

import time

from fastapi import APIRouter, Query

from api.dependencies import ContainerDep, OwnerRequired
from api.schemas.admin import (
    AdminCreateUserRequest,
    SetActiveRequest,
    SetRoleRequest,
    SystemHealthOut,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _user_out(user) -> dict[str, object]:  # type: ignore[no-untyped-def]
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role.value,
        "active": user.active,
        "created_at_ms": user.created_at_ms,
        "updated_at_ms": user.updated_at_ms,
        "last_login_at_ms": user.last_login_at_ms,
    }


@router.get("/users")
def list_users(owner: OwnerRequired, container: ContainerDep) -> list[dict[str, object]]:
    return [_user_out(user) for user in container.users.list_users(owner)]


@router.post("/users", status_code=201)
def create_user(
    payload: AdminCreateUserRequest, owner: OwnerRequired, container: ContainerDep
) -> dict[str, object]:
    from app_layer.models import Role

    created = container.users.create_user(
        payload.email,
        payload.password,
        role=Role(payload.role),
        actor=owner,
    )
    return _user_out(created)


@router.post("/users/{user_id}/active")
def set_active(
    user_id: str,
    payload: SetActiveRequest,
    owner: OwnerRequired,
    container: ContainerDep,
) -> dict[str, object]:
    return _user_out(
        container.users.set_user_active(owner, user_id, active=payload.active)
    )


@router.post("/users/{user_id}/role")
def set_role(
    user_id: str,
    payload: SetRoleRequest,
    owner: OwnerRequired,
    container: ContainerDep,
) -> dict[str, object]:
    from app_layer.models import Role

    return _user_out(container.users.set_user_role(owner, user_id, Role(payload.role)))


@router.post("/users/{user_id}/revoke-sessions")
def revoke_sessions(
    user_id: str, owner: OwnerRequired, container: ContainerDep
) -> dict[str, object]:
    revoked = container.users.revoke_sessions(owner, user_id)
    return {"revoked": revoked}


@router.get("/audit-log")
def audit_log(
    owner: OwnerRequired,
    container: ContainerDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, object]]:
    events = container.audit.tail(limit=limit)
    return [
        {
            "id": event.id,
            "actor_user_id": event.actor_user_id,
            "action": event.action,
            "resource_type": event.resource_type,
            "resource_id": event.resource_id,
            "timestamp_ms": event.timestamp_ms,
            "outcome": event.outcome,
            "metadata": dict(event.metadata),
        }
        for event in events
    ]


@router.get("/system-health")
def system_health(owner: OwnerRequired, container: ContainerDep) -> dict[str, object]:
    from backtesting.models import ENGINE_VERSION as BACKTEST_ENGINE_VERSION

    health = SystemHealthOut(
        status="ok",
        schema_version=container.store.schema_version,
        engine_versions={
            "backtester": BACKTEST_ENGINE_VERSION,
            "persistence_schema": str(container.store.schema_version),
        },
        user_count=len(container.users.list_users(owner)),
        dataset_count=len(container.store.list_dataset_summaries()),
        market_data_provider=container.markets.supported_timeframes().__len__() >= 0
        and "configured"
        or "unconfigured",
        time=int(time.time_ns() // 1_000_000),
    )
    return health.model_dump()


@router.get("/trading-activity")
def trading_activity(
    owner: OwnerRequired,
    container: ContainerDep,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, object]:
    """Aggregate oversight over recorded (simulated/live) trades and runs."""
    trades = container.store.list_trades()
    runs = container.backtests.list_runs(owner)
    wins = sum(1 for t in trades if t.result is not None and t.result.value == "win")
    losses = sum(1 for t in trades if t.result is not None and t.result.value == "loss")
    open_trades = sum(1 for t in trades if t.status.value == "open")
    recent_runs = [
        {
            "run_id": run.run_id,
            "symbol": run.symbol,
            "timeframe": run.timeframe,
            "total_trades": run.total_trades,
            "final_equity": run.final_equity,
            "created_at_ms": run.created_at_ms,
        }
        for run in runs[:limit]
    ]
    return {
        "totals": {
            "trades": len(trades),
            "wins": wins,
            "losses": losses,
            "open": open_trades,
            "backtest_runs": len(runs),
        },
        "recent_backtests": recent_runs,
    }
