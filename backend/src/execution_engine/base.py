"""Execution domain primitives: enums, the order-lifecycle state machine and
pure direction/side mappings.

Everything here is venue-independent and side-effect free. The lifecycle
machine is deliberately strict: transitions not present in
``LIFECYCLE_TRANSITIONS`` raise :class:`InvalidTransitionError`, ``UNKNOWN``
can only be left via explicit reconciliation, and terminal states accept no
further transitions. This is what makes "never blindly resubmit after an
UNKNOWN result" enforceable instead of merely conventional.
"""

from enum import Enum

from exchange.models import OrderSide, OrderStatus, PositionDirection


class ExecutionStatus(Enum):
    """Outcome of one :meth:`ExecutionEngine.execute` request.

    The first five statuses guarantee zero order submissions. UNKNOWN means
    the entry submission outcome is undeterminable; it always carries
    ``reconciliation_required = True`` and blocks further submissions on the
    symbol until reconciled.
    """

    PENDING = "pending"
    REJECTED_BY_RISK = "rejected_by_risk"
    INVALID_REQUEST = "invalid_request"
    UNSUPPORTED_OPERATION = "unsupported_operation"
    BLOCKED_RECONCILIATION = "blocked_reconciliation"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


#: Execution statuses after which no further automatic action occurs.
#: UNKNOWN is deliberately absent: it requires reconciliation first.
TERMINAL_EXECUTION_STATUSES: frozenset[ExecutionStatus] = frozenset(
    {
        ExecutionStatus.REJECTED_BY_RISK,
        ExecutionStatus.INVALID_REQUEST,
        ExecutionStatus.UNSUPPORTED_OPERATION,
        ExecutionStatus.FILLED,
        ExecutionStatus.REJECTED,
        ExecutionStatus.CANCELLED,
    }
)


class OrderRole(Enum):
    """Role an order plays inside one execution."""

    ENTRY = "entry"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class PositionAction(Enum):
    """What the execution does to the existing position on the symbol.

    Derived from the intended :class:`~exchange.models.PositionDirection` and
    the known same-symbol position; order side (BUY/SELL) never determines
    this on its own.
    """

    OPEN = "open"
    INCREASE = "increase"
    REDUCE = "reduce"
    CLOSE = "close"


class TimeInForce(Enum):
    """Time-in-force policies; recorded intent where a venue supports them."""

    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"
    GTD = "gtd"


class OrderLifecycle(Enum):
    """Execution-layer lifecycle of one order.

    Superset of the venue-level :class:`~exchange.models.OrderStatus`: adds
    pre-submission states (PENDING, SUBMITTING), the explicit
    CANCEL_REQUESTED state, and treats UNKNOWN as its own state — never as a
    synonym for REJECTED. UNKNOWN means "the system cannot currently determine
    what happened at the venue" and is exitable only through reconciliation.
    """

    PENDING = "pending"
    SUBMITTING = "submitting"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


#: Allowed ``OrderLifecycle`` transitions. Terminal states map to empty sets.
#: ``UNKNOWN`` has no automatic outgoing edges: only reconciliation moves an
#: order out of it, using the same validated transition table.
LIFECYCLE_TRANSITIONS: dict[OrderLifecycle, frozenset[OrderLifecycle]] = {
    OrderLifecycle.PENDING: frozenset({OrderLifecycle.SUBMITTING}),
    OrderLifecycle.SUBMITTING: frozenset(
        {
            OrderLifecycle.ACCEPTED,
            OrderLifecycle.PARTIALLY_FILLED,
            OrderLifecycle.FILLED,
            OrderLifecycle.CANCELLED,
            OrderLifecycle.REJECTED,
            OrderLifecycle.EXPIRED,
            OrderLifecycle.UNKNOWN,
        }
    ),
    OrderLifecycle.ACCEPTED: frozenset(
        {
            OrderLifecycle.PARTIALLY_FILLED,
            OrderLifecycle.FILLED,
            OrderLifecycle.CANCEL_REQUESTED,
            OrderLifecycle.CANCELLED,
            OrderLifecycle.EXPIRED,
            OrderLifecycle.UNKNOWN,
        }
    ),
    OrderLifecycle.PARTIALLY_FILLED: frozenset(
        {
            OrderLifecycle.FILLED,
            OrderLifecycle.CANCEL_REQUESTED,
            OrderLifecycle.CANCELLED,
            OrderLifecycle.EXPIRED,
            OrderLifecycle.UNKNOWN,
        }
    ),
    # A cancel request may lose a race with a fill or further partial fills;
    # the authoritative post-cancel state decides which edge applies.
    OrderLifecycle.CANCEL_REQUESTED: frozenset(
        {
            OrderLifecycle.CANCELLED,
            OrderLifecycle.FILLED,
            OrderLifecycle.PARTIALLY_FILLED,
            OrderLifecycle.EXPIRED,
            OrderLifecycle.UNKNOWN,
        }
    ),
    OrderLifecycle.UNKNOWN: frozenset(
        {
            OrderLifecycle.ACCEPTED,
            OrderLifecycle.PARTIALLY_FILLED,
            OrderLifecycle.FILLED,
            OrderLifecycle.CANCELLED,
            OrderLifecycle.REJECTED,
            OrderLifecycle.EXPIRED,
        }
    ),
    OrderLifecycle.FILLED: frozenset(),
    OrderLifecycle.CANCELLED: frozenset(),
    OrderLifecycle.REJECTED: frozenset(),
    OrderLifecycle.EXPIRED: frozenset(),
}

TERMINAL_LIFECYCLE_STATES: frozenset[OrderLifecycle] = frozenset(
    {state for state, targets in LIFECYCLE_TRANSITIONS.items() if not targets}
)


class InvalidTransitionError(RuntimeError):
    """Raised when an order-lifecycle transition is not allowed."""

    def __init__(self, current: OrderLifecycle, target: OrderLifecycle) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Illegal order lifecycle transition {current.value} -> {target.value}")


def validate_transition(current: OrderLifecycle, target: OrderLifecycle) -> bool:
    """Validate one lifecycle transition.

    Re-applying the current state is an accepted no-op (polling and repeated
    cancellation attempts must not explode); everything else must appear in
    :data:`LIFECYCLE_TRANSITIONS`.

    Returns:
        ``True`` when the state changed, ``False`` for a no-op self-transition.

    Raises:
        InvalidTransitionError: On any non-trivial disallowed transition.
    """
    if current is target:
        return False
    if target in LIFECYCLE_TRANSITIONS[current]:
        return True
    raise InvalidTransitionError(current, target)


def lifecycle_from_status(status: OrderStatus) -> OrderLifecycle:
    """Map a normalized venue status onto the execution-layer lifecycle."""
    mapping: dict[OrderStatus, OrderLifecycle] = {
        OrderStatus.OPEN: OrderLifecycle.ACCEPTED,
        OrderStatus.PARTIALLY_FILLED: OrderLifecycle.PARTIALLY_FILLED,
        OrderStatus.FILLED: OrderLifecycle.FILLED,
        OrderStatus.CANCELED: OrderLifecycle.CANCELLED,
        OrderStatus.REJECTED: OrderLifecycle.REJECTED,
        OrderStatus.EXPIRED: OrderLifecycle.EXPIRED,
        OrderStatus.UNKNOWN: OrderLifecycle.UNKNOWN,
    }
    return mapping[status]


def entry_side(direction: PositionDirection) -> OrderSide:
    """Order side that opens/increases a position of ``direction``.

    A BUY opens/increases LONG (or reduces/closes SHORT); a SELL mirrors it.
    """
    if direction is PositionDirection.LONG:
        return OrderSide.BUY
    return OrderSide.SELL


def protective_side(direction: PositionDirection) -> OrderSide:
    """Order side of stop-loss/take-profit orders protecting ``direction``.

    A SELL protects/reduces a LONG; a BUY protects/reduces a SHORT.
    """
    return OrderSide.SELL if direction is PositionDirection.LONG else OrderSide.BUY


def classify_position_action(
    intended_direction: PositionDirection,
    requested_quantity: float,
    current_side: PositionDirection | None,
    current_quantity: float | None,
) -> PositionAction:
    """Classify what an execution in ``intended_direction`` does to a position.

    Args:
        intended_direction: Direction the approved decision trades toward.
        requested_quantity: Planned execution quantity.
        current_side: Side of the existing same-symbol position, if any.
        current_quantity: Absolute size of the existing position, if any.

    Returns:
        OPEN with no known existing position; INCREASE when trading along the
        existing side; REDUCE when trading against it by less than its size;
        CLOSE when trading against it by at least its size. Flipping beyond a
        close classifies as CLOSE — this engine never auto-flips.
    """
    if current_side is None or current_quantity is None or current_quantity <= 0.0:
        return PositionAction.OPEN
    if current_side is intended_direction:
        return PositionAction.INCREASE
    if requested_quantity < current_quantity:
        return PositionAction.REDUCE
    return PositionAction.CLOSE
