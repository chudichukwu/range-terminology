"""Execution-to-trade recording boundary.

Converts a completed Phase 5 :class:`~execution_engine.models.ExecutionResult`
into a persistable :class:`~persistence.models.StoredTrade` — without
modifying the execution lifecycle. Only executions that actually took on
position (FILLED / PARTIALLY_FILLED) can become trades; everything else is a
programming error and rejected loudly. No price, quantity or risk figure is
ever invented: missing authoritative facts abort the conversion.
"""

from exchange.models import PositionDirection
from execution_engine.base import ExecutionStatus
from execution_engine.models import ExecutionResult
from persistence.errors import PersistenceError, PersistenceErrorCode
from persistence.models import StoredTrade, TradeContext, TradeStatus


def trade_from_execution(
    result: ExecutionResult,
    *,
    trade_id: str,
    risk_amount: float | None = None,
    timeframe: str | None = None,
    strategy_id: str | None = None,
    config_hash: str | None = None,
    context: TradeContext | None = None,
    created_at_ms: int = 0,
) -> StoredTrade:
    """Build an OPEN trade from an entry that actually filled.

    Args:
        result: Completed Phase 5 execution outcome.
        trade_id: Caller-chosen unique identifier.
        risk_amount: Authoritative planned risk (e.g.
            ``RiskDecision.risk_amount``); enables realized-R once the trade
            closes. Never guessed here.
        timeframe: Canonical timeframe string when known.
        strategy_id / config_hash: Strategy/configuration provenance so
            historical results never become ambiguous across config changes.
        context: Structured signal/range context for "why was this taken?".
        created_at_ms: Persistence timestamps.

    Raises:
        PersistenceError: When the execution did not take a position or lacks
            authoritative fill facts.
    """
    if result.status not in (ExecutionStatus.FILLED, ExecutionStatus.PARTIALLY_FILLED):
        raise PersistenceError(
            PersistenceErrorCode.TRADE_INVALID,
            f"execution {result.execution_id} has status {result.status.value}; "
            "only filled/partially-filled entries become trades",
            metadata={"execution_id": result.execution_id},
        )
    if result.direction is None:
        raise PersistenceError(
            PersistenceErrorCode.TRADE_INVALID,
            f"execution {result.execution_id} carries no direction",
            metadata={"execution_id": result.execution_id},
        )
    if result.direction not in (PositionDirection.LONG, PositionDirection.SHORT):
        raise PersistenceError(
            PersistenceErrorCode.TRADE_INVALID,
            f"execution direction {result.direction} is not a position direction",
            metadata={"execution_id": result.execution_id},
        )
    quantity = result.filled_quantity
    if quantity <= 0.0:
        raise PersistenceError(
            PersistenceErrorCode.TRADE_INVALID,
            f"execution {result.execution_id} reports no filled quantity",
            metadata={"execution_id": result.execution_id},
        )
    entry_price = result.average_fill_price
    if entry_price is None or entry_price <= 0.0:
        raise PersistenceError(
            PersistenceErrorCode.TRADE_INVALID,
            f"execution {result.execution_id} has no authoritative average fill price",
            metadata={"execution_id": result.execution_id},
        )
    return StoredTrade(
        trade_id=trade_id,
        symbol=result.symbol,
        direction=result.direction,
        quantity=quantity,
        entry_price=entry_price,
        opened_at_ms=result.created_at_ms,
        status=TradeStatus.OPEN,
        execution_ref=result.execution_id,
        timeframe=timeframe,
        risk_amount=risk_amount,
        strategy_id=strategy_id,
        config_hash=config_hash,
        context=context,
        created_at_ms=created_at_ms,
        updated_at_ms=created_at_ms,
    )


__all__ = ["trade_from_execution"]
