"""Read-oriented trade history endpoints (Phase 7 facts).

Ownership: a trade's ``strategy_id`` references its owning configuration, so
visibility is derived from the authenticated user's own strategies. OWNERs
see aggregate history.
"""

from fastapi import APIRouter, Query

from api.dependencies import ContainerDep, CurrentUser
from app_layer.errors import NotFoundError
from persistence.models import TradeResult

router = APIRouter(prefix="/trades", tags=["trades"])


def _out(trade) -> dict[str, object]:  # type: ignore[no-untyped-def]
    context_payload: dict[str, object] | None = None
    if trade.context is not None:
        context_payload = {
            "range_mode": trade.context.range_mode,
            "range_high": trade.context.range_high,
            "range_low": trade.context.range_low,
            "signal_direction": trade.context.signal_direction,
            "signal_reason": trade.context.signal_reason,
            "regime": trade.context.extra.get("regime"),
            "zone": trade.context.extra.get("zone"),
            "simulated": trade.context.extra.get("simulated"),
        }
    return {
        "trade_id": trade.trade_id,
        "symbol": trade.symbol,
        "timeframe": trade.timeframe,
        "direction": trade.direction.value,
        "quantity": trade.quantity,
        "entry_price": trade.entry_price,
        "exit_price": trade.exit_price,
        "opened_at_ms": trade.opened_at_ms,
        "closed_at_ms": trade.closed_at_ms,
        "status": trade.status.value,
        "realized_pnl": trade.realized_pnl,
        "fees": trade.fees,
        "slippage": trade.slippage,
        "risk_amount": trade.risk_amount,
        "realized_r": trade.realized_r,
        "result": trade.result.value if trade.result else None,
        "strategy_id": trade.strategy_id,
        "config_hash": trade.config_hash,
        "context": context_payload,
    }


def _visible_strategy_ids(container, user) -> set[str] | None:  # type: ignore[no-untyped-def]
    """None means unrestricted (OWNER)."""
    if user.role.value == "owner":
        return None
    return {strategy.name for strategy in container.strategies.list(user)}


@router.get("")
def list_trades(
    container: ContainerDep,
    user: CurrentUser,
    symbol: str | None = Query(default=None),
    result: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, object]]:
    parsed_result = (
        TradeResult(result) if result in {"win", "loss", "breakeven"} else None
    )
    trades = container.store.list_trades(symbol=symbol, result=parsed_result)
    visible_ids = _visible_strategy_ids(container, user)
    if visible_ids is not None:
        trades = tuple(
            trade for trade in trades if trade.strategy_id in visible_ids
        )
    return [_out(trade) for trade in trades[:limit]]


@router.get("/{trade_id}")
def get_trade(
    trade_id: str, container: ContainerDep, user: CurrentUser
) -> dict[str, object]:
    trade = container.store.get_trade(trade_id)
    if trade is None:
        raise NotFoundError("trade not found")
    visible_ids = _visible_strategy_ids(container, user)
    if visible_ids is not None and trade.strategy_id not in visible_ids:
        raise NotFoundError("trade not found")
    return _out(trade)
