"""Watchlist use cases with strict per-user ownership."""

import time
import uuid
from collections.abc import Callable

from app_layer.errors import NotFoundError, ValidationError
from app_layer.models import User, Watchlist, WatchlistItem
from app_layer.ports import WatchlistRepository


def _default_clock() -> int:
    return time.time_ns() // 1_000_000


def _new_id() -> str:
    return uuid.uuid4().hex


class WatchlistService:
    """CRUD for watchlists and their items; OWNER may read others' lists."""

    def __init__(
        self,
        repository: WatchlistRepository,
        *,
        clock_ms: Callable[[], int] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._repo = repository
        self._clock_ms = clock_ms if clock_ms is not None else _default_clock
        self._id = id_factory if id_factory is not None else _new_id

    def _owned(self, actor: User, watchlist_id: str) -> Watchlist:
        found = self._repo.get_watchlist(watchlist_id)
        if found is None:
            raise NotFoundError("watchlist not found")
        # Isolation: a resource owned by someone else simply does not exist
        # for this actor (no enumeration oracle), except explicit OWNER reads.
        if found.owner_user_id != actor.id and actor.role.value != "owner":
            raise NotFoundError("watchlist not found")
        return found

    def create(self, actor: User, name: str) -> Watchlist:
        clean = (name or "").strip()
        if not 1 <= len(clean) <= 80:
            raise ValidationError("watchlist name must be 1-80 characters")
        now = self._clock_ms()
        return self._repo.create_watchlist(
            Watchlist(
                id=self._id(),
                owner_user_id=actor.id,
                name=clean,
                created_at_ms=now,
                updated_at_ms=now,
            )
        )

    def list(self, actor: User) -> tuple[Watchlist, ...]:
        return self._repo.list_watchlists(actor.id)

    def get(self, actor: User, watchlist_id: str) -> tuple[Watchlist, tuple[WatchlistItem, ...]]:
        found = self._owned(actor, watchlist_id)
        return found, self._repo.list_items(found.id)

    def rename(self, actor: User, watchlist_id: str, name: str) -> Watchlist:
        self._owned(actor, watchlist_id)
        clean = (name or "").strip()
        if not 1 <= len(clean) <= 80:
            raise ValidationError("watchlist name must be 1-80 characters")
        updated = self._repo.rename_watchlist(watchlist_id, clean, self._clock_ms())
        assert updated is not None
        return updated

    def delete(self, actor: User, watchlist_id: str) -> None:
        self._owned(actor, watchlist_id)
        self._repo.delete_watchlist(watchlist_id)

    def add_item(
        self,
        actor: User,
        watchlist_id: str,
        *,
        symbol: str,
        venue_id: str,
        notes: str = "",
        sort_order: int = 0,
        enabled: bool = True,
    ) -> WatchlistItem:
        self._owned(actor, watchlist_id)
        clean_symbol = (symbol or "").strip().upper()
        clean_venue = (venue_id or "").strip().lower()
        if "/" not in clean_symbol or len(clean_symbol) > 20:
            raise ValidationError("symbol must look like BASE/QUOTE (e.g. BTC/USDT)")
        if not clean_venue or len(clean_venue) > 30:
            raise ValidationError("venue_id must be a non-empty identifier")
        if len(notes) > 500:
            raise ValidationError("notes must be at most 500 characters")
        return self._repo.add_item(
            WatchlistItem(
                id=self._id(),
                watchlist_id=watchlist_id,
                symbol=clean_symbol,
                venue_id=clean_venue,
                enabled=enabled,
                notes=notes,
                sort_order=int(sort_order),
                created_at_ms=self._clock_ms(),
            )
        )

    def remove_item(self, actor: User, watchlist_id: str, item_id: str) -> None:
        self._owned(actor, watchlist_id)
        item = self._repo.get_item(item_id)
        if item is None or item.watchlist_id != watchlist_id:
            raise NotFoundError("item not found")
        self._repo.delete_item(item_id)
