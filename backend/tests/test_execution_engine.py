"""Deterministic tests for the execution engine.

Every venue response comes from a scripted fake ``ExchangePort`` — no
network, no ccxt, no credentials, no real orders.
"""

import logging

import pytest

from exchange.base import ExchangePort
from exchange.capabilities import ExchangeCapabilities
from exchange.constraints import MarketConstraints
from exchange.errors import ExchangeError, ExchangeErrorCode
from exchange.models import (
    Order,
    OrderSide,
    OrderStatus,
    OrderSubmission,
    OrderType,
    Position,
    PositionDirection,
    SubmissionState,
)
from execution_engine import (
    DiscrepancyType,
    ExecutionContext,
    ExecutionEngine,
    ExecutionReconciler,
    ExecutionStatus,
    OrderLifecycle,
)
from risk_engine.base import RejectionReason, RiskDecision, RiskDecisionStatus

# ---------------------------------------------------------------------------
# Scriptable fake ExchangePort
# ---------------------------------------------------------------------------


class ScriptablePort(ExchangePort):
    """Fake venue: scripted submissions, observable calls, no I/O."""

    def __init__(self, **capability_flags: bool) -> None:
        defaults = {
            "spot": True,
            "market_orders": True,
            "limit_orders": True,
            "stop_orders": True,
            "shorting": True,
        }
        defaults.update(capability_flags)
        self._caps = ExchangeCapabilities(**defaults)  # type: ignore[arg-type]
        self.constraints = MarketConstraints()
        self.place_results: list[OrderSubmission | Exception] = []
        self.orders_by_client_id: dict[str, Order] = {}
        self.get_order_script: dict[str, Order | Exception] = {}
        self.cancel_scripts: dict[str, Order | Exception] = {}
        self.positions: tuple[Position, ...] = ()
        self.open_orders: tuple[Order, ...] = ()
        self.place_calls: list[tuple[str, str, OrderType, float, float | None, str | None]] = []
        self.cancel_calls: list[tuple[str, str | None, str | None]] = []
        self._next_id = 1

    @property
    def venue_id(self) -> str:
        return "fake"

    @property
    def capabilities(self) -> ExchangeCapabilities:
        return self._caps

    def get_ticker(self, symbol: str):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    def get_order_book(self, symbol: str, depth: int = 50):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 200):  # type: ignore[no-untyped-def]
        return ()

    def get_markets(self):  # type: ignore[no-untyped-def]
        return ()

    def get_market(self, symbol: str):  # type: ignore[no-untyped-def]
        return self.constraints

    def get_balances(self):  # type: ignore[no-untyped-def]
        return ()

    def get_positions(self):  # type: ignore[no-untyped-def]
        return self.positions

    def get_open_orders(self, symbol: str | None = None):  # type: ignore[no-untyped-def]
        return self.open_orders

    def get_order(
        self,
        symbol: str,
        order_id: str | None = None,
        client_order_id: str | None = None,
    ):  # type: ignore[no-untyped-def]
        key = client_order_id or order_id or ""
        if key in self.get_order_script:
            result = self.get_order_script[key]
            if isinstance(result, Exception):
                raise result
            return result
        stored = self.orders_by_client_id.get(key)
        if stored is not None:
            return stored
        raise ExchangeError(
            ExchangeErrorCode.ORDER_NOT_FOUND, f"no order {key}", metadata={"symbol": symbol}
        )

    def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: float | None = None,
        client_order_id: str | None = None,
    ):  # type: ignore[no-untyped-def]
        self.place_calls.append((symbol, side.value, order_type, quantity, price, client_order_id))
        if self.place_results:
            result = self.place_results.pop(0)
        else:
            result = self._default_accept(
                symbol, side, order_type, quantity, price, client_order_id
            )
        if isinstance(result, Exception):
            raise result
        if result.order is not None and client_order_id is not None:
            self.orders_by_client_id[client_order_id] = result.order
        return result

    def cancel_order(
        self,
        symbol: str,
        order_id: str | None = None,
        client_order_id: str | None = None,
    ):  # type: ignore[no-untyped-def]
        self.cancel_calls.append((symbol, order_id, client_order_id))
        for key in (client_order_id, order_id):
            if key is not None and key in self.cancel_scripts:
                result = self.cancel_scripts[key]
                if isinstance(result, Exception):
                    raise result
                return result
        cancelled = Order(
            symbol=symbol,
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            status=OrderStatus.CANCELED,
            quantity=1.0,
            id=order_id,
            client_order_id=client_order_id,
        )
        if client_order_id is not None:
            self.orders_by_client_id[client_order_id] = cancelled
        return cancelled

    def cancel_all_orders(self, symbol: str | None = None):  # type: ignore[no-untyped-def]
        return 0

    def _default_accept(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: float | None,
        client_order_id: str | None,
    ) -> OrderSubmission:
        """Market orders fill completely; everything else rests open."""
        fills = order_type is OrderType.MARKET
        oid = f"V{self._next_id}"
        self._next_id += 1
        order = Order(
            symbol=symbol,
            side=side,
            type=order_type,
            status=OrderStatus.FILLED if fills else OrderStatus.OPEN,
            quantity=quantity,
            filled_quantity=quantity if fills else 0.0,
            id=oid,
            client_order_id=client_order_id,
            price=price,
            average_fill_price=price if fills and price is not None else None,
        )
        return OrderSubmission(state=SubmissionState.ACCEPTED, order=order)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def fixed_clock(start: int = 1_000) -> object:
    state = {"now": start}

    def tick() -> int:
        state["now"] += 10
        return state["now"]

    return tick


def make_decision(
    *,
    entry: float = 100.0,
    stop: float = 95.0,
    target: float = 110.0,
    quantity: float = 2.0,
    approved: bool = True,
    rejection: RejectionReason | None = None,
) -> RiskDecision:
    if not approved:
        return RiskDecision(
            approved=False,
            status=RiskDecisionStatus.REJECTED,
            rejection_reason=rejection or RejectionReason.RISK_LIMIT,
            metadata={"note": "rejected by tests"},
        )
    return RiskDecision(
        approved=True,
        status=RiskDecisionStatus.APPROVED,
        rejection_reason=None,
        entry_price=entry,
        stop_price=stop,
        target_price=target,
        position_quantity=quantity,
        position_notional=quantity * entry,
    )


def make_context(**overrides: object) -> ExecutionContext:
    values: dict[str, object] = {
        "symbol": "BTC/USDT",
        "direction": PositionDirection.LONG,
        "idempotency_key": "req-1",
    }
    values.update(overrides)
    return ExecutionContext(**values)  # type: ignore[arg-type]


def make_engine(port: ScriptablePort) -> ExecutionEngine:
    return ExecutionEngine(port, clock_ms=fixed_clock(), id_generator=lambda: "gen-id")


# ---------------------------------------------------------------------------
# Safety invariants
# ---------------------------------------------------------------------------


class TestSafetyInvariants:
    def test_rejected_decision_produces_zero_submissions(self) -> None:
        port = ScriptablePort()
        engine = make_engine(port)
        result = engine.execute(make_decision(approved=False), make_context())
        assert result.status is ExecutionStatus.REJECTED_BY_RISK
        assert result.metadata["reason"] == "risk_decision_not_approved"
        assert result.metadata["rejection_reason"] == "risk_limit"
        assert port.place_calls == []

    def test_rejected_result_is_terminal_and_reconcile_free(self) -> None:
        engine = make_engine(ScriptablePort())
        result = engine.execute(make_decision(approved=False), make_context())
        assert result.is_terminal
        assert not result.reconciliation_required

    def test_invalid_request_missing_entry_price_submits_nothing(self) -> None:
        port = ScriptablePort()
        engine = make_engine(port)
        decision = RiskDecision(
            approved=True,
            status=RiskDecisionStatus.APPROVED,
            rejection_reason=None,
            stop_price=95.0,
            target_price=110.0,
            position_quantity=2.0,
        )
        result = engine.execute(decision, make_context())
        assert result.status is ExecutionStatus.INVALID_REQUEST
        assert "entry_price_missing_or_invalid" in result.metadata["problems"]
        assert port.place_calls == []

    def test_invalid_request_zero_quantity_submits_nothing(self) -> None:
        port = ScriptablePort()
        engine = make_engine(port)
        decision = make_decision(quantity=0.0)
        result = engine.execute(decision, make_context())
        assert result.status is ExecutionStatus.INVALID_REQUEST
        assert port.place_calls == []

    def test_invalid_request_stop_target_side_violation(self) -> None:
        port = ScriptablePort()
        engine = make_engine(port)
        decision = make_decision(entry=100.0, stop=105.0, target=110.0)
        result = engine.execute(decision, make_context())
        assert result.status is ExecutionStatus.INVALID_REQUEST
        assert result.metadata["reason"] == "stop_target_side_violation"
        assert port.place_calls == []

    def test_invalid_request_short_side_violation(self) -> None:
        port = ScriptablePort()
        engine = make_engine(port)
        decision = make_decision(entry=100.0, stop=95.0, target=90.0)
        context = make_context(direction=PositionDirection.SHORT)
        result = engine.execute(decision, context)
        assert result.status is ExecutionStatus.INVALID_REQUEST
        assert port.place_calls == []

    def test_empty_symbol_rejected_by_model_validation(self) -> None:
        with pytest.raises(ValueError, match="symbol"):
            make_context(symbol="")

    def test_unsupported_market_orders_aborts_before_submission(self) -> None:
        port = ScriptablePort(market_orders=False)
        engine = make_engine(port)
        result = engine.execute(make_decision(), make_context())
        assert result.status is ExecutionStatus.UNSUPPORTED_OPERATION
        assert "market_orders" in result.metadata["capabilities"]
        assert port.place_calls == []

    def test_missing_stop_orders_blocks_whole_execution(self) -> None:
        port = ScriptablePort(stop_orders=False)
        engine = make_engine(port)
        result = engine.execute(make_decision(), make_context())
        assert result.status is ExecutionStatus.UNSUPPORTED_OPERATION
        assert "stop_orders" in result.metadata["capabilities"]
        # Entering without protective capability is refused entirely.
        assert port.place_calls == []

    def test_limit_entry_requires_limit_order_capability(self) -> None:
        port = ScriptablePort(limit_orders=False)
        engine = make_engine(port)
        context = make_context(entry_order_type=OrderType.LIMIT)
        result = engine.execute(make_decision(), context)
        assert result.status is ExecutionStatus.UNSUPPORTED_OPERATION
        assert port.place_calls == []


# ---------------------------------------------------------------------------
# LONG / SHORT entry construction and side mapping
# ---------------------------------------------------------------------------


class TestEntryConstruction:
    def test_long_market_execution_full_flow(self) -> None:
        port = ScriptablePort()
        engine = make_engine(port)
        result = engine.execute(make_decision(), make_context())
        assert result.status is ExecutionStatus.FILLED
        assert len(port.place_calls) == 3
        entry_call, stop_call, target_call = port.place_calls
        assert entry_call[1] == "buy" and entry_call[2] is OrderType.MARKET
        assert entry_call[3] == 2.0
        assert stop_call[1] == "sell" and stop_call[2] is OrderType.STOP_MARKET
        assert stop_call[4] == 95.0
        assert target_call[1] == "sell" and target_call[2] is OrderType.LIMIT
        assert target_call[4] == 110.0

    def test_short_execution_sides_inverted(self) -> None:
        port = ScriptablePort()
        engine = make_engine(port)
        decision = make_decision(entry=100.0, stop=105.0, target=90.0)
        context = make_context(direction=PositionDirection.SHORT)
        result = engine.execute(decision, context)
        assert result.status is ExecutionStatus.FILLED
        entry_call, stop_call, target_call = port.place_calls
        assert entry_call[1] == "sell"
        assert stop_call[1] == "buy" and stop_call[4] == 105.0
        assert target_call[1] == "buy" and target_call[4] == 90.0
        assert result.direction is PositionDirection.SHORT

    def test_deterministic_client_order_ids_from_key(self) -> None:
        port = ScriptablePort()
        engine = make_engine(port)
        engine.execute(make_decision(), make_context(idempotency_key="trade-77"))
        ids = [call[5] for call in port.place_calls]
        assert ids == ["trade-77-entry", "trade-77-stop", "trade-77-target"]

    def test_plan_is_recorded_on_result_with_adjustments(self) -> None:
        engine = make_engine(ScriptablePort())
        result = engine.execute(make_decision(), make_context())
        assert result.plan is not None
        assert result.plan.requested_quantity == 2.0
        assert result.plan.adjustments == ()
        assert result.entry_order is not None
        assert result.entry_order.plan.client_order_id == "req-1-entry"

    def test_position_action_open_when_no_existing_position(self) -> None:
        engine = make_engine(ScriptablePort())
        result = engine.execute(make_decision(), make_context())
        assert result.position_action.value == "open"

    def test_position_action_increase_along_existing_long(self) -> None:
        engine = make_engine(ScriptablePort())
        context = make_context(
            current_position_side=PositionDirection.LONG, current_position_quantity=1.0
        )
        result = engine.execute(make_decision(), context)
        assert result.position_action.value == "increase"

    def test_position_action_reduce_opposing_partial_size(self) -> None:
        engine = make_engine(ScriptablePort())
        context = make_context(
            direction=PositionDirection.LONG,
            current_position_side=PositionDirection.SHORT,
            current_position_quantity=5.0,
        )
        result = engine.execute(make_decision(quantity=2.0), context)
        assert result.position_action.value == "reduce"

    def test_position_action_close_opposing_full_size(self) -> None:
        engine = make_engine(ScriptablePort())
        context = make_context(
            direction=PositionDirection.LONG,
            current_position_side=PositionDirection.SHORT,
            current_position_quantity=2.0,
        )
        result = engine.execute(make_decision(quantity=2.0), context)
        assert result.position_action.value == "close"


# ---------------------------------------------------------------------------
# Partial fills
# ---------------------------------------------------------------------------


class TestPartialFills:
    def partial_fill_port(self) -> tuple[ScriptablePort, OrderSubmission]:
        port = ScriptablePort()
        partial = OrderSubmission(
            state=SubmissionState.ACCEPTED,
            order=Order(
                symbol="BTC/USDT",
                side=OrderSide.BUY,
                type=OrderType.MARKET,
                status=OrderStatus.PARTIALLY_FILLED,
                quantity=1.0,
                filled_quantity=0.4,
                id="V-P",
                average_fill_price=99.5,
            ),
        )
        port.place_results.append(partial)
        return port, partial

    def test_protective_orders_sized_to_actual_fill_not_plan(self) -> None:
        port, _partial = self.partial_fill_port()
        engine = make_engine(port)
        result = engine.execute(make_decision(quantity=1.0), make_context())
        assert result.status is ExecutionStatus.PARTIALLY_FILLED
        assert len(port.place_calls) == 3
        _, stop_call, target_call = port.place_calls
        assert stop_call[3] == 0.4
        assert target_call[3] == 0.4

    def test_quantities_distinguish_requested_filled_remaining(self) -> None:
        port, _partial = self.partial_fill_port()
        engine = make_engine(port)
        result = engine.execute(make_decision(quantity=1.0), make_context())
        assert result.requested_quantity == 1.0
        assert result.filled_quantity == 0.4
        assert result.remaining_quantity == pytest.approx(0.6)
        assert result.average_fill_price == pytest.approx(99.5)
        assert result.entry_order is not None
        assert result.entry_order.state is OrderLifecycle.PARTIALLY_FILLED

    def test_execution_not_complete_while_quantity_remains(self) -> None:
        port, _partial = self.partial_fill_port()
        engine = make_engine(port)
        result = engine.execute(make_decision(quantity=1.0), make_context())
        assert not result.is_terminal


# ---------------------------------------------------------------------------
# UNKNOWN handling: no retry, reconciliation required, symbol blocked
# ---------------------------------------------------------------------------


class TestUnknownSubmissionFlow:
    def unknown_port(self) -> ScriptablePort:
        port = ScriptablePort()
        port.place_results.append(
            OrderSubmission(state=SubmissionState.UNKNOWN, message="request timed out")
        )
        return port

    def test_unknown_entry_never_retried_and_requires_reconciliation(self) -> None:
        port = self.unknown_port()
        engine = make_engine(port)
        result = engine.execute(make_decision(), make_context())
        assert result.status is ExecutionStatus.UNKNOWN
        assert result.reconciliation_required is True
        assert result.metadata["no_retry"] is True
        # Exactly one submission attempt; no protective orders followed.
        assert len(port.place_calls) == 1

    def test_new_submissions_on_symbol_blocked_until_reconciled(self) -> None:
        engine = make_engine(self.unknown_port())
        engine.execute(make_decision(), make_context(idempotency_key="first"))
        assert engine.has_unresolved_unknown("BTC/USDT")
        port2_calls_before = len(engine._executions)  # noqa: SLF001
        result = engine.execute(
            make_decision(), make_context(idempotency_key="second")
        )
        assert result.status is ExecutionStatus.BLOCKED_RECONCILIATION
        assert result.metadata["blocking_execution_id"] == "exec-first"
        assert "second" not in {k for k in engine._executions} or len(engine._executions) == (
            port2_calls_before + 1
        )

    def test_blocked_attempt_made_no_submissions(self) -> None:
        port = self.unknown_port()
        engine = make_engine(port)
        engine.execute(make_decision(), make_context(idempotency_key="first"))
        calls_before = len(port.place_calls)
        engine.execute(make_decision(), make_context(idempotency_key="second"))
        assert len(port.place_calls) == calls_before

    def test_reconciliation_resolves_unknown_and_unblocks_symbol(self) -> None:
        port = self.unknown_port()
        engine = make_engine(port)
        outcome_first = engine.execute(make_decision(), make_context(idempotency_key="req"))
        assert outcome_first.status is ExecutionStatus.UNKNOWN
        filled_remote = Order(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            type=OrderType.MARKET,
            status=OrderStatus.FILLED,
            quantity=2.0,
            filled_quantity=2.0,
            id="V-REMOTE",
            client_order_id="req-entry",
            average_fill_price=100.5,
        )
        port.get_order_script["req-entry"] = filled_remote
        outcome = engine.reconcile_execution("req")
        assert not outcome.report.requires_policy
        resolved = outcome.result
        assert resolved is not None and resolved.status is ExecutionStatus.FILLED
        assert not resolved.reconciliation_required
        assert resolved.filled_quantity == 2.0
        assert not engine.has_unresolved_unknown("BTC/USDT")

    def test_unresolved_unknown_after_empty_reconcile_keeps_block(self) -> None:
        port = self.unknown_port()
        engine = make_engine(port)
        engine.execute(make_decision(), make_context(idempotency_key="req"))
        port.get_order_script["req-entry"] = ExchangeError(
            ExchangeErrorCode.ORDER_NOT_FOUND, "no such order"
        )
        outcome = engine.reconcile_execution("req")
        assert outcome.result is not None
        assert outcome.result.status is ExecutionStatus.UNKNOWN
        assert outcome.result.reconciliation_required
        assert engine.has_unresolved_unknown("BTC/USDT")

    def test_accepted_without_order_snapshot_treated_as_unknown(self) -> None:
        port = ScriptablePort()
        port.place_results.append(OrderSubmission(state=SubmissionState.ACCEPTED, order=None))
        engine = make_engine(port)
        result = engine.execute(make_decision(), make_context())
        assert result.status is ExecutionStatus.UNKNOWN
        assert result.reconciliation_required


# ---------------------------------------------------------------------------
# Idempotency / duplicate protection
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_duplicate_request_returns_recorded_result_without_resubmitting(self) -> None:
        port = ScriptablePort()
        engine = make_engine(port)
        first = engine.execute(make_decision(), make_context(idempotency_key="dup"))
        calls_after_first = len(port.place_calls)
        second = engine.execute(make_decision(), make_context(idempotency_key="dup"))
        assert len(port.place_calls) == calls_after_first
        assert second.execution_id == first.execution_id
        assert second.status is ExecutionStatus.FILLED
        assert second.metadata["duplicate_request"] is True

    def test_get_execution_returns_latest_state(self) -> None:
        engine = make_engine(ScriptablePort())
        executed = engine.execute(make_decision(), make_context())
        stored = engine.get_execution("req-1")
        assert stored is not None
        assert stored.execution_id == executed.execution_id

    def test_generated_ids_unique_without_explicit_key(self) -> None:
        port = ScriptablePort()
        counter = {"n": 0}

        def next_id() -> str:
            counter["n"] += 1
            return f"auto-{counter['n']}"

        engine = ExecutionEngine(port, clock_ms=fixed_clock(), id_generator=next_id)
        one = engine.execute(make_decision(), make_context(idempotency_key=None))
        two = engine.execute(make_decision(), make_context(idempotency_key=None))
        assert one.execution_id != two.execution_id
        ids = [call[5] for call in port.place_calls]
        assert len(ids) == 6 and len(set(ids)) == 6

    def test_same_key_across_engines_yields_same_client_ids(self) -> None:
        ids_per_run = []
        for _ in range(2):
            port = ScriptablePort()
            engine = ExecutionEngine(
                port,
                clock_ms=fixed_clock(),
                id_generator=lambda: "ignored",
            )
            engine.execute(make_decision(), make_context(idempotency_key="stable"))
            ids_per_run.append([call[5] for call in port.place_calls])
        assert ids_per_run[0] == ids_per_run[1]


# ---------------------------------------------------------------------------
# Protective-order failure paths
# ---------------------------------------------------------------------------


class TestProtectiveOrderFailures:
    @staticmethod
    def filled_entry_submission() -> OrderSubmission:
        return OrderSubmission(
            state=SubmissionState.ACCEPTED,
            order=Order(
                symbol="BTC/USDT",
                side=OrderSide.BUY,
                type=OrderType.MARKET,
                status=OrderStatus.FILLED,
                quantity=2.0,
                filled_quantity=2.0,
                id="V-E",
                average_fill_price=100.0,
            ),
        )

    def test_stop_rejection_is_surfaced_but_target_still_placed(self) -> None:
        port = ScriptablePort()
        port.place_results.append(self.filled_entry_submission())
        port.place_results.append(
            OrderSubmission(state=SubmissionState.REJECTED, message="stop rejected")
        )
        engine = make_engine(port)
        result = engine.execute(make_decision(), make_context())
        assert result.status is ExecutionStatus.FILLED
        assert result.stop_order is not None
        assert result.stop_order.state is OrderLifecycle.REJECTED
        assert result.metadata.get("stop_loss_rejected") is True
        assert result.target_order is not None
        assert result.target_order.state is OrderLifecycle.ACCEPTED

    def test_stop_unknown_sets_reconciliation_required_and_blocks_symbol(self) -> None:
        port = ScriptablePort()
        port.place_results.append(self.filled_entry_submission())
        port.place_results.append(
            OrderSubmission(state=SubmissionState.UNKNOWN, message="stop timeout")
        )
        engine = make_engine(port)
        result = engine.execute(make_decision(), make_context())
        assert result.reconciliation_required is True
        assert result.metadata.get("stop_loss_unknown") is True
        assert engine.has_unresolved_unknown("BTC/USDT")
        # Entry accepted, stop attempted once (unknown), target still placed.
        assert len(port.place_calls) == 3


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


class TestCancellation:
    def resting_entry_port(self) -> tuple[ScriptablePort, ExecutionEngine]:
        port = ScriptablePort()
        engine = make_engine(port)
        context = make_context(entry_order_type=OrderType.LIMIT)
        result = engine.execute(make_decision(), context)
        assert result.status is ExecutionStatus.SUBMITTED
        return port, engine

    def test_cancel_resting_entry_moves_to_cancelled(self) -> None:
        port, engine = self.resting_entry_port()
        result = engine.cancel_execution("req-1")
        assert result.status is ExecutionStatus.CANCELLED
        assert result.completed_at_ms is not None
        assert len(port.cancel_calls) == 1
        assert port.cancel_calls[0][2] == "req-1-entry"

    def test_cancel_fully_filled_execution_only_touches_protectives(self) -> None:
        port = ScriptablePort()
        engine = make_engine(port)
        engine.execute(make_decision(), make_context())  # market: everything fills/accepts
        result = engine.cancel_execution("req-1")
        # Entry FILLED already: final state known -> never re-cancelled.
        cancelled_ids = [call[2] for call in port.cancel_calls]
        assert cancelled_ids == ["req-1-stop", "req-1-target"]
        assert result.status is ExecutionStatus.FILLED

    def test_cancel_is_idempotent_for_terminal_orders(self) -> None:
        port, engine = self.resting_entry_port()
        first = engine.cancel_execution("req-1")
        calls_after_first = len(port.cancel_calls)
        second = engine.cancel_execution("req-1")
        assert len(port.cancel_calls) == calls_after_first
        assert first.status is ExecutionStatus.CANCELLED
        assert second.status is ExecutionStatus.CANCELLED

    def test_cancel_race_with_fill_adopts_authoritative_fill(self) -> None:
        port, engine = self.resting_entry_port()
        filled_instead = Order(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            status=OrderStatus.FILLED,
            quantity=2.0,
            filled_quantity=2.0,
            id="V1",
            client_order_id="req-1-entry",
            average_fill_price=100.0,
        )
        port.cancel_scripts["req-1-entry"] = filled_instead
        result = engine.cancel_execution("req-1")
        assert result.status is ExecutionStatus.FILLED
        assert result.entry_order is not None
        assert result.entry_order.state is OrderLifecycle.FILLED

    def test_cancel_unknown_order_skipped_and_flagged(self) -> None:
        port = ScriptablePort()
        engine = make_engine(port)
        port.place_results.append(
            OrderSubmission(state=SubmissionState.UNKNOWN, message="timeout")
        )
        engine.execute(make_decision(), make_context(idempotency_key="u"))
        result = engine.cancel_execution("u")
        assert port.cancel_calls == []
        assert result.reconciliation_required is True

    def test_cancel_network_error_marks_unknown_reconciliation_required(self) -> None:
        port, engine = self.resting_entry_port()
        port.cancel_scripts["req-1-entry"] = ExchangeError(
            ExchangeErrorCode.NETWORK_ERROR, "connection lost"
        )
        result = engine.cancel_execution("req-1")
        assert result.reconciliation_required is True
        assert result.entry_order is not None
        assert result.entry_order.state is OrderLifecycle.UNKNOWN

    def test_cancel_order_not_found_fetches_authoritative_state(self) -> None:
        port, engine = self.resting_entry_port()
        port.cancel_scripts["req-1-entry"] = ExchangeError(
            ExchangeErrorCode.ORDER_NOT_FOUND, "gone"
        )
        port.get_order_script["req-1-entry"] = Order(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            status=OrderStatus.CANCELED,
            quantity=2.0,
            id="V1",
            client_order_id="req-1-entry",
        )
        result = engine.cancel_execution("req-1")
        assert result.status is ExecutionStatus.CANCELLED
        assert result.entry_order is not None
        assert result.entry_order.state is OrderLifecycle.CANCELLED

    def test_cancel_unknown_execution_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown execution"):
            make_engine(ScriptablePort()).cancel_execution("nope")


# ---------------------------------------------------------------------------
# Reconciliation details
# ---------------------------------------------------------------------------


class TestReconciliationFindings:
    def executed(self, **context_overrides: object) -> tuple[ScriptablePort, ExecutionEngine]:
        port = ScriptablePort()
        engine = make_engine(port)
        engine.execute(make_decision(), make_context(**context_overrides))
        return port, engine

    def test_matching_state_reports_match_without_policy(self) -> None:
        port, engine = self.executed()
        outcome = engine.reconcile_execution("req-1")
        findings = {f.role_value: f.finding for f in outcome.report.order_findings}
        assert findings == {
            "stop_loss": DiscrepancyType.MATCH,
            "take_profit": DiscrepancyType.MATCH,
            "entry": DiscrepancyType.MATCH,
        }
        assert not outcome.report.requires_policy

    def test_fill_quantity_mismatch_reported_and_authoritative_applied(self) -> None:
        port = ScriptablePort()
        engine = make_engine(port)
        partial = OrderSubmission(
            state=SubmissionState.ACCEPTED,
            order=Order(
                symbol="BTC/USDT",
                side=OrderSide.BUY,
                type=OrderType.MARKET,
                status=OrderStatus.PARTIALLY_FILLED,
                quantity=2.0,
                filled_quantity=0.5,
                id="V-PART",
            ),
        )
        port.place_results.append(partial)
        engine.execute(make_decision(quantity=2.0), make_context())
        remote_truth = Order(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            type=OrderType.MARKET,
            status=OrderStatus.PARTIALLY_FILLED,
            quantity=2.0,
            filled_quantity=0.9,
            id="V-PART",
        )
        port.get_order_script["req-1-entry"] = remote_truth
        outcome = engine.reconcile_execution("req-1")
        entry_finding = next(
            f for f in outcome.report.order_findings if f.role_value == "entry"
        )
        assert entry_finding.finding is DiscrepancyType.FILL_QUANTITY_MISMATCH
        assert entry_finding.local_filled == 0.5
        assert entry_finding.remote_filled == 0.9
        assert outcome.report.requires_policy
        assert outcome.result is not None
        assert outcome.result.filled_quantity == pytest.approx(0.9)

    def test_status_mismatch_detected(self) -> None:
        port, engine = self.executed()
        expired_remote = Order(
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            type=OrderType.STOP_MARKET,
            status=OrderStatus.EXPIRED,
            quantity=2.0,
            price=95.0,
            id="V2",
        )
        port.get_order_script["req-1-stop"] = expired_remote
        outcome = engine.reconcile_execution("req-1")
        stop_finding = next(
            f for f in outcome.report.order_findings if f.role_value == "stop_loss"
        )
        assert stop_finding.finding is DiscrepancyType.STATUS_MISMATCH

    def test_live_local_missing_remotely_requires_policy(self) -> None:
        port, engine = self.executed()
        port.get_order_script["req-1-stop"] = ExchangeError(
            ExchangeErrorCode.ORDER_NOT_FOUND, "not found"
        )
        outcome = engine.reconcile_execution("req-1")
        stop_finding = next(
            f for f in outcome.report.order_findings if f.role_value == "stop_loss"
        )
        assert stop_finding.finding is DiscrepancyType.MISSING_REMOTELY
        assert outcome.report.requires_policy

    def test_untracked_remote_order_with_our_prefix_flagged(self) -> None:
        port, engine = self.executed()
        stranger = Order(
            symbol="BTC/USDT",
            side=OrderSide.SELL,
            type=OrderType.STOP_MARKET,
            status=OrderStatus.OPEN,
            quantity=0.5,
            price=94.0,
            id="V-GHOST",
            client_order_id="req-1-stop-duplicate",
        )
        port.open_orders = (stranger,)
        outcome = engine.reconcile_execution("req-1")
        assert any(
            o.id == "V-GHOST" for o in outcome.report.untracked_remote_orders
        )
        assert outcome.report.requires_policy

    def test_venue_error_during_reconciliation_requires_policy(self) -> None:
        port, engine = self.executed()
        port.get_order_script["req-1-entry"] = ExchangeError(
            ExchangeErrorCode.UNKNOWN, "garbage payload"
        )
        outcome = engine.reconcile_execution("req-1")
        entry_finding = next(
            f for f in outcome.report.order_findings if f.role_value == "entry"
        )
        assert entry_finding.finding is DiscrepancyType.VENUE_ERROR
        assert outcome.report.requires_policy

    def test_position_mismatch_requires_policy(self) -> None:
        port, engine = self.executed()
        expected = Position(
            symbol="BTC/USDT", side=PositionDirection.LONG, quantity=2.0, entry_price=100.0
        )
        port.positions = (
            Position(symbol="BTC/USDT", side=PositionDirection.LONG, quantity=1.0),
        )
        reconciler = ExecutionReconciler(port)
        report = reconciler.reconcile_orders("BTC/USDT", (), expected_position=expected)
        assert report.position_finding.checked
        assert report.position_finding.match is False
        assert report.requires_policy

    def test_position_match_clean(self) -> None:
        port = ScriptablePort()
        expected = Position(
            symbol="BTC/USDT", side=PositionDirection.SHORT, quantity=2.0, entry_price=100.0
        )
        port.positions = (
            Position(symbol="BTC/USDT", side=PositionDirection.SHORT, quantity=2.0),
        )
        report = ExecutionReconciler(port).reconcile_orders(
            "BTC/USDT", (), expected_position=expected
        )
        assert report.position_finding.match is True
        assert not report.requires_policy

    def test_standalone_reconciler_on_plain_records(self) -> None:
        port = ScriptablePort()
        engine = make_engine(port)
        result = engine.execute(make_decision(), make_context())
        assert result.entry_order is not None and result.stop_order is not None
        records = [result.entry_order, result.stop_order]
        report = ExecutionReconciler(port).reconcile_orders("BTC/USDT", tuple(records))
        assert all(f.finding is DiscrepancyType.MATCH for f in report.order_findings)


# ---------------------------------------------------------------------------
# Constraint shaping: explicit, traceable adjustments
# ---------------------------------------------------------------------------


class TestConstraintShaping:
    def test_quantity_step_rounding_recorded_as_adjustment(self) -> None:
        port = ScriptablePort()
        port.constraints = MarketConstraints(quantity_step=0.5)
        engine = make_engine(port)
        result = engine.execute(make_decision(quantity=2.3), make_context())
        assert result.status is ExecutionStatus.FILLED
        assert port.place_calls[0][3] == 2.0
        assert result.plan is not None and len(result.plan.adjustments) == 1
        adjustment = result.plan.adjustments[0]
        assert adjustment.field == "entry.quantity"
        assert adjustment.original == pytest.approx(2.3)
        assert adjustment.adjusted == 2.0
        assert adjustment.reason == "quantity_step_rounding"

    def test_max_quantity_clamp_traced(self) -> None:
        port = ScriptablePort()
        port.constraints = MarketConstraints(max_quantity=1.0)
        engine = make_engine(port)
        result = engine.execute(make_decision(quantity=2.0), make_context())
        assert port.place_calls[0][3] == 1.0
        assert result.plan is not None
        assert result.plan.adjustments[0].reason == "max_quantity_clamp"

    def test_below_min_quantity_refuses_without_submissions(self) -> None:
        port = ScriptablePort()
        port.constraints = MarketConstraints(min_quantity=5.0, quantity_step=0.5)
        engine = make_engine(port)
        result = engine.execute(make_decision(quantity=2.0), make_context())
        assert result.status is ExecutionStatus.INVALID_REQUEST
        assert "quantity_below_min" in result.metadata["problems"]
        assert port.place_calls == []

    def test_notional_below_min_refuses(self) -> None:
        port = ScriptablePort()
        port.constraints = MarketConstraints(min_notional=1_000_000.0)
        engine = make_engine(port)
        result = engine.execute(make_decision(), make_context())
        assert result.status is ExecutionStatus.INVALID_REQUEST
        assert "notional_below_min" in result.metadata["problems"]
        assert port.place_calls == []

    def test_stop_rounds_away_from_entry_preserving_risk(self) -> None:
        port = ScriptablePort()
        port.constraints = MarketConstraints(price_tick=0.5)
        engine = make_engine(port)
        # LONG stop 95.20 -> must round DOWN (away from entry below).
        result = engine.execute(
            make_decision(entry=100.0, stop=95.2, target=110.3), make_context()
        )
        stop_call, target_call = port.place_calls[1], port.place_calls[2]
        assert stop_call[4] == pytest.approx(95.0)
        # Target rounds toward entry: 110.3 -> 110.0 with tick 0.5.
        assert target_call[4] == pytest.approx(110.0)
        reasons = {a.reason for a in (result.plan.adjustments if result.plan else [])}
        assert "price_tick_rounding_preserving_risk" in reasons
        assert "price_tick_rounding_reducing_reward" in reasons

    def test_short_stop_rounds_away_upward(self) -> None:
        port = ScriptablePort()
        port.constraints = MarketConstraints(price_tick=0.5)
        engine = make_engine(port)
        decision = make_decision(entry=100.0, stop=105.2, target=90.3)
        context = make_context(direction=PositionDirection.SHORT)
        engine.execute(decision, context)
        stop_call, target_call = port.place_calls[1], port.place_calls[2]
        # SHORT stop above entry rounds UP (away); target below rounds toward
        # entry, i.e. UP with a 0.5 tick: 90.3 -> 90.5.
        assert stop_call[4] == pytest.approx(105.5)
        assert target_call[4] == pytest.approx(90.5)

    def test_constraints_from_context_skip_port_query(self) -> None:
        port = ScriptablePort()
        engine = make_engine(port)
        constraints = MarketConstraints(quantity_step=1.0)
        context = make_context(constraints=constraints)
        engine.execute(make_decision(quantity=1.4), context)
        assert port.place_calls[0][3] == 1.0


# ---------------------------------------------------------------------------
# Lifecycle state machine
# ---------------------------------------------------------------------------


class TestLifecycleMachine:
    def test_illegal_transition_raises(self) -> None:
        from execution_engine import InvalidTransitionError, validate_transition

        with pytest.raises(InvalidTransitionError):
            validate_transition(OrderLifecycle.FILLED, OrderLifecycle.SUBMITTING)

    def test_unknown_cannot_go_straight_to_submitting(self) -> None:
        from execution_engine import InvalidTransitionError, validate_transition

        with pytest.raises(InvalidTransitionError):
            validate_transition(OrderLifecycle.UNKNOWN, OrderLifecycle.SUBMITTING)

    def test_self_transitions_are_noops(self) -> None:
        from execution_engine import validate_transition

        for state in OrderLifecycle:
            assert validate_transition(state, state) is False

    def test_rejected_is_terminal_and_distinct_from_unknown(self) -> None:
        from execution_engine import TERMINAL_LIFECYCLE_STATES

        assert OrderLifecycle.REJECTED in TERMINAL_LIFECYCLE_STATES
        assert OrderLifecycle.UNKNOWN not in TERMINAL_LIFECYCLE_STATES
        assert OrderLifecycle.REJECTED is not OrderLifecycle.UNKNOWN

    def test_lifecycle_maps_all_venue_statuses(self) -> None:
        from exchange.models import OrderStatus as OS
        from execution_engine import lifecycle_from_status

        assert lifecycle_from_status(OS.OPEN) is OrderLifecycle.ACCEPTED
        assert lifecycle_from_status(OS.PARTIALLY_FILLED) is OrderLifecycle.PARTIALLY_FILLED
        assert lifecycle_from_status(OS.FILLED) is OrderLifecycle.FILLED
        assert lifecycle_from_status(OS.CANCELED) is OrderLifecycle.CANCELLED
        assert lifecycle_from_status(OS.REJECTED) is OrderLifecycle.REJECTED
        assert lifecycle_from_status(OS.EXPIRED) is OrderLifecycle.EXPIRED
        assert lifecycle_from_status(OS.UNKNOWN) is OrderLifecycle.UNKNOWN

    def test_event_history_recorded(self) -> None:
        port = ScriptablePort()
        port.place_results.append(OrderSubmission(state=SubmissionState.UNKNOWN, message="t"))
        engine = make_engine(port)
        result = engine.execute(make_decision(), make_context())
        assert result.entry_order is not None
        states = [event.to_state for event in result.entry_order.events]
        assert states == [
            OrderLifecycle.SUBMITTING,
            OrderLifecycle.UNKNOWN,
        ]


# ---------------------------------------------------------------------------
# Determinism and secret safety
# ---------------------------------------------------------------------------


class TestDeterminismAndSecrets:
    def test_identical_inputs_identical_results(self) -> None:
        results = []
        for _ in range(2):
            port = ScriptablePort()
            engine = ExecutionEngine(port, clock_ms=fixed_clock(), id_generator=lambda: "x")
            results.append(engine.execute(make_decision(), make_context()))
        assert results[0] == results[1]

    def test_no_secrets_in_logs_across_success_and_failure_paths(self, caplog) -> None:
        caplog.set_level(logging.DEBUG)
        port = ScriptablePort()
        engine = make_engine(port)
        engine.execute(make_decision(), make_context())
        failing = ScriptablePort()
        failing.place_results.append(OrderSubmission(state=SubmissionState.UNKNOWN, message="x"))
        engine_two = make_engine(failing)
        engine_two.execute(make_decision(), make_context(idempotency_key="k2"))
        blocked = engine_two.execute(make_decision(), make_context(idempotency_key="k3"))
        assert blocked.status is ExecutionStatus.BLOCKED_RECONCILIATION
        assert caplog.records == []

    def test_result_metadata_carries_no_credential_like_keys(self) -> None:
        engine = make_engine(ScriptablePort())
        result = engine.execute(make_decision(), make_context())
        forbidden = {"api_key", "secret", "password", "uid", "token"}
        assert not forbidden & set(result.metadata)

    def test_frozen_models_reject_mutation(self) -> None:
        import dataclasses

        engine = make_engine(ScriptablePort())
        result = engine.execute(make_decision(), make_context())
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.status = ExecutionStatus.REJECTED  # type: ignore[misc]
