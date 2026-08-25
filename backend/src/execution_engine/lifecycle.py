"""Explicit order-lifecycle tracking.

:class:`OrderTracker` owns the lifecycle of exactly one planned order. All
state changes flow through the validated transition table in
:mod:`execution_engine.base`, so an illegal move raises immediately instead of
corrupting execution history. Snapshots exposed via :attr:`record` are frozen
:data:`~execution_engine.models.OrderRecord` values safe to hand to callers,
logs, and the future persistence layer.
"""

import math

from exchange.models import Order, OrderSubmission, SubmissionState
from execution_engine.base import (
    OrderLifecycle,
    lifecycle_from_status,
    validate_transition,
)
from execution_engine.models import LifecycleEvent, OrderRecord, PlannedOrder

_QUANTITY_EPS = 1e-12


class OrderTracker:
    """Tracks one order from planning through a terminal or reconciled state."""

    def __init__(self, plan: PlannedOrder, now_ms: int) -> None:
        self._plan = plan
        self._state = OrderLifecycle.PENDING
        self._venue_order_id: str | None = None
        self._filled = 0.0
        self._average_fill_price: float | None = None
        self._last_known_order: Order | None = None
        self._events: list[LifecycleEvent] = []
        self._created_at = now_ms
        self._updated_at = now_ms
        self._message: str | None = None

    # ----- introspection -----

    @property
    def plan(self) -> PlannedOrder:
        return self._plan

    @property
    def state(self) -> OrderLifecycle:
        return self._state

    @property
    def role_client_order_id(self) -> str | None:
        return self._plan.client_order_id

    @property
    def record(self) -> OrderRecord:
        """Frozen snapshot of the current tracking state."""
        return OrderRecord(
            plan=self._plan,
            state=self._state,
            venue_order_id=self._venue_order_id,
            requested_quantity=self._plan.quantity,
            filled_quantity=self._filled,
            average_fill_price=self._average_fill_price,
            last_known_order=self._last_known_order,
            events=tuple(self._events),
            created_at_ms=self._created_at,
            updated_at_ms=self._updated_at,
            message=self._message,
        )

    @property
    def filled_quantity(self) -> float:
        return self._filled

    # ----- transitions -----

    def mark_submitting(self, now_ms: int) -> None:
        """Move PENDING -> SUBMITTING right before calling the port."""
        self._transition(OrderLifecycle.SUBMITTING, now_ms)

    def mark_cancel_requested(self, now_ms: int) -> None:
        """Record that cancellation has been requested at the venue."""
        self._transition(OrderLifecycle.CANCEL_REQUESTED, now_ms)

    def apply_submission(self, submission: OrderSubmission, now_ms: int) -> None:
        """Incorporate the outcome of one place_order attempt.

        ACCEPTED submissions adopt whatever authoritative order snapshot the
        venue returned (possibly already partially/fully filled). REJECTED and
        UNKNOWN submissions carry no authoritative order; UNKNOWN is recorded
        as its own lifecycle state and left for reconciliation.
        """
        if submission.state is SubmissionState.ACCEPTED:
            if submission.order is None:
                # An acceptance without any order snapshot cannot be trusted;
                # treat like UNKNOWN rather than inventing state.
                self._transition(OrderLifecycle.UNKNOWN, now_ms, submission.message)
                return
            self._apply_authoritative_order(submission.order, now_ms)
            return
        if submission.state is SubmissionState.REJECTED:
            self._transition(OrderLifecycle.REJECTED, now_ms, submission.message)
            return
        self._transition(OrderLifecycle.UNKNOWN, now_ms, submission.message)

    def apply_order(self, order: Order, now_ms: int, *, note: str | None = None) -> None:
        """Apply an authoritative venue order observation (poll/fetch)."""
        self._apply_authoritative_order(order, now_ms, note=note)

    def reconcile(self, order: Order | None, now_ms: int, note: str | None = None) -> bool:
        """Resolve this order using authoritative exchange information.

        This is the only path allowed to move an order out of UNKNOWN. Passing
        ``None`` means the venue reports no such order; the state stays
        UNKNOWN (absence of evidence is not evidence of rejection).

        Returns:
            ``True`` when the state changed.
        """
        if order is None:
            self._message = note or "reconciliation found no venue order"
            self._updated_at = now_ms
            return False
        before = self._state
        self._apply_authoritative_order(order, now_ms, note=note or "reconciled")
        return before is not self._state

    def force_state(
        self, target: OrderLifecycle, now_ms: int, message: str | None = None
    ) -> None:
        """Explicitly move to ``target`` through the validated transition table.

        Used only by reconciliation/cancellation flows when an operation's
        outcome is undeterminable; still refuses illegal transitions.
        """
        self._transition(target, now_ms, message)

    # ----- internals -----

    def _transition(
        self, target: OrderLifecycle, now_ms: int, message: str | None = None
    ) -> bool:
        """Validate and apply a state change, recording an event."""
        changed = validate_transition(self._state, target)
        if not changed:
            self._message = message if message is not None else self._message
            return False
        self._events.append(
            LifecycleEvent(
                from_state=self._state, to_state=target, timestamp_ms=now_ms, note=message
            )
        )
        self._state = target
        self._updated_at = now_ms
        self._message = message
        return True

    def _apply_authoritative_order(
        self, order: Order, now_ms: int, *, note: str | None = None
    ) -> None:
        """Adopt an authoritative venue snapshot: ids, fills, then state."""
        self._last_known_order = order
        if order.id is not None:
            self._venue_order_id = order.id
        if order.filled_quantity > self._filled + _QUANTITY_EPS:
            self._filled = min(order.filled_quantity, self._plan.quantity)
        elif order.filled_quantity < self._filled - _QUANTITY_EPS:
            # Authoritative data may legitimately revise fills downward
            # (e.g. partial-fill corrections); trust the venue.
            self._filled = min(order.filled_quantity, self._plan.quantity)
        if order.average_fill_price is not None:
            self._average_fill_price = order.average_fill_price
        target = lifecycle_from_status(order.status)
        message = note
        if math.isclose(self._filled, self._plan.quantity, abs_tol=_QUANTITY_EPS):
            target = OrderLifecycle.FILLED
        self._transition(target, now_ms, message)
