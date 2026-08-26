"""Exchange connection endpoints: metadata only, never secrets."""

from fastapi import APIRouter

from api.dependencies import ContainerDep, CurrentUser
from api.schemas.exchanges import ExchangeConnectRequest

router = APIRouter(prefix="/exchanges", tags=["exchanges"])


def _out(connection) -> dict[str, object]:  # type: ignore[no-untyped-def]
    return {
        "id": connection.id,
        "venue_id": connection.venue_id,
        "display_name": connection.display_name,
        "status": connection.status,
        "sandbox": connection.sandbox,
        "created_at_ms": connection.created_at_ms,
        "updated_at_ms": connection.updated_at_ms,
    }


@router.get("/connections")
def list_connections(
    container: ContainerDep, user: CurrentUser
) -> list[dict[str, object]]:
    return [_out(c) for c in container.exchanges.list(user)]


@router.post("/connections", status_code=201)
def connect(
    payload: ExchangeConnectRequest, container: ContainerDep, user: CurrentUser
) -> dict[str, object]:
    created = container.exchanges.connect(
        user,
        venue_id=payload.venue_id,
        display_name=payload.display_name,
        api_key=payload.api_key.get_secret_value(),
        secret=payload.secret.get_secret_value(),
        password=(
            payload.password.get_secret_value() if payload.password else None
        ),
        sandbox=payload.sandbox,
    )
    return _out(created)


@router.delete("/connections/{connection_id}", status_code=204)
def disconnect(
    connection_id: str, container: ContainerDep, user: CurrentUser
) -> None:
    container.exchanges.disconnect(user, connection_id)
