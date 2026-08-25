"""Execution-layer value types.

All models are frozen dataclasses in the style of :mod:`exchange.models`:
unknown venue facts stay ``None``, nothing is invented, and validation runs
eagerly in ``__post_init__``. These are the shapes a future persistence layer
consumes; they deliberately contain no venue SDK types.
"""

import math
from dataclasses import dataclass, field

from exchange.constraints import MarketConstraints
from exchange.models import Order, OrderSide, OrderType, PositionDirection
from execution_engine.base import (
    TERMINAL_EXECUTION_STATUSES,
    TERMINAL_LIFECYCLE_STATES,
    ExecutionStatus,
    OrderLifecycle,
    OrderRole,
    PositionAction,
    TimeInForce,
)


def _set(instance: object, name: str, value: object) -> None:
    """Assign to a frozen dataclass field from within __post_init__."""
    object.__setattr__(instance, name, value)


def _positive_float(value: object, name: str) -> float:
    """Require a finite, strictly positive number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a real number, got {type(value).__name__}")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{name} must be finite and positive, got {result}")
    return result


def _non_negative_float(value: object, name: str) -> float | None:
    """Accept None or a finite non-negative number; reject everything else."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a real number, got {type(value).__name__}")
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and non-negative, got {result}")
    return result


@dataclass(frozen=True)
class PlannedOrder:
    """One order as it will be (or was) submitted for an execution.

    Attributes:
        role: ENTRY, STOP_LOSS or TAKE_PROFIT.
        symbol: Instrument identifier, e.g. ``"BTC/USDT"``.
        side: BUY/SELL order side (distinct from position direction).
        order_type: MARKET, LIMIT, STOP_MARKET or STOP_LIMIT. For STOP_* the
            ``price`` field carries the trigger price, mirroring
            :meth:`exchange.base.ExchangePort.place_order`.
        quantity: Requested order quantity, always strictly positive.
        price: Limit price or stop trigger where the type requires one.
        time_in_force: Recorded policy intent; applied by adapters wherever a
            venue supports it.
        client_order_id: Deterministic idempotency-bearing identifier sent to
            the venue when supported.
    """

    role: OrderRole
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: float | None = None
    time_in_force: TimeInForce = TimeInForce.GTC
    client_order_id: str | None = None

    def __post_init__(self) -> None:
        if not self.symbol or not isinstance(self.symbol, str):
            raise ValueError("PlannedOrder.symbol must be a non-empty string")
        _set(self, "quantity", _positive_float(self.quantity, "PlannedOrder.quantity"))
        requires_price = self.order_type in (
            OrderType.LIMIT,
            OrderType.STOP_LIMIT,
            OrderType.STOP_MARKET,
        )
        if requires_price and self.price is None:
            raise ValueError(f"PlannedOrder of type {self.order_type.value} requires a price")
        _set(self, "price", _non_negative_float(self.price, "PlannedOrder.price"))


@dataclass(frozen=True)
class PlanAdjustment:
    """One explicit, traceable change made while shaping a plan.

    Exchange constraints may require numeric rounding; every such change is
    recorded here rather than silently applied. The approved RiskDecision
    itself is never mutated; adjustments live only on the plan.
    """

    field: str
    original: float
    adjusted: float
    reason: str

    def __post_init__(self) -> None:
        if not self.field:
            raise ValueError("PlanAdjustment.field must be non-empty")
        if not self.reason:
            raise ValueError("PlanAdjustment.reason must be non-empty")
        _set(self, "original", float(self.original))
        _set(self, "adjusted", float(self.adjusted))


@dataclass(frozen=True)
class ExecutionPlan:
    """Explicit plan derived from one approved RiskDecision.

    Describes exactly what will be submitted: entry plus optional protective
    orders, each with side/type/quantity/price/time-in-force/client id, along
    with the position-level classification and every constraint-driven
    adjustment. Immutable and traceable.
    """

    execution_id: str
    symbol: str
    direction: PositionDirection
    position_action: PositionAction
    requested_quantity: float
    entry: PlannedOrder
    stop_loss: PlannedOrder | None = None
    take_profit: PlannedOrder | None = None
    adjustments: tuple[PlanAdjustment, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.execution_id:
            raise ValueError("ExecutionPlan.execution_id must be non-empty")
        if not self.symbol:
            raise ValueError("ExecutionPlan.symbol must be non-empty")
        _set(
            self,
            "requested_quantity",
            _positive_float(self.requested_quantity, "ExecutionPlan.requested_quantity"),
        )
        for name in ("entry", "stop_loss", "take_profit"):
            planned = getattr(self, name)
            if planned is not None and planned.symbol != self.symbol:
                raise ValueError(
                    f"ExecutionPlan.{name}.symbol {planned.symbol!r} != plan symbol "
                    f"{self.symbol!r}"
                )


@dataclass(frozen=True)
class LifecycleEvent:
    """One recorded lifecycle transition of a tracked order."""

    from_state: OrderLifecycle
    to_state: OrderLifecycle
    timestamp_ms: int
    note: str | None = None


@dataclass(frozen=True)
class OrderRecord:
    """Immutable snapshot of one tracked order at a point in time.

    Attributes:
        plan: The planned order this record tracks.
        state: Current execution-layer lifecycle state.
        venue_order_id: Venue-assigned id once known, else ``None``.
        requested_quantity: Quantity originally planned for submission.
        filled_quantity: Authoritative filled amount when known.
        remaining_quantity: Requested minus filled (never negative).
        average_fill_price: Venue-reported average fill price when known.
        last_known_order: Latest authoritative venue :class:`~exchange.models.Order`
            snapshot; ``None`` when the venue has not confirmed anything.
        events: Full transition history (append-only).
        created_at_ms: When tracking started.
        updated_at_ms: When this snapshot's state was last changed.
        message: Sanitized diagnostic from the last transition, if any.
    """

    plan: PlannedOrder
    state: OrderLifecycle
    venue_order_id: str | None
    requested_quantity: float
    filled_quantity: float
    average_fill_price: float | None
    last_known_order: Order | None
    events: tuple[LifecycleEvent, ...]
    created_at_ms: int
    updated_at_ms: int
    message: str | None = None

    @property
    def remaining_quantity(self) -> float:
        """Quantity not yet filled."""
        return round(max(0.0, self.requested_quantity - self.filled_quantity), 12)

    @property
    def is_terminal(self) -> bool:
        """True when no further transitions are possible without reconciliation."""
        return self.state in TERMINAL_LIFECYCLE_STATES

    @property
    def is_unknown(self) -> bool:
        """True when outcome at the venue cannot currently be determined."""
        return self.state is OrderLifecycle.UNKNOWN


@dataclass(frozen=True)
class ExecutionContext:
    """Caller-supplied context for one execution request.

    Attributes:
        symbol: Instrument to trade; must be non-empty.
        direction: Intended position direction (LONG/SHORT) from the approved
            decision. Order sides are derived from this, never passed in.
        idempotency_key: Optional stable key. When present, execution and
            client order ids derive deterministically from it and duplicate
            requests return the recorded result instead of resubmitting.
        current_position_side: Side of the existing same-symbol position when
            known; ``None`` means "no known position" (spot-style OPEN).
        current_position_quantity: Absolute size of that position.
        constraints: Optional pre-fetched venue constraints; when omitted the
            engine queries ``ExchangePort.get_market`` itself.
        entry_order_type: MARKET (default) or LIMIT for the entry leg.
        time_in_force: Recorded time-in-force intent for all planned orders.
        timestamp_ms: Optional fixed clock value for deterministic tests.
        metadata: Free-form, secret-free diagnostics propagated to results.
    """

    symbol: str
    direction: PositionDirection
    idempotency_key: str | None = None
    current_position_side: PositionDirection | None = None
    current_position_quantity: float | None = None
    constraints: MarketConstraints | None = None
    entry_order_type: OrderType = OrderType.MARKET
    time_in_force: TimeInForce = TimeInForce.GTC
    timestamp_ms: int | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.symbol or not isinstance(self.symbol, str):
            raise ValueError("ExecutionContext.symbol must be a non-empty string")
        if self.idempotency_key is not None and (
            not self.idempotency_key or not isinstance(self.idempotency_key, str)
        ):
            raise ValueError("ExecutionContext.idempotency_key must be a non-empty string")
        if self.entry_order_type not in (OrderType.MARKET, OrderType.LIMIT):
            raise ValueError(
                f"ExecutionContext.entry_order_type must be MARKET or LIMIT, "
                f"got {self.entry_order_type}"
            )
        _set(
            self,
            "current_position_quantity",
            _non_negative_float(
                self.current_position_quantity, "ExecutionContext.current_position_quantity"
            ),
        )
        if self.timestamp_ms is not None:
            if isinstance(self.timestamp_ms, bool) or not isinstance(self.timestamp_ms, int):
                raise ValueError("ExecutionContext.timestamp_ms must be an integer ms value")


@dataclass(frozen=True)
class ExecutionResult:
    """Immutable outcome of one execution request.

    Carries everything a future persistence layer needs: identification,
    requested vs filled quantity, average fill price, per-order records with
    full lifecycle history, reconciliation flags and sanitized diagnostics.
    """

    execution_id: str
    symbol: str
    status: ExecutionStatus
    requested_quantity: float
    filled_quantity: float
    average_fill_price: float | None
    direction: PositionDirection | None = None
    position_action: PositionAction | None = None
    entry_order: OrderRecord | None = None
    stop_order: OrderRecord | None = None
    target_order: OrderRecord | None = None
    plan: ExecutionPlan | None = None
    reconciliation_required: bool = False
    created_at_ms: int = 0
    completed_at_ms: int | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def remaining_quantity(self) -> float:
        """Entry quantity not yet filled."""
        return round(max(0.0, self.requested_quantity - self.filled_quantity), 12)

    @property
    def is_terminal(self) -> bool:
        """True when no further automatic action will be taken."""
        return self.status in TERMINAL_EXECUTION_STATUSES

    @property
    def requires_reconciliation(self) -> bool:
        """Alias kept explicit for callers scanning results."""
        return self.reconciliation_required

