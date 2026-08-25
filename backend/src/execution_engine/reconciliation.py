"""Reconciliation: comparing local execution beliefs against venue truth.

The reconciler never guesses and never silently rewrites dangerous
discrepancies. Authoritative venue snapshots are returned so the engine can
apply them through validated lifecycle transitions (the only way out of
UNKNOWN); material mismatches surface as explicit findings flagged
``requires_policy`` for higher-level decisions.
"""

from dataclasses import dataclass, field
from enum import Enum

from exchange.base import ExchangePort
from exchange.errors import ExchangeError, ExchangeErrorCode
from exchange.models import Order, Position, PositionDirection
from execution_engine.base import (
    TERMINAL_LIFECYCLE_STATES,
    OrderLifecycle,
    lifecycle_from_status,
)
from execution_engine.models import ExecutionResult, OrderRecord

_FILL_TOLERANCE = 1e-9


class DiscrepancyType(Enum):
    """What reconciliation concluded about one locally tracked order."""

    MATCH = "match"
    RESOLVED_FROM_UNKNOWN = "resolved_from_unknown"
    FILL_QUANTITY_MISMATCH = "fill_quantity_mismatch"
    STATUS_MISMATCH = "status_mismatch"
    MISSING_REMOTELY = "missing_remotely"
    UNTRACKED_REMOTELY = "untracked_remotely"
    MALFORMED_RESPONSE = "malformed_response"
    VENUE_ERROR = "venue_error"


#: Findings serious enough that higher-level policy must decide next steps.
#: MISSING_REMOTELY is added dynamically: venues purge terminal orders, so it
#: only demands policy when the local state is still live.
_POLICY_FINDINGS: frozenset[DiscrepancyType] = frozenset(
    {
        DiscrepancyType.FILL_QUANTITY_MISMATCH,
        DiscrepancyType.UNTRACKED_REMOTELY,
        DiscrepancyType.MALFORMED_RESPONSE,
        DiscrepancyType.VENUE_ERROR,
    }
)


@dataclass(frozen=True)
class OrderFinding:
    """Reconciliation verdict for one locally tracked order."""

    role_value: str
    client_order_id: str | None
    venue_order_id: str | None
    finding: DiscrepancyType
    detail: str
    local_state: OrderLifecycle | None = None
    remote_lifecycle: OrderLifecycle | None = None
    local_filled: float | None = None
    remote_filled: float | None = None
    #: Authoritative venue snapshot to apply locally, when one exists.
    authoritative_order: Order | None = None


@dataclass(frozen=True)
class PositionFinding:
    """Reconciliation verdict for the expected post-trade position."""

    checked: bool
    match: bool | None
    detail: str
    actual_side: PositionDirection | None = None
    actual_quantity: float | None = None


_NO_POSITION_FINDING = PositionFinding(
    checked=False, match=None, detail="position check not requested"
)


@dataclass(frozen=True)
class ReconciliationReport:
    """Full comparison result for one execution on one symbol."""

    symbol: str
    order_findings: tuple[OrderFinding, ...] = ()
    untracked_remote_orders: tuple[Order, ...] = ()
    position_finding: PositionFinding = _NO_POSITION_FINDING
    requires_policy: bool = False
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ReconciliationOutcome:
    """Reconciliation report plus the refreshed execution snapshot."""

    report: ReconciliationReport
    result: ExecutionResult | None = None


class ExecutionReconciler:
    """Compares locally tracked orders with authoritative venue state."""

    def __init__(self, exchange: ExchangePort) -> None:
        self._exchange = exchange

    def reconcile_orders(
        self,
        symbol: str,
        records: tuple[OrderRecord, ...] | list[OrderRecord],
        *,
        client_id_prefixes: tuple[str, ...] = (),
        expected_position: Position | None = None,
    ) -> ReconciliationReport:
        """Compare ``records`` against the venue and return explicit findings.

        Args:
            symbol: Instrument reconciled.
            records: Locally tracked order snapshots, in stable order.
            client_id_prefixes: Prefixes identifying this engine's client
                order ids; remote open orders matching a prefix but absent
                from ``records`` are reported as UNTRACKED_REMOTELY.
            expected_position: Optional expected post-trade position to check
                against :meth:`ExchangePort.get_positions`.

        Returns:
            A :class:`ReconciliationReport`; findings carry authoritative
            venue orders where available. ``requires_policy`` is True when any
            finding needs a human/policy decision rather than blind adoption.
        """
        findings: list[OrderFinding] = []
        requires_policy = False
        for record in records:
            finding = self._reconcile_record(symbol, record)
            findings.append(finding)
            if finding.finding in _POLICY_FINDINGS:
                requires_policy = True
            if (
                finding.finding is DiscrepancyType.MISSING_REMOTELY
                and record.state not in TERMINAL_LIFECYCLE_STATES
            ):
                requires_policy = True
        untracked = self._find_untracked_remote(symbol, records, client_id_prefixes)
        if untracked:
            requires_policy = True
        position_finding = (
            self._check_position(symbol, expected_position)
            if expected_position is not None
            else _NO_POSITION_FINDING
        )
        if position_finding.checked and position_finding.match is False:
            requires_policy = True
        return ReconciliationReport(
            symbol=symbol,
            order_findings=tuple(findings),
            untracked_remote_orders=untracked,
            position_finding=position_finding,
            requires_policy=requires_policy,
        )

    # ----- internals -----

    def _reconcile_record(self, symbol: str, record: OrderRecord) -> OrderFinding:
        """Build the verdict for one tracked order."""
        try:
            remote = self._exchange.get_order(
                symbol,
                order_id=record.venue_order_id,
                client_order_id=record.plan.client_order_id,
            )
        except ExchangeError as exc:
            if exc.code is ExchangeErrorCode.ORDER_NOT_FOUND:
                terminal_locally = record.is_terminal
                detail = (
                    "venue has no such order; local state is terminal"
                    if terminal_locally
                    else "venue has no such order while local state is live"
                )
                return OrderFinding(
                    role_value=record.plan.role.value,
                    client_order_id=record.plan.client_order_id,
                    venue_order_id=record.venue_order_id,
                    finding=DiscrepancyType.MISSING_REMOTELY,
                    detail=detail,
                    local_state=record.state,
                    remote_lifecycle=None,
                    local_filled=record.filled_quantity,
                    remote_filled=None,
                    authoritative_order=None,
                )
            return OrderFinding(
                role_value=record.plan.role.value,
                client_order_id=record.plan.client_order_id,
                venue_order_id=record.venue_order_id,
                finding=DiscrepancyType.VENUE_ERROR,
                detail=f"venue query failed: {exc.code.value}",
                local_state=record.state,
                local_filled=record.filled_quantity,
            )
        remote_lifecycle = lifecycle_from_status(remote.status)
        remote_filled = min(remote.filled_quantity, record.requested_quantity)
        fills_match = abs(remote_filled - record.filled_quantity) <= _FILL_TOLERANCE * max(
            1.0, record.filled_quantity
        )
        if record.is_unknown:
            finding_type = DiscrepancyType.RESOLVED_FROM_UNKNOWN
            detail = f"unknown resolved to {remote_lifecycle.value}"
        elif not fills_match:
            finding_type = DiscrepancyType.FILL_QUANTITY_MISMATCH
            detail = (
                f"local filled {record.filled_quantity} vs remote {remote_filled}; "
                "authoritative data attached"
            )
        elif remote_lifecycle is not record.state:
            finding_type = DiscrepancyType.STATUS_MISMATCH
            detail = f"local {record.state.value} vs remote {remote_lifecycle.value}"
        else:
            finding_type = DiscrepancyType.MATCH
            detail = "local state matches venue"
        return OrderFinding(
            role_value=record.plan.role.value,
            client_order_id=record.plan.client_order_id,
            venue_order_id=record.venue_order_id or remote.id,
            finding=finding_type,
            detail=detail,
            local_state=record.state,
            remote_lifecycle=remote_lifecycle,
            local_filled=record.filled_quantity,
            remote_filled=remote_filled,
            authoritative_order=remote,
        )

    def _find_untracked_remote(
        self,
        symbol: str,
        records: tuple[OrderRecord, ...] | list[OrderRecord],
        prefixes: tuple[str, ...],
    ) -> tuple[Order, ...]:
        """Remote open orders carrying our prefixes but tracked nowhere."""
        if not prefixes:
            return ()
        known_client_ids = {
            record.plan.client_order_id for record in records if record.plan.client_order_id
        }
        known_venue_ids = {record.venue_order_id for record in records if record.venue_order_id}
        try:
            open_orders = self._exchange.get_open_orders(symbol)
        except ExchangeError:
            return ()
        untracked: list[Order] = []
        for order in open_orders:
            cid = order.client_order_id
            matches_prefix = cid is not None and any(cid.startswith(p) for p in prefixes)
            known = cid in known_client_ids or (
                order.id is not None and order.id in known_venue_ids
            )
            if matches_prefix and not known:
                untracked.append(order)
        return tuple(untracked)

    def _check_position(self, symbol: str, expected: Position | None) -> PositionFinding:
        """Compare expected vs actual same-symbol position."""
        assert expected is not None
        try:
            positions = self._exchange.get_positions()
        except ExchangeError as exc:
            return PositionFinding(
                checked=True, match=None, detail=f"unavailable: {exc.code.value}"
            )
        actual = next((p for p in positions if p.symbol == symbol), None)
        if actual is None:
            return PositionFinding(
                checked=True,
                match=False,
                detail=f"expected {expected.side.value} {expected.quantity}, found none",
                actual_side=None,
                actual_quantity=None,
            )
        same_side = actual.side is expected.side
        quantity_ok = abs(actual.quantity - expected.quantity) <= _FILL_TOLERANCE * max(
            1.0, expected.quantity
        )
        if same_side and quantity_ok:
            return PositionFinding(
                checked=True,
                match=True,
                detail="position matches expectation",
                actual_side=actual.side,
                actual_quantity=actual.quantity,
            )
        return PositionFinding(
            checked=True,
            match=False,
            detail=(
                f"expected {expected.side.value} {expected.quantity}; "
                f"found {actual.side.value} {actual.quantity}"
            ),
            actual_side=actual.side,
            actual_quantity=actual.quantity,
        )
