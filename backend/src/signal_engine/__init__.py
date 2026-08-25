"""signal_engine: range-trading signal evaluation for the trading terminal.

Pure domain layer consuming approved :class:`range_engine.base.RangeState`
values plus a market price; produces immutable :class:`Signal` results.
No sizing, risk, execution, exchange access, or I/O lives here.
"""

from signal_engine.base import ConfirmationPolicy, Signal, SignalDirection, SignalReason
from signal_engine.engine import RangeSignalEngine

__version__ = "0.1.0"

__all__ = [
    "ConfirmationPolicy",
    "RangeSignalEngine",
    "Signal",
    "SignalDirection",
    "SignalReason",
    "__version__",
]
