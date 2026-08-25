"""risk_engine: portfolio risk evaluation for the range-trading terminal.

Pure domain layer consuming :class:`signal_engine.Signal` values plus an
:class:`risk_engine.base.AccountRiskState` snapshot; produces immutable
:class:`RiskDecision` outcomes. No order placement, no I/O.
"""

from risk_engine.base import (
    AccountRiskState,
    OpenPosition,
    RejectionReason,
    RiskDecision,
    RiskDecisionStatus,
    StopMethod,
    TargetMethod,
    TradingConstraints,
)
from risk_engine.engine import RiskEngine

__version__ = "0.1.0"

__all__ = [
    "AccountRiskState",
    "OpenPosition",
    "RejectionReason",
    "RiskDecision",
    "RiskDecisionStatus",
    "RiskEngine",
    "StopMethod",
    "TargetMethod",
    "TradingConstraints",
    "__version__",
]
