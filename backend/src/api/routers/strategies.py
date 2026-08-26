"""Strategy configuration endpoints (user-owned, reproducible payloads)."""

from fastapi import APIRouter

from api.dependencies import ContainerDep, CurrentUser
from api.schemas.strategies import StrategyCreate, StrategyUpdate

router = APIRouter(prefix="/strategies", tags=["strategies"])


def _out(strategy) -> dict[str, object]:  # type: ignore[no-untyped-def]
    return {
        "id": strategy.id,
        "name": strategy.name,
        "owner_user_id": strategy.owner_user_id,
        "payload": strategy.payload(),
        "schema_version": strategy.schema_version,
        "active": strategy.active,
        "created_at_ms": strategy.created_at_ms,
        "updated_at_ms": strategy.updated_at_ms,
    }


@router.get("")
def list_strategies(
    container: ContainerDep, user: CurrentUser
) -> list[dict[str, object]]:
    return [_out(strategy) for strategy in container.strategies.list(user)]


@router.post("", status_code=201)
def create_strategy(
    payload: StrategyCreate, container: ContainerDep, user: CurrentUser
) -> dict[str, object]:
    created = container.strategies.create(
        user, name=payload.name, payload=dict(payload.payload.model_dump()),
        active=payload.active,
    )
    return _out(created)


@router.get("/{strategy_id}")
def get_strategy(
    strategy_id: str, container: ContainerDep, user: CurrentUser
) -> dict[str, object]:
    return _out(container.strategies.get(user, strategy_id))


@router.patch("/{strategy_id}")
def update_strategy(
    strategy_id: str,
    payload: StrategyUpdate,
    container: ContainerDep,
    user: CurrentUser,
) -> dict[str, object]:
    updated = container.strategies.update(
        user,
        strategy_id,
        name=payload.name,
        payload=(
            dict(payload.payload.model_dump()) if payload.payload is not None else None
        ),
        active=payload.active,
    )
    return _out(updated)


@router.delete("/{strategy_id}", status_code=204)
def deactivate_strategy(
    strategy_id: str, container: ContainerDep, user: CurrentUser
) -> None:
    container.strategies.delete(user, strategy_id)
