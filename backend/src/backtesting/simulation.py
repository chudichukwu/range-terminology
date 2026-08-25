"""Deterministic simulated execution on OHLCV bars.

DOCUMENTED SIMULATION ASSUMPTIONS (deliberately conservative; never
optimistic):

A1. Decisions happen after a candle CLOSES; entry fills at the NEXT candle's
    open. The close that produced a decision is never traded directly.
A2. Market-entry slippage always moves AGAINST the trader:
    long fills at ``open * (1 + slippage)``, short at ``open * (1 - slippage)``.
A3. Protective levels are active immediately on the entry candle: its full
    high/low range may stop out or take profit the same bar.
A4. Gap handling: when a bar OPENS beyond a level, the fill happens AT THE
    OPEN (worse for stops, better-but-realistic for gap-through targets).
    Otherwise limit-style levels fill exactly at the level.
A5. AMBIGUOUS SAME-CANDLE STOP+TARGET: if one bar's range touches both the
    stop and the target, the trade is resolved as a STOP-OUT. OHLCV cannot
    reveal intrabar path; we always assume the worst ordering.
A6. Full fills only. OHLCV carries no tick data, so partial fills would be
    invention; quantity from the RiskDecision fills completely.
A7. Fees apply per side on notional at each modeled fill price.

These rules make replays deterministic and reproducible while biasing
results PESSIMISTICALLY — a strategy must survive them honestly.
"""

import math

from exchange.models import PositionDirection


def simulate_entry_fill(
    direction: PositionDirection,
    open_price: float,
    *,
    slippage_rate: float,
) -> float:
    """Entry fill per A2: adverse slippage against the trader."""
    if open_price <= 0.0 or slippage_rate < 0.0:
        raise ValueError("open_price must be positive and slippage non-negative")
    adverse = 1.0 + slippage_rate if direction is PositionDirection.LONG else 1.0 - slippage_rate
    return open_price * adverse


def simulate_exit_fill(
    direction: PositionDirection,
    level_price: float,
    open_price: float,
    *,
    slippage_rate: float,
    is_stop: bool,
) -> float:
    """Exit fill per A4/A2.

    A bar that OPENS already beyond the level (in whichever direction counts
    as through for this side/kind) fills exactly AT THE OPEN: the gap itself
    is realized slippage. Otherwise the level fills with adverse exit-side
    slippage (A2).

    Through-the-level geometry:
        LONG  stop  : gapped when ``open <  level``
        LONG  target: gapped when ``open >  level``
        SHORT stop  : gapped when ``open >  level``
        SHORT target: gapped when ``open <  level``
    """
    if direction is PositionDirection.LONG:
        gapped = open_price < level_price if is_stop else open_price > level_price
        if gapped:
            return open_price
        return level_price * (1.0 - slippage_rate)
    gapped = open_price > level_price if is_stop else open_price < level_price
    if gapped:
        return open_price
    return level_price * (1.0 + slippage_rate)


def resolve_protective_exit(
    direction: PositionDirection,
    stop_price: float,
    target_price: float,
    *,
    candle_open: float,
    candle_high: float,
    candle_low: float,
    slippage_rate: float = 0.0,
) -> tuple[str | None, float]:
    """Decide whether one bar triggers the stop, the target, or neither.

    Returns:
        ``("stop", fill_price)``, ``("target", fill_price)`` or
        ``(None, 0.0)`` when the bar resolves nothing. Per A5, when both
        levels sit inside the bar's range the STOP wins (pessimistic).
    """
    touched_stop = (
        candle_low <= stop_price if direction is PositionDirection.LONG
        else candle_high >= stop_price
    )
    touched_target = (
        candle_high >= target_price if direction is PositionDirection.LONG
        else candle_low <= target_price
    )
    if touched_stop:
        return (
            "stop",
            simulate_exit_fill(
                direction,
                stop_price,
                candle_open,
                slippage_rate=slippage_rate,
                is_stop=True,
            ),
        )
    if touched_target:
        return (
            "target",
            simulate_exit_fill(
                direction,
                target_price,
                candle_open,
                slippage_rate=slippage_rate,
                is_stop=False,
            ),
        )
    return None, 0.0


def wilder_atr(
    highs: list[float], lows: list[float], closes: list[float], period: int
) -> float | None:
    """Wilder-smoothed ATR over provided closed candles.

    Used solely to feed the Phase 3 RiskEngine when ``stop_method`` is
    ``"atr"`` — computed strictly from candles available at decision time.
    Returns ``None`` when there is not enough history for one full period.
    """
    count = len(closes)
    if period < 1 or count < period + 1:
        return None
    true_ranges = [
        max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        for i in range(1, count)
    ]
    atr = sum(true_ranges[:period]) / period
    for value in true_ranges[period:]:
        atr = (atr * (period - 1) + value) / period
    if not math.isfinite(atr):
        return None
    return atr


__all__ = [
    "resolve_protective_exit",
    "simulate_entry_fill",
    "simulate_exit_fill",
    "wilder_atr",
]
