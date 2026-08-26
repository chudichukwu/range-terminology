from pydantic import BaseModel, Field


class TickerOut(BaseModel):
    symbol: str
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    volume: float | None = None
    timestamp_ms: int | None = None


class CandleOut(BaseModel):
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
    is_closed: bool


class CandlesOut(BaseModel):
    symbol: str
    timeframe: str
    candles: list[CandleOut]
    quality_issues: list[str] = Field(default_factory=list)
