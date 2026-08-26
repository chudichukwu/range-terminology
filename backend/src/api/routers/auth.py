"""Authentication endpoints: bootstrap registration, login, logout, me."""

from fastapi import APIRouter, Request

from api.dependencies import ContainerDep
from api.schemas.auth import LoginRequest, LogoutRequest, RegisterRequest
from app_layer.errors import UnauthenticatedError
from app_layer.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_dict(user: User) -> dict[str, object]:
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role.value,
        "active": user.active,
        "created_at_ms": user.created_at_ms,
        "updated_at_ms": user.updated_at_ms,
        "last_login_at_ms": user.last_login_at_ms,
    }


def _bearer_token(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


@router.post("/register", status_code=201)
def register(payload: RegisterRequest, container: ContainerDep) -> dict[str, object]:
    """Create the first account (becomes OWNER); later ones need an OWNER."""
    container.users.create_user(payload.email, payload.password)
    user, token = container.users.authenticate(payload.email, payload.password)
    return {"access_token": token, "token_type": "bearer", "user": _user_dict(user)}


@router.post("/login")
def login(payload: LoginRequest, container: ContainerDep) -> dict[str, object]:
    user, token = container.users.authenticate(payload.email, payload.password)
    return {"access_token": token, "token_type": "bearer", "user": _user_dict(user)}


@router.post("/logout", status_code=204)
def logout(
    payload: LogoutRequest, request: Request, container: ContainerDep
) -> None:
    token = payload.token or _bearer_token(request)
    if not token:
        raise UnauthenticatedError()
    container.users.logout(token)


@router.get("/me")
def me(request: Request, container: ContainerDep) -> dict[str, object]:
    user = container.users.resolve_session(_bearer_token(request) or None)
    return _user_dict(user)
