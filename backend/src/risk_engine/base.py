"""Risk domain primitives: account state, constraints, decisions, and enums.

Pure value types shared by the risk engine and its callers. Independent of any
exchange, database, or API model.
"""

import math
from dataclasses import dataclass, field
from enum import Enum

from signal_engine import SignalDirection


class StopMethod(Enum):
    """How the protective stop level is derived."""

    RANGE = "range"
    ATR = "atr"
    FIXED_PERCENT = "fixed_percent"


class TargetMethod(Enum):
    """How the profit target level is derived."""

    OPPOSITE_RANGE_EDGE = "opposite_range_edge"
    RANGE_FRACTION = "range_fraction"
    FIXED_RR = "fixed_rr"


class RiskDecisionStatus(Enum):
    """Outcome of a risk evaluation."""

    APPROVED = "approved"
    REJECTED = "rejected"


class RejectionReason(Enum):
    """Why a risk evaluation did not approve a trade.

    ``NONE`` accompanies approved decisions.
    """

    NONE = "none"
    NO_SIGNAL = "no_signal"
    INVALID_SIGNAL = "invalid_signal"
    INVALID_STOP = "invalid_stop"
    RISK_LIMIT = "risk_limit"
    MAX_POSITION_SIZE = "max_position_size"
    MAX_PORTFOLIO_EXPOSURE = "max_portfolio_exposure"
    MAX_OPEN_POSITIONS = "max_open_positions"
    DRAWDOWN_LIMIT = "drawdown_limit"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    CONSECUTIVE_LOSS_LIMIT = "consecutive_loss_limit"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    LEVERAGE_LIMIT = "leverage_limit"
    EXCHANGE_CONSTRAINT = "exchange_constraint"
    MIN_REWARD_RISK = "min_reward_risk"


@dataclass(frozen=True)
class OpenPosition:
    """Domain-level representation of one open position.

    Attributes:
        symbol: Instrument identifier (venue-neutral string, e.g. ``BTC/USDT``).
        side: Position direction; LONG or SHORT only.
        quantity: Absolute position size (always positive; ``side`` carries sign).
        entry_price: Average entry price.
    """

    symbol: str
    side: SignalDirection
    quantity: float
    entry_price: float

    def __post_init__(self) -> None:
        if self.side not in (SignalDirection.LONG, SignalDirection.SHORT):
            raise ValueError(f"OpenPosition.side must be LONG or SHORT, got {self.side}")
        for name in ("quantity", "entry_price"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"OpenPosition.{name} must be finite and positive, got {value}")

    @property
    def notional(self) -> float:
        """Absolute notional value of the position at entry."""
        return self.quantity * self.entry_price


@dataclass(frozen=True)
class AccountRiskState:
    """Immutable snapshot of the portfolio risk state used for decisions.

    Attributes:
        equity: Current account equity (quote currency).
        available_balance: Balance available to fund a new position.
        peak_equity: Historical equity peak, used for max-drawdown checks.
        daily_start_equity: Equity at the start of the trading day, used for
            daily-loss checks.
        open_positions: Currently open positions (read-only snapshot).
        total_exposure: Total notional exposure of open positions as reported
            by the caller; trusted as authoritative.
        consecutive_losses: Number of losing trades in a row.
        realized_pnl: Realized PnL to date (informational).
    """

    equity: float
    available_balance: float
    peak_equity: float
    daily_start_equity: float
    open_positions: tuple[OpenPosition, ...] = ()
    total_exposure: float = 0.0
    consecutive_losses: int = 0
    realized_pnl: float = 0.0

    def __post_init__(self) -> None:
        for name in ("equity", "available_balance", "peak_equity", "daily_start_equity"):
            value = getattr(self, name)
            if not math.isfinite(value):
                raise ValueError(f"AccountRiskState.{name} must be finite, got {value}")
            if value < 0.0:
                raise ValueError(f"AccountRiskState.{name} must be non-negative, got {value}")
        if not math.isfinite(self.total_exposure) or self.total_exposure < 0.0:
            raise ValueError(
                f"AccountRiskState.total_exposure must be finite and non-negative, "
                f"got {self.total_exposure}"
            )
        if self.consecutive_losses < 0:
            raise ValueError(
                f"AccountRiskState.consecutive_losses must be non-negative, "
                f"got {self.consecutive_losses}"
            )


def _validated_positive(name: str, value: float | None) -> float | None:
    """Validate an optional strictly-positive constraint value."""
    if value is None:
        return None
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and positive when provided, got {value}")
    return value


@dataclass(frozen=True)
class TradingConstraints:
    """Normalized, venue-independent trading constraints.

    All fields optional: absent fields mean "unconstrained" — the engine never
    invents exchange-specific values. Populated by infrastructure from real
    exchange metadata when available.
    """

    min_quantity: float | None = None
    max_quantity: float | None = None
    quantity_step: float | None = None
    price_tick: float | None = None
    min_notional: float | None = None
    max_leverage: float | None = None

    def __post_init__(self) -> None:
        for attr in (
            "min_quantity",
            "max_quantity",
            "quantity_step",
            "price_tick",
            "min_notional",
            "max_leverage",
        ):
            _validated_positive(attr, getattr(self, attr))


@dataclass(frozen=True)
class RiskDecision:
    """Immutable outcome of a risk evaluation.

    Approved decisions carry complete trade parameters; rejected decisions
    carry ``rejection_reason`` plus whatever context was computable before the
    rejection. The engine NEVER places orders — downstream execution consumes
    this value.

    Attributes:
        approved: Convenience flag mirroring ``status``.
        status: APPROVED or REJECTED.
        rejection_reason: Machine-readable cause when rejected, else ``None``.
        entry_price: Entry used for calculations.
        stop_price: Protective stop level (constraint-rounded when applicable).
        target_price: Profit target level (constraint-rounded when applicable).
        risk_amount: Capital at risk if the stop is hit (before costs cap).
        requested_quantity: Quantity implied by pure percentage-of-equity risk,
            before balance/exposure/constraint shaping.
        position_quantity: Final approved quantity after all shaping.
        position_notional: Notional of the final quantity at entry.
        leverage: Effective leverage of the final position relative to
            available balance (<= 1 means spot-like).
        potential_reward: Expected profit at target including fee/slippage
            estimates.
        potential_loss: Expected loss at stop including fee/slippage estimates.
        reward_risk_ratio: ``potential_reward / potential_loss``.
        fees_estimate: Estimated round-trip fees at target.
        slippage_estimate: Estimated round-trip slippage cost at target.
        metadata: Full decision context (limits, caps trace, rates).
    """

    approved: bool
    status: RiskDecisionStatus
    rejection_reason: RejectionReason | None
    entry_price: float | None = None
    stop_price: float | None = None
    target_price: float | None = None
    risk_amount: float | None = None
    requested_quantity: float | None = None
    position_quantity: float | None = None
    position_notional: float | None = None
    leverage: float | None = None
    potential_reward: float | None = None
    potential_loss: float | None = None
    reward_risk_ratio: float | None = None
    fees_estimate: float | None = None
    slippage_estimate: float | None = None
    metadata: dict[str, object] = field(default_factory=dict)
