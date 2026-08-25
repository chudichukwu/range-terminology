"""execution_engine: safe decision-to-order execution for the trading terminal.

Turns approved :class:`risk_engine.base.RiskDecision` values into exchange
orders through :class:`exchange.base.ExchangePort`, tracking an explicit order
lifecycle with idempotent submissions, fill-aware protective orders and
reconciliation-first handling of UNKNOWN outcomes.

The engine never generates signals, never recomputes risk, never overrides an
approved decision, and never touches a venue SDK directly.
"""

from execution_engine.base import (
    LIFECYCLE_TRANSITIONS,
    TERMINAL_EXECUTION_STATUSES,
    TERMINAL_LIFECYCLE_STATES,
    ExecutionStatus,
    InvalidTransitionError,
    OrderLifecycle,
    OrderRole,
    PositionAction,
    TimeInForce,
    classify_position_action,
    entry_side,
    lifecycle_from_status,
    protective_side,
    validate_transition,
)
from execution_engine.engine import ExecutionEngine
from execution_engine.models import (
    ExecutionContext,
    ExecutionPlan,
    ExecutionResult,
    LifecycleEvent,
    OrderRecord,
    PlanAdjustment,
    PlannedOrder,
)
from execution_engine.reconciliation import (
    DiscrepancyType,
    ExecutionReconciler,
    OrderFinding,
    PositionFinding,
    ReconciliationOutcome,
    ReconciliationReport,
)

__version__ = "0.1.0"

__all__ = [
    "DiscrepancyType",
    "ExecutionContext",
    "ExecutionEngine",
    "ExecutionPlan",
    "ExecutionReconciler",
    "ExecutionResult",
    "ExecutionStatus",
    "InvalidTransitionError",
    "LIFECYCLE_TRANSITIONS",
    "LifecycleEvent",
    "OrderFinding",
    "OrderLifecycle",
    "OrderRecord",
    "OrderRole",
    "PlanAdjustment",
    "PlannedOrder",
    "PositionAction",
    "PositionFinding",
    "ReconciliationOutcome",
    "ReconciliationReport",
    "TERMINAL_EXECUTION_STATUSES",
    "TERMINAL_LIFECYCLE_STATES",
    "TimeInForce",
    "__version__",
    "classify_position_action",
    "entry_side",
    "lifecycle_from_status",
    "protective_side",
    "validate_transition",
]
