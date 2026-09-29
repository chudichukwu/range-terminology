import os

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from api.dependencies import ContainerDep, CurrentUser
from app_layer.errors import ValidationError
from market_data.models import Timeframe

router = APIRouter(prefix="/alerts", tags=["alerts"])


class RuleInput(BaseModel):
    watchlist_id: str
    timeframes: list[str] = Field(min_length=1, max_length=8)
    strategy_id: str | None = None
    enabled: bool = True
    telegram: bool = False
    telegram_chat_id: str = Field(default="", max_length=80, pattern=r"^-?\d*$")


@router.get("")
def events(request: Request, user: CurrentUser):
    return request.app.state.alerts.events(user.id)


@router.post("/read")
def mark_read(request: Request, user: CurrentUser):
    request.app.state.alerts.mark_seen(user.id)
    return {"ok": True}


@router.get("/rules")
def rules(request: Request, user: CurrentUser):
    return {
        "rules": request.app.state.alerts.rules(user.id),
        "telegram_configured": bool(os.environ.get("TELEGRAM_BOT_TOKEN")),
        "poll_seconds": 30,
    }


@router.post("/rules")
def save_rule(body: RuleInput, request: Request, container: ContainerDep, user: CurrentUser):
    container.watchlists.get(user, body.watchlist_id)
    if body.strategy_id:
        container.strategies.get(user, body.strategy_id)
    try:
        for tf in body.timeframes:
            Timeframe.parse(tf)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    if body.telegram and (not body.telegram_chat_id or not os.environ.get("TELEGRAM_BOT_TOKEN")):
        raise ValidationError(
            "Set TELEGRAM_BOT_TOKEN on the server and enter your Telegram chat ID first"
        )
    request.app.state.alerts.save_rule(user.id, body.watchlist_id, body.model_dump())
    return {"ok": True}
