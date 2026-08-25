"""Derived trade statistics — computed from stored facts, never authoritative.

Definitions (deliberately explicit; do not silently reinterpret):

- COMPLETED TRADE      : ``status == CLOSED``.
- BREAKEVEN            : closed trade with ``|realized_pnl| <= epsilon``
                         (default 1e-9).
- WIN                  : ``realized_pnl > +epsilon``.
- LOSS                 : ``realized_pnl < -epsilon``.
- WIN RATE             : wins / (wins + losses). Breakevens are excluded
                         from BOTH numerator and denominator.
- AVERAGE WIN/LOSS     : mean realized P&L over winners/losers respectively
                         (breakevens excluded).
- TOTAL REALIZED P&L   : sum over ALL completed trades (breakevens included;
                         they contribute ~0 by definition).
- EXPECTANCY (per trade): total_realized_pnl / completed_count.
- PROFIT FACTOR        : gross_profit / |gross_loss| where gross profit is
                         the sum of winning P&Ls and gross loss the sum of
                         losing P&Ls. ``None`` when there are no losses
                         (division undefined — never reported as infinity).
- AVERAGE R            : mean of non-null realized_r over completed trades.
- MAX DRAWDOWN         : max peak-to-trough decline of the cumulative
                         realized-P&L curve ordered by close time; ``None``
                         with fewer than two data points. Trade-close
                         granularity only — not an intraday equity curve.

Open trades are ignored everywhere except nowhere: they simply never count.
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass

from persistence.models import (
    DEFAULT_BREAKEVEN_EPSILON,
    StoredTrade,
    TradeStatus,
)


@dataclass(frozen=True)
class TradeStatistics:
    """Immutable snapshot derived from a set of stored trades."""

    total_trades: int
    open_trades: int
    completed_trades: int
    wins: int
    losses: int
    breakevens: int
    win_rate: float | None
    average_win: float | None
    average_loss: float | None
    average_r: float | None
    total_realized_pnl: float
    expectancy: float | None
    profit_factor: float | None
    max_drawdown: float | None


def compute_trade_statistics(
    trades: Iterable[StoredTrade],
    *,
    breakeven_epsilon: float = DEFAULT_BREAKEVEN_EPSILON,
) -> TradeStatistics:
    """Derive statistics for the given trades per the module definitions."""
    all_trades = tuple(trades)
    completed = [trade for trade in all_trades if trade.status is TradeStatus.CLOSED]
    open_count = len(all_trades) - len(completed)

    wins: list[float] = []
    losses: list[float] = []
    breakevens = 0
    r_values: list[float] = []
    for trade in completed:
        pnl = trade.realized_pnl
        if pnl is None:
            continue
        if not math.isfinite(pnl):
            raise ValueError(f"stored trade {trade.trade_id} has non-finite P&L")
        if trade.realized_r is not None:
            r_values.append(trade.realized_r)
        if pnl > breakeven_epsilon:
            wins.append(pnl)
        elif pnl < -breakeven_epsilon:
            losses.append(pnl)
        else:
            breakevens += 1

    decided = len(wins) + len(losses)
    win_rate = (len(wins) / decided) if decided > 0 else None
    total_pnl = sum(
        (trade.realized_pnl or 0.0)
        for trade in completed
        if trade.realized_pnl is not None
    )
    gross_profit = sum(pnl for pnl in wins)
    gross_loss = sum(pnl for pnl in losses)
    profit_factor = None
    if losses:
        denominator = abs(gross_loss)
        profit_factor = round(gross_profit / denominator, 6)

    return TradeStatistics(
        total_trades=len(all_trades),
        open_trades=open_count,
        completed_trades=len(completed),
        wins=len(wins),
        losses=len(losses),
        breakevens=breakevens,
        win_rate=round(win_rate, 6) if win_rate is not None else None,
        average_win=round(sum(wins) / len(wins), 6) if wins else None,
        average_loss=round(sum(losses) / len(losses), 6) if losses else None,
        average_r=round(sum(r_values) / len(r_values), 6) if r_values else None,
        total_realized_pnl=round(total_pnl, 6),
        expectancy=round(total_pnl / len(completed), 6) if completed else None,
        profit_factor=profit_factor,
        max_drawdown=_max_drawdown(completed),
    )


def _max_drawdown(completed: list[StoredTrade]) -> float | None:
    """Max peak-to-trough decline of the cumulative P&L curve, if derivable."""
    points = sorted(
        (
            (trade.closed_at_ms, trade.realized_pnl or 0.0)
            for trade in completed
            if trade.closed_at_ms is not None
        ),
        key=lambda pair: (pair[0], ),
    )
    if len(points) < 2:
        return None
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for _, pnl in points:
        equity += pnl
        peak = max(peak, equity)
        drawdown = peak - equity
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    return round(max_drawdown, 6)


__all__ = [
    "DEFAULT_BREAKEVEN_EPSILON",
    "TradeStatistics",
    "compute_trade_statistics",
]
