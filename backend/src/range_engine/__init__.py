"""range_engine: pluggable range-detection domain for the range-trading terminal.

Pure domain layer: no network, no filesystem, no exchange SDKs. Pandas is the
input boundary format; results are immutable :class:`RangeState` values carrying
an explicit :class:`RangeStatus`.
"""

from range_engine.base import (
    REQUIRED_OHLCV_COLUMNS,
    RangeDetector,
    RangeState,
    RangeStatus,
    validate_ohlcv,
)
from range_engine.factory import RangeEngineFactory
from range_engine.manual import ManualRangeDetector
from range_engine.oscillator import OscillatorConfirmedRangeDetector
from range_engine.structural import StructuralRangeDetector
from range_engine.volatility import VolatilityRangeDetector

__version__ = "0.1.0"

__all__ = [
    "REQUIRED_OHLCV_COLUMNS",
    "ManualRangeDetector",
    "OscillatorConfirmedRangeDetector",
    "RangeDetector",
    "RangeEngineFactory",
    "RangeState",
    "RangeStatus",
    "StructuralRangeDetector",
    "VolatilityRangeDetector",
    "__version__",
    "validate_ohlcv",
]
