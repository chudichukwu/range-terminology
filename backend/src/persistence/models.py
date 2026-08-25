"""Persistence-layer value types.

These are the normalized shapes stored and returned by repositories. The
layer records authoritative FACTS (validated candles, completed trades);
derived statistics live in :mod:`persistence.statistics` and are always
computed from those facts, never stored as authority.

Types compose the existing domain models instead of duplicating them:
candles are Phase 6 :class:`~market_data.models.MarketCandle` values, trade
direction reuses :class:`~exchange.models.PositionDirection`, and the
execution-to-trade helper consumes Phase 5
:class:`~execution_engine.models.ExecutionResult` without modifying it.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from enum import Enum

from exchange.models import PositionDirection
from market_data.models import DataQualityReport


class QualityStatus(Enum):
    """Stored quality verdict for one ingested dataset window.

    Derived from the Phase 6 report at ingestion time — persistence never
    re-validates and never upgrades questionable data to clean.
    """

    CLEAN = "clean"
    WARNINGS = "warnings"


#: Maps a Phase 6 quality report onto its stored status.
def quality_status_of(report: DataQualityReport) -> QualityStatus:
    return QualityStatus.CLEAN if report.is_clean else QualityStatus.WARNINGS


@dataclass(frozen=True)
class DatasetSummary:
    """Persistent metadata describing one dataset window.

    Answers "what historical data do we actually possess?" for later
    backtesting sufficiency checks.
    """

    symbol: str
    timeframe: str
    source: str
    candle_count: int
    first_timestamp_ms: int | None
    last_timestamp_ms: int | None
    quality_status: QualityStatus
    ingested_at_ms: int
    updated_at_ms: int


@dataclass(frozen=True)
class IngestionResult:
    """Outcome of one idempotent batch ingestion.

    Attributes:
        inserted: New candles written.
        updated: Existing candles whose stored facts changed (e.g. a forming
            candle that has since closed, or revised volume).
        unchanged: Existing candles identical to the incoming facts.
        summary: Recomputed dataset metadata after the write.
    """

    inserted: int
    updated: int
    unchanged: int
    summary: DatasetSummary


class TradeStatus(Enum):
    """Lifecycle state of a persisted trade."""

    OPEN = "open"
    CLOSED = "closed"


class TradeResult(Enum):
    """Classification of a COMPLETED trade's outcome.

    Definitions (deliberately explicit):
        WIN       — realized P&L strictly above the breakeven epsilon.
        LOSS      — realized P&L strictly below minus the epsilon.
        BREAKEVEN — |realized P&L| within the epsilon (default 1e-9).
    Open trades carry no result at all; none is ever invented.
    """

    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"


#: Default absolute-PnL tolerance under which a closed trade is BREAKEVEN.
DEFAULT_BREAKEVEN_EPSILON = 1e-9


def classify_result(
    realized_pnl: float | None,
    *,
    epsilon: float = DEFAULT_BREAKEVEN_EPSILON,
) -> TradeResult | None:
    """Classify a realized P&L, or ``None`` when no P&L exists yet."""
    if realized_pnl is None:
        return None
    if not math.isfinite(realized_pnl):
        raise ValueError(f"realized_pnl must be finite, got {realized_pnl}")
    if realized_pnl > epsilon:
        return TradeResult.WIN
    if realized_pnl < -epsilon:
        return TradeResult.LOSS
    return TradeResult.BREAKEVEN


@dataclass(frozen=True)
class TradeContext:
    """Typed, extensible context explaining WHY a trade was taken.

    Common fields are explicit for queryability and discipline; anything not
    yet worth a column (future RSI value/confirmation/divergence, regime
    labels, ...) goes into ``extra`` as JSON-serializable diagnostics. This
    keeps the trade table stable while context evolves with the strategy.
    Manual journaling ("what did I think?") deliberately does NOT live here.
    """

    range_mode: str | None = None
    range_high: float | None = None
    range_low: float | None = None
    range_width: float | None = None
    range_confidence: float | None = None
    signal_direction: str | None = None
    signal_reason: str | None = None
    position_in_range: float | None = None
    confirmation: bool | None = None
    stop_distance: float | None = None
    target_distance: float | None = None
    risk_percent: float | None = None
    timeframe: str | None = None
    strategy_config_version: str | None = None
    extra: dict[str, object] = field(default_factory=dict)

    def to_json(self) -> str:
        payload: dict[str, object] = {
            "range_mode": self.range_mode,
            "range_high": self.range_high,
            "range_low": self.range_low,
            "range_width": self.range_width,
            "range_confidence": self.range_confidence,
            "signal_direction": self.signal_direction,
            "signal_reason": self.signal_reason,
            "position_in_range": self.position_in_range,
            "confirmation": self.confirmation,
            "stop_distance": self.stop_distance,
            "target_distance": self.target_distance,
            "risk_percent": self.risk_percent,
            "timeframe": self.timeframe,
            "strategy_config_version": self.strategy_config_version,
            "extra": dict(self.extra),
        }
        return json.dumps(payload, sort_keys=True)

    @staticmethod
    def from_json(raw: str) -> TradeContext:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("TradeContext JSON must be an object")
        extra_raw = data.get("extra")
        extra = {str(k): v for k, v in extra_raw.items()} if isinstance(extra_raw, dict) else {}
        return TradeContext(
            range_mode=_opt_str(data.get("range_mode")),
            range_high=_opt_float(data.get("range_high")),
            range_low=_opt_float(data.get("range_low")),
            range_width=_opt_float(data.get("range_width")),
            range_confidence=_opt_float(data.get("range_confidence")),
            signal_direction=_opt_str(data.get("signal_direction")),
            signal_reason=_opt_str(data.get("signal_reason")),
            position_in_range=_opt_float(data.get("position_in_range")),
            confirmation=_opt_bool(data.get("confirmation")),
            stop_distance=_opt_float(data.get("stop_distance")),
            target_distance=_opt_float(data.get("target_distance")),
            risk_percent=_opt_float(data.get("risk_percent")),
            timeframe=_opt_str(data.get("timeframe")),
            strategy_config_version=_opt_str(data.get("strategy_config_version")),
            extra=extra,
        )


def _opt_str(value: object) -> str | None:
    return str(value) if value is not None else None


def _opt_float(value: object) -> float | None:
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _opt_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


@dataclass(frozen=True)
class StoredTrade:
    """One recorded ACTUAL trade (never an individual order).

    A trade may span several Phase 5 orders/fills; persistence stores the
    resulting economic outcome plus provenance, not the execution state
    machine. Facts only: statistics are derived elsewhere.

    Validation invariants:
        OPEN trades must have no exit price / close time / P&L / result.
        CLOSED trades must have exit price and close time; P&L-bearing
        closed trades get their result classified automatically unless one
        was supplied consistently.

    Attributes:
        realized_r: Realized R multiple = realized_pnl / risk_amount when
            both exist; computed here from authoritative inputs, never guessed.
    """

    trade_id: str
    symbol: str
    direction: PositionDirection
    quantity: float
    entry_price: float
    opened_at_ms: int
    status: TradeStatus = TradeStatus.OPEN
    execution_ref: str | None = None
    timeframe: str | None = None
    exit_price: float | None = None
    closed_at_ms: int | None = None
    realized_pnl: float | None = None
    fees: float | None = None
    slippage: float | None = None
    risk_amount: float | None = None
    realized_r: float | None = None
    result: TradeResult | None = None
    strategy_id: str | None = None
    config_hash: str | None = None
    context: TradeContext | None = None
    created_at_ms: int = 0
    updated_at_ms: int = 0

    def __post_init__(self) -> None:
        if not self.trade_id or not isinstance(self.trade_id, str):
            raise ValueError("StoredTrade.trade_id must be a non-empty string")
        if not self.symbol:
            raise ValueError("StoredTrade.symbol must be non-empty")
        for name in ("quantity", "entry_price"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"StoredTrade.{name} must be finite and positive, got {value}")
        if self.opened_at_ms <= 0:
            raise ValueError("StoredTrade.opened_at_ms must be a positive ms timestamp")

        if self.status is TradeStatus.OPEN:
            for name in ("exit_price", "closed_at_ms", "realized_pnl"):
                if getattr(self, name) is not None:
                    raise ValueError(
                        f"Open trade cannot carry {name}; close the trade explicitly"
                    )
            if self.result is not None:
                raise ValueError("Open trade cannot carry a result classification")
        else:
            exit_ok = (
                self.exit_price is not None
                and math.isfinite(self.exit_price)
                and self.exit_price > 0
            )
            if not exit_ok:
                raise ValueError("Closed trade requires a positive exit_price")
            if self.closed_at_ms is None or self.closed_at_ms < self.opened_at_ms:
                raise ValueError("Closed trade requires closed_at_ms >= opened_at_ms")

        for name in ("fees", "slippage"):
            value = getattr(self, name)
            if value is not None and (not math.isfinite(value) or value < 0.0):
                raise ValueError(f"StoredTrade.{name} must be non-negative when present")
        if self.risk_amount is not None and (
            not math.isfinite(self.risk_amount) or self.risk_amount <= 0.0
        ):
            raise ValueError("StoredTrade.risk_amount must be positive when present")
        if self.realized_r is not None and not math.isfinite(self.realized_r):
            raise ValueError("StoredTrade.realized_r must be finite when present")

        if self.status is TradeStatus.CLOSED:
            expected_result = classify_result(self.realized_pnl)
            if self.result is None:
                object.__setattr__(self, "result", expected_result)
            elif expected_result is not None and self.result is not expected_result:
                raise ValueError(
                    f"Supplied result {self.result.value} contradicts realized P&L "
                    f"classification {expected_result.value}"
                )
            if (
                self.realized_r is None
                and self.realized_pnl is not None
                and self.risk_amount is not None
                and self.risk_amount > 0.0
            ):
                object.__setattr__(
                    self, "realized_r", round(self.realized_pnl / self.risk_amount, 6)
                )

    @property
    def gross_pnl(self) -> float | None:
        """Realized P&L net of fees when both are known."""
        if self.realized_pnl is None:
            return None
        return self.realized_pnl - (self.fees or 0.0)


@dataclass(frozen=True)
class TradeUpdate:
    """Partial, validated update closing an open trade."""

    exit_price: float
    closed_at_ms: int
    realized_pnl: float | None = None
    fees: float | None = None
    slippage: float | None = None
    risk_amount: float | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.exit_price) or self.exit_price <= 0.0:
            raise ValueError("TradeUpdate.exit_price must be finite and positive")
        if self.closed_at_ms <= 0:
            raise ValueError("TradeUpdate.closed_at_ms must be a positive ms timestamp")


@dataclass(frozen=True)
class BacktestRunRecord:
    """Persisted identity + headline facts of one backtest run.

    Stores the FULL configuration JSON and engine version so any run is
    reproducible; statistics are stored as a derived snapshot (clearly not
    authoritative — trades remain the source of truth).
    """

    run_id: str
    config_hash: str
    symbol: str
    timeframe: str
    period_start_ms: int
    period_end_ms: int
    initial_capital: float
    final_equity: float
    peak_equity: float
    max_drawdown: float
    total_trades: int
    stats_json: str
    config_json: str
    engine_version: str
    created_at_ms: int

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("BacktestRunRecord.run_id must be non-empty")
        if not self.config_hash:
            raise ValueError("BacktestRunRecord.config_hash must be non-empty")
        if not self.symbol:
            raise ValueError("BacktestRunRecord.symbol must be non-empty")
        if self.initial_capital <= 0.0:
            raise ValueError("BacktestRunRecord.initial_capital must be positive")
