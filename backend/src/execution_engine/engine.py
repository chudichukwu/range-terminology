"""ExecutionEngine: RiskDecision + ExecutionContext -> ExecutionResult.

The engine is the only component that turns approved risk decisions into
exchange orders. It never generates signals, never recomputes strategy risk,
never overrides an approved decision, and never sees a venue SDK: all I/O
flows through :class:`~exchange.base.ExchangePort`.

Safety invariants enforced here:

1. Rejected decisions produce zero order submissions.
2. UNKNOWN submissions are terminal for the call: no automatic retry, the
   execution is flagged ``reconciliation_required`` and further submissions
   on the symbol are blocked until reconciliation resolves it.
3. Protective orders are sized to actual fills only — never to the planned
   quantity.
4. Approved risk parameters are never silently modified; constraint-driven
   rounding is explicit via :class:`~execution_engine.models.PlanAdjustment`.
5. Capabilities are checked before any submission; unsupported operations
   abort with zero submissions.
"""

import dataclasses
import math
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from exchange.base import ExchangePort
from exchange.constraints import MarketConstraints
from exchange.errors import ExchangeError, ExchangeErrorCode
from exchange.models import (
    Order,
    OrderSubmission,
    OrderType,
    Position,
    SubmissionState,
)
from execution_engine.base import (
    TERMINAL_EXECUTION_STATUSES,
    TERMINAL_LIFECYCLE_STATES,
    ExecutionStatus,
    OrderLifecycle,
    OrderRole,
    PositionAction,
    classify_position_action,
    entry_side,
    protective_side,
)
from execution_engine.lifecycle import OrderTracker
from execution_engine.models import (
    ExecutionContext,
    ExecutionPlan,
    ExecutionResult,
    PlanAdjustment,
    PlannedOrder,
)
from execution_engine.reconciliation import ExecutionReconciler, ReconciliationOutcome
from risk_engine.base import RiskDecision, RiskDecisionStatus

_FILL_EPS = 1e-12

#: Entry-order lifecycle -> overall execution status projection.
_LIFECYCLE_TO_EXECUTION_STATUS: dict[OrderLifecycle, ExecutionStatus] = {
    OrderLifecycle.PENDING: ExecutionStatus.PENDING,
    OrderLifecycle.SUBMITTING: ExecutionStatus.PENDING,
    OrderLifecycle.ACCEPTED: ExecutionStatus.SUBMITTED,
    OrderLifecycle.PARTIALLY_FILLED: ExecutionStatus.PARTIALLY_FILLED,
    OrderLifecycle.FILLED: ExecutionStatus.FILLED,
    OrderLifecycle.CANCEL_REQUESTED: ExecutionStatus.SUBMITTED,
    OrderLifecycle.CANCELLED: ExecutionStatus.CANCELLED,
    OrderLifecycle.REJECTED: ExecutionStatus.REJECTED,
    OrderLifecycle.EXPIRED: ExecutionStatus.CANCELLED,
    OrderLifecycle.UNKNOWN: ExecutionStatus.UNKNOWN,
}


def _default_clock_ms() -> int:
    return time.time_ns() // 1_000_000


def _default_id_generator() -> str:
    return uuid.uuid4().hex


class _PlanRefusal(Exception):
    """Internal signal: venue constraints make the approved plan untradable.

    Carries a pre-sanitized detail dict for the resulting INVALID_REQUEST
    result. Raised only before any submission occurs.
    """

    def __init__(self, detail: dict[str, object]) -> None:
        self.detail = detail
        super().__init__(str(detail))


@dataclass
class _ExecutionTrack:
    """Internal mutable book-keeping for one execution request."""

    execution_id: str
    idempotency_key: str
    context: ExecutionContext
    result: ExecutionResult
    entry_tracker: OrderTracker | None = None
    stop_tracker: OrderTracker | None = None
    target_tracker: OrderTracker | None = None
    resolved: bool = True
    metadata: dict[str, object] = field(default_factory=dict)


class ExecutionEngine:
    """Executes approved risk decisions through an ExchangePort.

    Deterministic when external venue state is fixed: timestamps and ids are
    injectable (``clock_ms`` / ``id_generator``), so tests run fully offline.
    """

    def __init__(
        self,
        exchange: ExchangePort,
        *,
        clock_ms: Callable[[], int] | None = None,
        id_generator: Callable[[], str] | None = None,
    ) -> None:
        self._exchange = exchange
        self._clock_ms = clock_ms if clock_ms is not None else _default_clock_ms
        self._id_generator = id_generator if id_generator is not None else _default_id_generator
        self._executions: dict[str, _ExecutionTrack] = {}
        self._symbol_unknowns: dict[str, str] = {}

    # ----- public API -----

    def execute(self, decision: RiskDecision, context: ExecutionContext) -> ExecutionResult:
        """Turn one risk decision into orders per ``context``.

        Returns:
            An immutable :class:`ExecutionResult` describing exactly what
            happened. Domain-level refusals (rejected decision, invalid
            request, unsupported capability, blocked symbol) are results with
            zero submissions, never exceptions.

        Raises:
            ValueError: Only for structurally invalid arguments already
                rejected by model validation.
        """
        now_ms = context.timestamp_ms if context.timestamp_ms is not None else self._clock_ms()
        key = context.idempotency_key or self._id_generator()

        duplicate = self._executions.get(key)
        if duplicate is not None:
            return self._annotate_duplicate(duplicate)

        blocked_by = self._symbol_unknowns.get(context.symbol)
        if blocked_by is not None:
            return self._blocked_result(key, context, blocked_by, now_ms)

        track = _ExecutionTrack(
            execution_id=self._execution_id_for(key),
            idempotency_key=key,
            context=context,
            result=self._empty_result(self._execution_id_for(key), context, now_ms),
        )
        self._executions[key] = track

        if not decision.approved or decision.status is not RiskDecisionStatus.APPROVED:
            return self._finish_noop(
                track,
                ExecutionStatus.REJECTED_BY_RISK,
                now_ms,
                {
                    "reason": "risk_decision_not_approved",
                    "rejection_reason": (
                        decision.rejection_reason.value if decision.rejection_reason else None
                    ),
                },
            )

        invalid = self._validate_decision(decision, context)
        if invalid is not None:
            return self._finish_noop(track, ExecutionStatus.INVALID_REQUEST, now_ms, invalid)

        unsupported = self._check_capabilities(context)
        if unsupported is not None:
            return self._finish_noop(
                track, ExecutionStatus.UNSUPPORTED_OPERATION, now_ms, unsupported
            )

        constraints, constraint_error = self._resolve_constraints(context)
        if constraint_error is not None:
            return self._finish_noop(
                track, ExecutionStatus.INVALID_REQUEST, now_ms, constraint_error
            )

        try:
            plan = self._build_plan(track, decision, context, constraints)
        except _PlanRefusal as refusal:
            return self._finish_noop(track, ExecutionStatus.INVALID_REQUEST, now_ms, refusal.detail)
        position_action = classify_position_action(
            context.direction,
            plan.requested_quantity,
            context.current_position_side,
            context.current_position_quantity,
        )
        plan = self._with_position_action(plan, position_action)
        track.metadata["plan"] = plan

        return self._submit_entry(track, plan, now_ms)

    def get_execution(self, idempotency_key: str) -> ExecutionResult | None:
        """Latest recorded result for ``idempotency_key``, if any."""
        track = self._executions.get(idempotency_key)
        return track.result if track is not None else None

    def has_unresolved_unknown(self, symbol: str) -> bool:
        """True while submissions on ``symbol`` are blocked by an UNKNOWN."""
        return symbol in self._symbol_unknowns

    # ----- validation helpers -----

    @staticmethod
    def _validate_decision(
        decision: RiskDecision, context: ExecutionContext
    ) -> dict[str, object] | None:
        """Structural checks on an approved decision before anything is sent."""
        problems: list[str] = []
        entry = decision.entry_price
        if entry is None or not math.isfinite(entry) or entry <= 0.0:
            problems.append("entry_price_missing_or_invalid")
        quantity = decision.position_quantity
        if quantity is None or not math.isfinite(quantity) or quantity <= 0.0:
            problems.append("position_quantity_missing_or_invalid")
        stop = decision.stop_price
        if stop is None or not math.isfinite(stop) or stop <= 0.0:
            problems.append("stop_price_missing_or_invalid")
        target = decision.target_price
        if target is None or not math.isfinite(target) or target <= 0.0:
            problems.append("target_price_missing_or_invalid")
        if problems:
            return {"reason": "invalid_execution_request", "problems": problems}
        assert entry is not None and quantity is not None and stop is not None
        assert target is not None
        long = context.direction.value == "long"
        if long and not (stop < entry < target):
            return {
                "reason": "stop_target_side_violation",
                "expected": "stop < entry < target for LONG",
            }
        if not long and not (target < entry < stop):
            return {
                "reason": "stop_target_side_violation",
                "expected": "target < entry < stop for SHORT",
            }
        return None

    def _check_capabilities(self, context: ExecutionContext) -> dict[str, object] | None:
        """Refuse unsupported operations before any submission occurs."""
        caps = self._exchange.capabilities
        required: list[str] = []
        if context.entry_order_type is OrderType.MARKET and not caps.supports("market_orders"):
            required.append("market_orders")
        if context.entry_order_type is OrderType.LIMIT and not caps.supports("limit_orders"):
            required.append("limit_orders")
        # A protective stop is mandatory for every approved range trade;
        # without stop support the trade must not be entered at all.
        if not caps.supports("stop_orders"):
            required.append("stop_orders")
        if not caps.supports("limit_orders"):
            required.append("limit_orders")
        if required:
            return {
                "reason": "unsupported_operation",
                "capabilities": sorted(set(required)),
                "venue": self._exchange.venue_id,
            }
        return None

    def _resolve_constraints(
        self, context: ExecutionContext
    ) -> tuple[MarketConstraints | None, dict[str, object] | None]:
        """Use caller-provided constraints or fetch them from the port."""
        if context.constraints is not None:
            return context.constraints, None
        try:
            return self._exchange.get_market(context.symbol), None
        except ExchangeError as exc:
            return None, {
                "reason": "market_constraints_unavailable",
                "error_code": exc.code.value,
                "message": exc.message,
            }

    # ----- planning -----

    @staticmethod
    def _needs_price(context: ExecutionContext) -> bool:
        """Limit entries need a price; market entries do not."""
        return context.entry_order_type is OrderType.LIMIT

    def _build_plan(
        self,
        track: _ExecutionTrack,
        decision: RiskDecision,
        context: ExecutionContext,
        constraints: MarketConstraints | None,
    ) -> ExecutionPlan:
        """Derive an explicit, adjustment-traced plan from approved parameters.

        Raises:
            _PlanRefusal: When venue constraints make the approved quantity
                untradable (below minimums or shaped to zero); nothing has
                been submitted at that point and execute() converts this into
                an explicit INVALID_REQUEST result.
        """
        adjustments: list[PlanAdjustment] = []
        quantity = decision.position_quantity
        assert quantity is not None
        shaped_quantity, qty_notes = self._shape_quantity(quantity, constraints)
        if shaped_quantity <= 0.0:
            raise _PlanRefusal(
                {
                    "reason": "invalid_execution_request",
                    "problems": ["quantity_shaped_to_zero"],
                    "requested_quantity": quantity,
                }
            )
        if "quantity_below_min" in qty_notes:
            raise _PlanRefusal(
                {
                    "reason": "invalid_execution_request",
                    "problems": ["quantity_below_min"],
                    "requested_quantity": quantity,
                    "shaped_quantity": shaped_quantity,
                }
            )
        for note in qty_notes:
            adjustments.append(
                PlanAdjustment(
                    field="entry.quantity", original=quantity, adjusted=shaped_quantity,
                    reason=note,
                )
            )
        entry_price = decision.entry_price
        stop_price = decision.stop_price
        target_price = decision.target_price
        assert entry_price is not None and stop_price is not None and target_price is not None

        if (
            constraints is not None
            and constraints.min_notional is not None
            and shaped_quantity * entry_price < constraints.min_notional
        ):
            raise _PlanRefusal(
                {
                    "reason": "invalid_execution_request",
                    "problems": ["notional_below_min"],
                    "notional": shaped_quantity * entry_price,
                    "min_notional": constraints.min_notional,
                }
            )

        planned_entry_price = (
            self._round_nearest_tick(entry_price, constraints)
            if self._needs_price(context)
            else None
        )
        if planned_entry_price is not None and not math.isclose(
            planned_entry_price, entry_price, abs_tol=_FILL_EPS
        ):
            adjustments.append(
                PlanAdjustment(
                    field="entry.price", original=entry_price,
                    adjusted=planned_entry_price, reason="price_tick_rounding",
                )
            )
        planned_stop = self._round_away(stop_price, entry_price, constraints)
        if not math.isclose(planned_stop, stop_price, abs_tol=_FILL_EPS):
            adjustments.append(
                PlanAdjustment(
                    field="stop_loss.price", original=stop_price,
                    adjusted=planned_stop, reason="price_tick_rounding_preserving_risk",
                )
            )
        planned_target = self._round_toward(target_price, entry_price, constraints)
        if not math.isclose(planned_target, target_price, abs_tol=_FILL_EPS):
            adjustments.append(
                PlanAdjustment(
                    field="take_profit.price", original=target_price,
                    adjusted=planned_target, reason="price_tick_rounding_reducing_reward",
                )
            )

        side = entry_side(context.direction)
        protective = protective_side(context.direction)
        key = track.idempotency_key
        tif = context.time_in_force
        entry = PlannedOrder(
            role=OrderRole.ENTRY,
            symbol=context.symbol,
            side=side,
            order_type=context.entry_order_type,
            quantity=shaped_quantity,
            price=planned_entry_price,
            time_in_force=tif,
            client_order_id=f"{key}-entry",
        )
        stop = PlannedOrder(
            role=OrderRole.STOP_LOSS,
            symbol=context.symbol,
            side=protective,
            order_type=OrderType.STOP_MARKET,
            quantity=shaped_quantity,
            price=planned_stop,
            time_in_force=tif,
            client_order_id=f"{key}-stop",
        )
        take_profit = PlannedOrder(
            role=OrderRole.TAKE_PROFIT,
            symbol=context.symbol,
            side=protective,
            order_type=OrderType.LIMIT,
            quantity=shaped_quantity,
            price=planned_target,
            time_in_force=tif,
            client_order_id=f"{key}-target",
        )
        return ExecutionPlan(
            execution_id=track.execution_id,
            symbol=context.symbol,
            direction=context.direction,
            position_action=PositionAction.OPEN,
            requested_quantity=shaped_quantity,
            entry=entry,
            stop_loss=stop,
            take_profit=take_profit,
            adjustments=tuple(adjustments),
            metadata={
                "venue": self._exchange.venue_id,
                "requested_quantity_pre_shaping": quantity,
                "decision_reward_risk_ratio": decision.reward_risk_ratio,
            },
        )

    @staticmethod
    def _with_position_action(plan: ExecutionPlan, action: PositionAction) -> ExecutionPlan:
        """Return the plan with its final position-action classification."""
        return dataclasses.replace(plan, position_action=action)

    def _shape_quantity(
        self, quantity: float, constraints: MarketConstraints | None
    ) -> tuple[float, list[str]]:
        """Shape entry quantity to venue constraints; notes become adjustments."""
        if constraints is None:
            return quantity, []
        shaped = quantity
        notes: list[str] = []
        if constraints.max_quantity is not None and shaped > constraints.max_quantity:
            shaped = constraints.max_quantity
            notes.append("max_quantity_clamp")
        if constraints.quantity_step is not None:
            stepped = (
                math.floor(shaped / constraints.quantity_step + 1e-12)
                * constraints.quantity_step
            )
            stepped = round(stepped, 12)
            if stepped < shaped:
                notes.append("quantity_step_rounding")
                shaped = stepped
            else:
                shaped = stepped
        if constraints.min_quantity is not None and shaped < constraints.min_quantity:
            notes.append("quantity_below_min")
        return shaped, notes

    @staticmethod
    def _round_nearest_tick(
        value: float, constraints: MarketConstraints | None
    ) -> float:
        """Round a plain limit price to the venue tick (nearest)."""
        if constraints is None or constraints.price_tick is None:
            return value
        return round(round(value / constraints.price_tick) * constraints.price_tick, 12)

    @staticmethod
    def _round_away(
        value: float, entry: float, constraints: MarketConstraints | None
    ) -> float:
        """Round a stop away from entry so planned risk distance is preserved."""
        if constraints is None or constraints.price_tick is None:
            return value
        tick = constraints.price_tick
        below_entry = value < entry
        rounded = (
            math.floor(value / tick + 1e-9) * tick
            if below_entry
            else math.ceil(value / tick - 1e-9) * tick
        )
        return round(max(rounded, tick), 12)

    @staticmethod
    def _round_toward(
        value: float, entry: float, constraints: MarketConstraints | None
    ) -> float:
        """Round a target toward entry so planned reward is conservative."""
        if constraints is None or constraints.price_tick is None:
            return value
        tick = constraints.price_tick
        above_entry = value > entry
        rounded = (
            math.floor(value / tick + 1e-9) * tick
            if above_entry
            else math.ceil(value / tick - 1e-9) * tick
        )
        return round(rounded, 12)

    # ----- submission -----

    def _submit_entry(
        self, track: _ExecutionTrack, plan: ExecutionPlan, now_ms: int
    ) -> ExecutionResult:
        """Submit the entry leg; protective legs follow only on real fills."""
        context = track.context
        entry_tracker = OrderTracker(plan.entry, now_ms)
        track.entry_tracker = entry_tracker
        entry_tracker.mark_submitting(now_ms)

        submission = self._place(entry_tracker.plan)
        entry_tracker.apply_submission(submission, now_ms)

        if entry_tracker.state is OrderLifecycle.UNKNOWN:
            self._symbol_unknowns[context.symbol] = track.idempotency_key
            track.resolved = False
            return self._snapshot(
                track,
                ExecutionStatus.UNKNOWN,
                now_ms,
                reconciliation_required=True,
                extra_metadata={
                    "reason": "entry_submission_unknown",
                    "message": submission.message,
                    "no_retry": True,
                },
            )

        if entry_tracker.state is OrderLifecycle.REJECTED:
            return self._snapshot(
                track,
                ExecutionStatus.REJECTED,
                now_ms,
                extra_metadata={"reason": "entry_rejected", "message": submission.message},
            )

        filled = entry_tracker.filled_quantity
        metadata: dict[str, object] = {}
        reconciliation_required = False
        if filled <= _FILL_EPS:
            metadata["protective_orders_deferred"] = "awaiting_entry_fill"
            status = ExecutionStatus.SUBMITTED
        else:
            protective_outcome = self._place_protective(track, plan, filled, now_ms)
            metadata.update(protective_outcome)
            reconciliation_required = any(
                key.endswith("_unknown") for key in protective_outcome
            )
            status = (
                ExecutionStatus.FILLED
                if math.isclose(filled, plan.requested_quantity, abs_tol=_FILL_EPS)
                else ExecutionStatus.PARTIALLY_FILLED
            )
        return self._snapshot(
            track,
            status,
            now_ms,
            reconciliation_required=reconciliation_required,
            extra_metadata=metadata,
        )

    def _place_protective(
        self,
        track: _ExecutionTrack,
        plan: ExecutionPlan,
        filled_quantity: float,
        now_ms: int,
    ) -> dict[str, object]:
        """Place stop-loss and take-profit sized to the actual fill only.

        Quantities never exceed ``filled_quantity`` — an unfilled remainder
        must not be protected as though it were held position.
        """
        outcome: dict[str, object] = {}
        assert plan.stop_loss is not None and plan.take_profit is not None
        for role_name, planned, tracker_slot in (
            ("stop_loss", plan.stop_loss, "stop_tracker"),
            ("take_profit", plan.take_profit, "target_tracker"),
        ):
            protective_plan = PlannedOrder(
                role=planned.role,
                symbol=planned.symbol,
                side=planned.side,
                order_type=planned.order_type,
                quantity=filled_quantity,
                price=planned.price,
                time_in_force=planned.time_in_force,
                client_order_id=planned.client_order_id,
            )
            tracker = OrderTracker(protective_plan, now_ms)
            setattr(track, tracker_slot, tracker)
            tracker.mark_submitting(now_ms)
            submission = self._place(protective_plan)
            tracker.apply_submission(submission, now_ms)
            state = tracker.state
            if state is OrderLifecycle.UNKNOWN:
                self._symbol_unknowns[plan.symbol] = track.idempotency_key
                track.resolved = False
                outcome[f"{role_name}_unknown"] = True
                outcome[f"{role_name}_message"] = submission.message
            elif state is OrderLifecycle.REJECTED:
                outcome[f"{role_name}_rejected"] = True
                outcome[f"{role_name}_message"] = submission.message
        return outcome

    def _place(self, plan: PlannedOrder) -> OrderSubmission:
        """Call place_order; normalize unexpected ExchangeError to UNKNOWN."""
        try:
            return self._exchange.place_order(
                plan.symbol,
                plan.side,
                plan.order_type,
                plan.quantity,
                price=plan.price,
                client_order_id=plan.client_order_id,
            )
        except ExchangeError as exc:
            network_like = exc.code in (
                ExchangeErrorCode.NETWORK_ERROR,
                ExchangeErrorCode.EXCHANGE_UNAVAILABLE,
            )
            return OrderSubmission(
                state=SubmissionState.UNKNOWN if network_like else SubmissionState.REJECTED,
                message=exc.message,
                metadata={"error_code": exc.code.value},
            )

    # ----- result assembly -----

    def _execution_id_for(self, key: str) -> str:
        return f"exec-{key}"

    def _empty_result(
        self, execution_id: str, context: ExecutionContext, now_ms: int
    ) -> ExecutionResult:
        return ExecutionResult(
            execution_id=execution_id,
            symbol=context.symbol,
            status=ExecutionStatus.PENDING,
            requested_quantity=0.0,
            filled_quantity=0.0,
            average_fill_price=None,
            direction=context.direction,
            created_at_ms=now_ms,
        )

    def _finish_noop(
        self,
        track: _ExecutionTrack,
        status: ExecutionStatus,
        now_ms: int,
        detail: dict[str, object],
    ) -> ExecutionResult:
        """Terminal result with zero submissions."""
        base = self._empty_result(track.execution_id, track.context, now_ms)
        noop_quantity = 0.0
        result = ExecutionResult(
            execution_id=base.execution_id,
            symbol=base.symbol,
            status=status,
            requested_quantity=noop_quantity,
            filled_quantity=0.0,
            average_fill_price=None,
            direction=base.direction,
            created_at_ms=now_ms,
            completed_at_ms=now_ms,
            metadata={
                **dict(track.context.metadata),
                **detail,
            },
        )
        track.result = result
        return result

    def _blocked_result(
        self,
        key: str,
        context: ExecutionContext,
        blocking_key: str,
        now_ms: int,
    ) -> ExecutionResult:
        blocking = self._executions.get(blocking_key)
        return ExecutionResult(
            execution_id=f"exec-{key}",
            symbol=context.symbol,
            status=ExecutionStatus.BLOCKED_RECONCILIATION,
            requested_quantity=0.0,
            filled_quantity=0.0,
            average_fill_price=None,
            direction=context.direction,
            created_at_ms=now_ms,
            completed_at_ms=now_ms,
            metadata={
                "reason": "unresolved_unknown_on_symbol",
                "blocking_execution_id": (
                    blocking.execution_id if blocking is not None else f"exec-{blocking_key}"
                ),
                "no_new_submissions_until_reconciled": True,
            },
        )

    def _annotate_duplicate(self, track: _ExecutionTrack) -> ExecutionResult:
        """Idempotent replay: recorded result plus a duplicate marker."""
        annotated = dataclasses.replace(
            track.result,
            metadata={**track.result.metadata, "duplicate_request": True},
        )
        return annotated

    def _snapshot(
        self,
        track: _ExecutionTrack,
        status: ExecutionStatus,
        now_ms: int,
        *,
        reconciliation_required: bool = False,
        extra_metadata: dict[str, object] | None = None,
    ) -> ExecutionResult:
        entry_record = track.entry_tracker.record if track.entry_tracker else None
        stop_record = track.stop_tracker.record if track.stop_tracker else None
        target_record = track.target_tracker.record if track.target_tracker else None
        filled = entry_record.filled_quantity if entry_record else 0.0
        avg = entry_record.average_fill_price if entry_record else None
        plan = track.metadata.get("plan")
        terminal = status in TERMINAL_EXECUTION_STATUSES
        extra: dict[str, object] = dict(extra_metadata or {})
        result = ExecutionResult(
            execution_id=track.execution_id,
            symbol=track.context.symbol,
            status=status,
            requested_quantity=entry_record.requested_quantity if entry_record else 0.0,
            filled_quantity=filled,
            average_fill_price=avg,
            direction=track.context.direction,
            position_action=plan.position_action if isinstance(plan, ExecutionPlan) else None,
            entry_order=entry_record,
            stop_order=stop_record,
            target_order=target_record,
            plan=plan if isinstance(plan, ExecutionPlan) else None,
            reconciliation_required=reconciliation_required,
            created_at_ms=now_ms,
            completed_at_ms=now_ms if terminal else None,
            metadata={
                **extra,
                **dict(track.context.metadata),
                "venue": self._exchange.venue_id,
            },
        )
        track.result = result
        return result

    # ----- cancellation -----

    def cancel_execution(self, idempotency_key: str) -> ExecutionResult:
        """Cancel every non-terminal order of a recorded execution.

        Orders whose final state is already known (FILLED, CANCELLED,
        REJECTED, EXPIRED) are never re-cancelled. An order in UNKNOWN is
        left untouched: its very existence at the venue is unproven, so a
        cancel attempt would be blind; reconciliation must run first.
        """
        track = self._executions.get(idempotency_key)
        if track is None:
            raise ValueError(f"Unknown execution for idempotency key {idempotency_key!r}")
        now_ms = self._clock_ms()
        recon_required = track.result.reconciliation_required
        notes: dict[str, object] = {}
        for slot in ("entry_tracker", "stop_tracker", "target_tracker"):
            tracker: OrderTracker | None = getattr(track, slot)
            if tracker is None:
                continue
            state = tracker.state
            if state in TERMINAL_LIFECYCLE_STATES or state in (
                OrderLifecycle.UNKNOWN,
                OrderLifecycle.PENDING,
                OrderLifecycle.SUBMITTING,
            ):
                if state is OrderLifecycle.UNKNOWN:
                    recon_required = True
                    notes[tracker.plan.role.value] = "cancel_skipped_unknown"
                continue
            tracker.mark_cancel_requested(now_ms)
            final_state, message = self._cancel_one(tracker)
            if final_state is not None:
                tracker.apply_order(final_state, now_ms, note=message)
            else:
                # The cancel outcome itself could not be determined.
                tracker.force_state(OrderLifecycle.UNKNOWN, now_ms, message)
                recon_required = True
                self._symbol_unknowns.setdefault(track.context.symbol, track.idempotency_key)
                notes[tracker.plan.role.value] = "cancel_unknown"
        status = self._status_after_cancel(track)
        return self._snapshot(
            track,
            status,
            now_ms,
            reconciliation_required=recon_required,
            extra_metadata={"cancel_notes": notes} if notes else {},
        )

    def _cancel_one(self, tracker: OrderTracker) -> tuple[Order | None, str | None]:
        """Cancel one tracked order; returns authoritative state or None."""
        plan = tracker.plan
        try:
            return (
                self._exchange.cancel_order(
                    plan.symbol,
                    order_id=tracker.record.venue_order_id,
                    client_order_id=plan.client_order_id,
                ),
                "cancelled",
            )
        except ExchangeError as exc:
            if exc.code is ExchangeErrorCode.ORDER_NOT_FOUND:
                fetched = self._fetch_authoritative(plan.symbol, tracker)
                if fetched is not None:
                    return fetched, "order_absent_at_cancel_fetched"
                return None, "order_not_found_and_unfetchable"
            return None, f"cancel_error:{exc.code.value}"

    def _fetch_authoritative(self, symbol: str, tracker: OrderTracker) -> Order | None:
        """Best-effort authoritative fetch after an inconclusive cancel."""
        record = tracker.record
        try:
            return self._exchange.get_order(
                symbol,
                order_id=record.venue_order_id,
                client_order_id=tracker.plan.client_order_id,
            )
        except ExchangeError:
            return None

    @staticmethod
    def _status_after_cancel(track: _ExecutionTrack) -> ExecutionStatus:
        """Derive execution status from entry state post-cancel."""
        entry = track.entry_tracker
        if entry is None:
            return track.result.status
        return _LIFECYCLE_TO_EXECUTION_STATUS[entry.state]

    # ----- reconciliation -----

    def reconcile_execution(
        self, idempotency_key: str, expected_position: Position | None = None
    ) -> ReconciliationOutcome:
        """Reconcile one recorded execution against the venue.

        Authoritative venue snapshots are applied to local trackers (the only
        path out of UNKNOWN); material discrepancies are reported for
        higher-level policy rather than silently rewritten.
        """
        track = self._executions.get(idempotency_key)
        if track is None:
            raise ValueError(f"Unknown execution for idempotency key {idempotency_key!r}")
        now_ms = self._clock_ms()
        reconciler = ExecutionReconciler(self._exchange)
        trackers: list[OrderTracker] = []
        for slot in ("stop_tracker", "target_tracker", "entry_tracker"):
            tracker: OrderTracker | None = getattr(track, slot)
            if tracker is not None:
                trackers.append(tracker)
        report = reconciler.reconcile_orders(
            track.context.symbol,
            [tracker.record for tracker in trackers],
            client_id_prefixes=(f"{track.idempotency_key}-",),
            expected_position=expected_position,
        )
        for tracker, finding in zip(trackers, report.order_findings, strict=True):
            if finding.authoritative_order is not None:
                tracker.reconcile(finding.authoritative_order, now_ms, note=finding.finding.value)
        still_unknown = any(
            tracker.state is OrderLifecycle.UNKNOWN for tracker in trackers
        )
        if not still_unknown:
            self._symbol_unknowns.pop(track.context.symbol, None)
        result = self._snapshot(
            track,
            self._derive_status(track),
            now_ms,
            reconciliation_required=still_unknown,
            extra_metadata={
                "reconciled": True,
                "findings": [finding.finding.value for finding in report.order_findings],
                "requires_policy": report.requires_policy,
            },
        )
        return ReconciliationOutcome(report=report, result=result)

    def _derive_status(self, track: _ExecutionTrack) -> ExecutionStatus:
        entry = track.entry_tracker
        if entry is None:
            return track.result.status
        return _LIFECYCLE_TO_EXECUTION_STATUS[entry.state]
