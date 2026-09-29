from pydantic import BaseModel


class DatasetIssueOut(BaseModel):
    kind: str
    detail: str
    index: int | None = None
    gap_start_ms: int | None = None
    gap_end_ms: int | None = None


class DatasetOut(BaseModel):
    symbol: str
    timeframe: str
    source: str
    candle_count: int
    first_timestamp_ms: int | None = None
    last_timestamp_ms: int | None = None
    quality_status: str
    issues: list[DatasetIssueOut] = []
    ingested_at_ms: int
    updated_at_ms: int
