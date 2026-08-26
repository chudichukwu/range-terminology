"""Pair analysis DTOs — composite view of market + range + regime + signal + risk.

All fields are populated on the backend from existing engines (range, signal,
risk, regime, market data). The frontend renders them as-is.
"""

from pydantic import BaseModel, Field


class RangeOut(BaseModel):
    high: float | None
    low: float | None
    width: float | None
    status: str  # RangeStatus.value
    confidence: float
    is_tradable: bool
    mode: str
    metadata: dict[str, object] = Field(default_factory=dict)


class RegimeOut(BaseModel):
    value: str  # MarketRegime.value
    lookback: int
    threshold: float
    efficiency_ratio: float | None = None


class SignalOut(BaseModel):
    direction: str  # SignalDirection.value
    reason: str  # SignalReason.value
    price: float | None
    position_in_range: float | None
    confidence: float
    confirmation: bool | None = None
    confirmation_policy: str | None = None
    range_high: float | None = None
    range_low: float | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class OscillatorOut(BaseModel):
    value: float | None
    type: str | None = None  # "rsi" | "stoch" | None
    overbought: float | None = None
    oversold: float | None = None
    is_confirmation: bool | None = None


class RiskOut(BaseModel):
    approved: bool
    status: str  # RiskDecisionStatus.value
    rejection_reason: str | None = None
    entry_price: float | None = None
    stop_price: float | None = None
    target_price: float | None = None
    position_quantity: float | None = None
    requested_quantity: float | None = None
    position_notional: float | None = None
    risk_amount: float | None = None
    reward_risk_ratio: float | None = None
    fees_estimate: float | None = None
    slippage_estimate: float | None = None
    leverage: float | None = None
    binding_constraint: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class CandleOutLite(BaseModel):
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
    is_closed: bool


class FreshnessOut(BaseModel):
    retrieved_at_ms: int
    age_ms: int | None = None
    is_stale: bool = False
    has_forming_candle: bool = False
    last_closed_timestamp_ms: int | None = None


class AnalysisOut(BaseModel):
    symbol: str
    timeframe: str
    strategy_id: str | None = None
    strategy_name: str | None = None
    ticker_last: float | None = None
    ticker_bid: float | None = None
    ticker_ask: float | None = None
    ticker_timestamp_ms: int | None = None
    candles: list[CandleOutLite] = Field(default_factory=list)
    quality_issues: list[str] = Field(default_factory=list)
    is_analysis_safe: bool = True
    range: RangeOut
    regime: RegimeOut
    signal: SignalOut
    oscillator: OscillatorOut
    risk: RiskOut | None = None
    freshness: FreshnessOut
