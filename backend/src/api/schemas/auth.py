from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=120)
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class LogoutRequest(BaseModel):
    token: str | None = None


class UserOut(BaseModel):
    id: str
    email: str
    role: str
    active: bool
    created_at_ms: int
    updated_at_ms: int
    last_login_at_ms: int | None = None
