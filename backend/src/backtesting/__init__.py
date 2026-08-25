"""backtesting: deterministic research replay through the live strategy engines.

Historical closed candles are replayed chronologically through the SAME
Range/Signal/Risk engines used by the live system, executed by a documented
conservative OHLCV simulator. No alternate strategy implementations, no
network, no randomness: identical data + config always yield an identical
result.

MEASURE -> VALIDATE -> ANALYZE -> THEN OPTIMIZE. This package is a
measurement instrument; it never searches parameters or reports "best".
"""

from backtesting.models import (
    ENGINE_VERSION,
    BacktestConfig,
    BacktestResult,
    EquityPoint,
    ZoneObservation,
)
from backtesting.regime import (
    DEFAULT_REGIME_LOOKBACK,
    DEFAULT_REGIME_THRESHOLD,
    MarketRegime,
    classify_regime,
    efficiency_ratio,
)
from backtesting.runner import BacktestRunner
from backtesting.simulation import (
    resolve_protective_exit,
    simulate_entry_fill,
    simulate_exit_fill,
    wilder_atr,
)

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_REGIME_LOOKBACK",
    "DEFAULT_REGIME_THRESHOLD",
    "ENGINE_VERSION",
    "BacktestConfig",
    "BacktestResult",
    "BacktestRunner",
    "EquityPoint",
    "MarketRegime",
    "ZoneObservation",
    "__version__",
    "classify_regime",
    "efficiency_ratio",
    "resolve_protective_exit",
    "simulate_entry_fill",
    "simulate_exit_fill",
    "wilder_atr",
]
