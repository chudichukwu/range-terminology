from pydantic import BaseModel, Field


class AdminCreateUserRequest(BaseModel):
    email: str = Field(min_length=5, max_length=120)
    password: str = Field(min_length=8, max_length=200)
    role: str = Field(default="user", pattern="^(user|owner)$")


class UserAdminOut(BaseModel):
    id: str
    email: str
    role: str
    active: bool
    created_at_ms: int
    updated_at_ms: int
    last_login_at_ms: int | None = None


class SetActiveRequest(BaseModel):
    active: bool


class SetRoleRequest(BaseModel):
    role: str = Field(pattern="^(user|owner)$")


class AuditEventOut(BaseModel):
    id: str
    actor_user_id: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    timestamp_ms: int
    outcome: str
    metadata: dict[str, object] = {}


class SystemHealthOut(BaseModel):
    status: str
    schema_version: int
    engine_versions: dict[str, str]
    user_count: int
    dataset_count: int
    market_data_provider: str
    time: int
