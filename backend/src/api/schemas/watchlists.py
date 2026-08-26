from pydantic import BaseModel, Field


class WatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class WatchlistUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class WatchlistItemCreate(BaseModel):
    symbol: str = Field(min_length=3, max_length=20, examples=["BTC/USDT"])
    venue_id: str = Field(min_length=2, max_length=30, examples=["binance"])
    notes: str = Field(default="", max_length=500)
    sort_order: int = 0
    enabled: bool = True


class WatchlistItemOut(WatchlistItemCreate):
    id: str
    watchlist_id: str
    created_at_ms: int


class WatchlistOut(BaseModel):
    id: str
    name: str
    owner_user_id: str
    created_at_ms: int
    updated_at_ms: int


class WatchlistWithItems(WatchlistOut):
    items: list[WatchlistItemOut] = []
