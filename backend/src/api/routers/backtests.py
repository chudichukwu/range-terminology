"""Backtest endpoints: strategy + window -> deterministic persisted run."""

from fastapi import APIRouter

from api.dependencies import ContainerDep, CurrentUser
from api.schemas.backtests import BacktestRunRequest

router = APIRouter(prefix="/backtests", tags=["backtests"])


def _summary(record) -> dict[str, object]:  # type: ignore[no-untyped-def]
    return {
        "run_id": record.run_id,
        "config_hash": record.config_hash,
        "symbol": record.symbol,
        "timeframe": record.timeframe,
        "period_start_ms": record.period_start_ms,
        "period_end_ms": record.period_end_ms,
        "initial_capital": record.initial_capital,
        "final_equity": record.final_equity,
        "peak_equity": record.peak_equity,
        "max_drawdown": record.max_drawdown,
        "total_trades": record.total_trades,
        "owner_user_id": record.owner_user_id,
        "created_at_ms": record.created_at_ms,
    }


@router.post("", status_code=201)
def run_backtest(
    payload: BacktestRunRequest,
    container: ContainerDep,
    user: CurrentUser,
) -> dict[str, object]:
    strategy = container.strategies.get(user, payload.strategy_id)
    result, record = container.backtests.run_for_strategy(
        user,
        strategy,
        start_ms=payload.start_ms,
        end_ms=payload.end_ms,
        initial_capital=payload.initial_capital,
        fee_rate=payload.fee_rate,
        slippage_rate=payload.slippage_rate,
    )
    body = _summary(record)
    body["statistics"] = {
        "total_trades": result.statistics.total_trades,
        "completed_trades": result.statistics.completed_trades,
        "wins": result.statistics.wins,
        "losses": result.statistics.losses,
        "breakevens": result.statistics.breakevens,
        "win_rate": result.statistics.win_rate,
        "average_r": result.statistics.average_r,
        "profit_factor": result.statistics.profit_factor,
        "expectancy": result.statistics.expectancy,
        "total_realized_pnl": result.statistics.total_realized_pnl,
        "max_drawdown": result.statistics.max_drawdown,
    }
    body["regime_counts"] = dict(result.regime_counts)
    body["zone_counts"] = {
        key: value for key, value in result.zone_counts.items()
    }
    body["trades"] = [
        {
            "trade_id": trade.trade_id,
            "symbol": trade.symbol,
            "direction": trade.direction.value,
            "quantity": trade.quantity,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "realized_pnl": trade.realized_pnl,
            "fees": trade.fees,
            "slippage": trade.slippage,
            "realized_r": trade.realized_r,
            "result": trade.result.value if trade.result else None,
            "opened_at_ms": trade.opened_at_ms,
            "closed_at_ms": trade.closed_at_ms,
        }
        for trade in result.trades
    ]
    return body


@router.get("")
def list_backtests(container: ContainerDep, user: CurrentUser) -> list[dict[str, object]]:
    return [_summary(record) for record in container.backtests.list_runs(user)]


@router.get("/{run_id}")
def get_backtest(
    run_id: str, container: ContainerDep, user: CurrentUser
) -> dict[str, object]:
    return _summary(container.backtests.get_run(user, run_id))
