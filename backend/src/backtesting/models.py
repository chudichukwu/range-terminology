"""Backtesting value types: configuration, equity tracking, results.

Everything is frozen, serializable and deterministic. The configuration
carries its own identity: ``config_hash`` is the SHA-256 of the canonical
JSON form, so two materially different configurations are always
distinguishable and any run can be reproduced from its stored config.
"""

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field

from backtesting.regime import MarketRegime
from market_data.models import Timeframe
from persistence.models import StoredTrade
from persistence.statistics import TradeStatistics

ENGINE_VERSION = "backtest-1.0.0"


def _canonical_json(payload: object) -> str:
    """Deterministic JSON: sorted keys everywhere, no whitespace."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


@dataclass(frozen=True)
class BacktestConfig:
    """Fully declarative, reproducible description of one backtest run.

    Attributes:
        symbol/timeframe/start_ms/end_ms: What to replay.
        initial_capital: Simulated starting equity (quote currency).
        range_config: ``RangeEngineFactory`` config (mode + params).
        signal_config: ``RangeSignalEngine`` config (zones, confirmation
            policy). Confirmation policies ignored/optional/required are
            honored exactly as in live trading.
        risk_config: ``RiskEngine`` overrides. ``fee_rate`` and
            ``slippage_rate`` default to the simulation assumptions below
            unless explicitly overridden here, keeping economics consistent.
        fee_rate/slippage_rate: Simulation execution assumptions (per side,
            fractions of notional).
        regime_lookback/threshold: Regime classifier settings.
        strategy_id/config_version: Identity of the strategy under test so
            historical results never become ambiguous.
        warmup_candles: Closed candles required before the first decision.
    """

    symbol: str
    timeframe: Timeframe | str
    start_ms: int
    end_ms: int
    initial_capital: float
    range_config: Mapping[str, object] = field(default_factory=dict)
    signal_config: Mapping[str, object] = field(default_factory=dict)
    risk_config: Mapping[str, object] = field(default_factory=dict)
    fee_rate: float = 0.0005
    slippage_rate: float = 0.0002
    regime_lookback: int = 20
    regime_threshold: float = 0.3
    strategy_id: str = "range-strategy"
    config_version: str = "v0"
    warmup_candles: int = 30

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("BacktestConfig.symbol must be non-empty")
        _ = Timeframe.parse(self.timeframe)  # validates; canonical form on demand
        for name in ("start_ms", "end_ms"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"BacktestConfig.{name} must be a positive integer ms")
        if self.start_ms >= self.end_ms:
            raise ValueError("BacktestConfig.start_ms must precede end_ms")
        if not math.isfinite(self.initial_capital) or self.initial_capital <= 0.0:
            raise ValueError("BacktestConfig.initial_capital must be finite and positive")
        for name in ("fee_rate", "slippage_rate"):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0 or value >= 0.1:
                raise ValueError(f"BacktestConfig.{name} must be within [0, 0.1)")
        if isinstance(self.regime_lookback, bool) or self.regime_lookback < 4:
            raise ValueError("BacktestConfig.regime_lookback must be an int >= 4")
        if not 0.0 < self.regime_threshold <= 1.0:
            raise ValueError("BacktestConfig.regime_threshold must be within (0, 1]")
        if self.warmup_candles < 2:
            raise ValueError("BacktestConfig.warmup_candles must be >= 2")
        if not self.strategy_id:
            raise ValueError("BacktestConfig.strategy_id must be non-empty")

    @property
    def resolved_timeframe(self) -> Timeframe:
        return Timeframe.parse(self.timeframe)

    @property
    def effective_risk_config(self) -> dict[str, object]:
        """Risk config with simulation economics injected as defaults."""
        merged: dict[str, object] = {
            "fee_rate": self.fee_rate,
            "slippage_rate": self.slippage_rate,
        }
        merged.update(dict(self.risk_config))
        return merged

    def to_json(self) -> str:
        """Canonical JSON representation (sorted keys, stable ordering)."""
        payload: dict[str, object] = {
            "symbol": self.symbol,
            "timeframe": self.resolved_timeframe.value,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "initial_capital": self.initial_capital,
            "range_config": dict(self.range_config),
            "signal_config": dict(self.signal_config),
            "risk_config": dict(self.risk_config),
            "fee_rate": self.fee_rate,
            "slippage_rate": self.slippage_rate,
            "regime_lookback": self.regime_lookback,
            "regime_threshold": self.regime_threshold,
            "strategy_id": self.strategy_id,
            "config_version": self.config_version,
            "warmup_candles": self.warmup_candles,
            "engine_version": ENGINE_VERSION,
        }
        return _canonical_json(payload)

    @property
    def config_hash(self) -> str:
        """SHA-256 identity of this configuration (includes engine version)."""
        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EquityPoint:
    """One realized-equity observation after a trade closes."""

    timestamp_ms: int
    equity: float
    peak_equity: float
    drawdown: float


@dataclass(frozen=True)
class ZoneObservation:
    """Where price sat inside the range at one decision point.

    Research-only context; the middle zone is a NO-TRADE region by strategy
    design and these counts make that observable.
    """

    timestamp_ms: int
    regime: MarketRegime
    range_status: str | None
    zone: str | None  # lower_edge | middle | upper_edge | outside | None
    tradable_range: bool


@dataclass(frozen=True)
class BacktestResult:
    """Structured outcome of one deterministic replay."""

    run_id: str
    config: BacktestConfig
    config_hash: str
    engine_version: str
    symbol: str
    timeframe: str
    period_start_ms: int
    period_end_ms: int
    candles_replayed: int
    decisions_evaluated: int
    initial_capital: float
    final_equity: float
    peak_equity: float
    max_drawdown: float
    trades: tuple[StoredTrade, ...]
    statistics: TradeStatistics
    equity_curve: tuple[EquityPoint, ...]
    observations: tuple[ZoneObservation, ...]
    regime_counts: dict[str, int]
    zone_counts: dict[str, int]
