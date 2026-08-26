from pydantic import BaseModel, Field


class StrategyPayload(BaseModel):
    """All three engine configs are REQUIRED for reproducibility."""

    model_config = {"extra": "allow"}

    range_config: dict[str, object]
    signal_config: dict[str, object]
    risk_config: dict[str, object]


class StrategyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    payload: StrategyPayload
    active: bool = True


class StrategyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    payload: StrategyPayload | None = None
    active: bool | None = None


class StrategyOut(BaseModel):
    id: str
    name: str
    owner_user_id: str
    payload: dict[str, object]
    schema_version: str
    active: bool
    created_at_ms: int
    updated_at_ms: int
