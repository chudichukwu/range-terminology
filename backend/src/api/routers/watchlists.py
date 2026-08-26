"""Watchlist endpoints; ownership enforced in the application service."""

from fastapi import APIRouter

from api.dependencies import ContainerDep, CurrentUser
from api.schemas.watchlists import (
    WatchlistCreate,
    WatchlistItemCreate,
    WatchlistUpdate,
)

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


def _out(watchlist) -> dict[str, object]:  # type: ignore[no-untyped-def]
    return {
        "id": watchlist.id,
        "name": watchlist.name,
        "owner_user_id": watchlist.owner_user_id,
        "created_at_ms": watchlist.created_at_ms,
        "updated_at_ms": watchlist.updated_at_ms,
    }


def _item_out(item) -> dict[str, object]:  # type: ignore[no-untyped-def]
    return {
        "id": item.id,
        "watchlist_id": item.watchlist_id,
        "symbol": item.symbol,
        "venue_id": item.venue_id,
        "notes": item.notes,
        "sort_order": item.sort_order,
        "enabled": item.enabled,
        "created_at_ms": item.created_at_ms,
    }


@router.get("")
def list_watchlists(container: ContainerDep, user: CurrentUser) -> list[dict[str, object]]:
    return [_out(watchlist) for watchlist in container.watchlists.list(user)]


@router.post("", status_code=201)
def create_watchlist(
    payload: WatchlistCreate, container: ContainerDep, user: CurrentUser
) -> dict[str, object]:
    return _out(container.watchlists.create(user, payload.name))


@router.get("/{watchlist_id}")
def get_watchlist(
    watchlist_id: str, container: ContainerDep, user: CurrentUser
) -> dict[str, object]:
    watchlist, items = container.watchlists.get(user, watchlist_id)
    body = _out(watchlist)
    body["items"] = [_item_out(item) for item in items]
    return body


@router.patch("/{watchlist_id}")
def rename_watchlist(
    watchlist_id: str,
    payload: WatchlistUpdate,
    container: ContainerDep,
    user: CurrentUser,
) -> dict[str, object]:
    return _out(container.watchlists.rename(user, watchlist_id, payload.name))


@router.delete("/{watchlist_id}", status_code=204)
def delete_watchlist(
    watchlist_id: str, container: ContainerDep, user: CurrentUser
) -> None:
    container.watchlists.delete(user, watchlist_id)


@router.post("/{watchlist_id}/items", status_code=201)
def add_item(
    watchlist_id: str,
    payload: WatchlistItemCreate,
    container: ContainerDep,
    user: CurrentUser,
) -> dict[str, object]:
    item = container.watchlists.add_item(
        user,
        watchlist_id,
        symbol=payload.symbol,
        venue_id=payload.venue_id,
        notes=payload.notes,
        sort_order=payload.sort_order,
        enabled=payload.enabled,
    )
    return _item_out(item)


@router.delete("/{watchlist_id}/items/{item_id}", status_code=204)
def remove_item(
    watchlist_id: str,
    item_id: str,
    container: ContainerDep,
    user: CurrentUser,
) -> None:
    container.watchlists.remove_item(user, watchlist_id, item_id)
