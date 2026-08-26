"""Pair analysis service — orchestrates existing domain engines, no new domain logic.

Exposes RangeState + MarketRegime + Signal + (optional) RiskDecision + oscillator
metadata for a symbol/timeframe via the already-tested engines. The frontend
calls this for dashboard rendering; it never re-derives these values.
"""

from __future__ import annotations

import math
import time
from typing import Any

import pandas as pd

from app_layer.errors import ValidationError
from app_layer.services.markets import MarketDataFacade
from app_layer.services.strategies import StrategyConfigService
from backtesting.regime import MarketRegime, classify_regime, efficiency_ratio
from market_data.models import CandleDataset
from range_engine.base import RangeState
from range_engine.factory import RangeEngineFactory
from risk_engine.base import AccountRiskState, RiskDecision
from risk_engine.engine import RiskEngine
from signal_engine.base import Signal
from signal_engine.engine import RangeSignalEngine

_STALE_THRESHOLD_MS = 5 * 60_000  # 5 minutes


def _to_df(dataset: CandleDataset) -> pd.DataFrame:
    rows = [
        {
            "timestamp": c.timestamp,
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "volume": 0.0 if c.volume is None else c.volume,
        }
        for c in dataset.candles
        if c.is_closed
    ]
    # Ensure DataFrame has required columns even when empty
    if not rows:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
    return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])


def _safe_float(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except Exception:
        return None


class PairAnalysisService:
    """Application service for dashboard pair analysis."""

    def __init__(
        self,
        markets: MarketDataFacade,
        strategies: StrategyConfigService,
    ) -> None:
        self._markets = markets
        self._strategies = strategies

    def analyze(
        self,
        actor: Any,
        symbol: str,
        timeframe: str,
        *,
        strategy_id: str | None = None,
        limit: int = 200,
        now_ms: int | None = None,
    ) -> dict[str, Any]:
        # --- fetch market data (delegates validation to facade) ---
        dataset: CandleDataset = self._markets.candles(
            symbol, timeframe, limit=limit, include_current=False
        )
        ticker: dict[str, Any] | None = None
        try:
            ticker = self._markets.ticker(symbol)
        except Exception:
            ticker = None  # ticker is best-effort; analysis proceeds

        # --- resolve strategy configs (if provided) ---
        range_config: dict[str, Any] = {}
        signal_config: dict[str, Any] = {}
        risk_config: dict[str, Any] = {}
        strategy_name: str | None = None
        if strategy_id:
            cfg = self._strategies.get(actor, strategy_id)
            payload = cfg.payload()
            rc = payload.get("range_config")
            sc = payload.get("signal_config")
            rk = payload.get("risk_config")
            range_config = dict(rc) if isinstance(rc, dict) else {}
            signal_config = dict(sc) if isinstance(sc, dict) else {}
            risk_config = dict(rk) if isinstance(rk, dict) else {}
            strategy_name = cfg.name

        # Use effective configs flattened via factory defaults where needed
        # Range detection
        df = _to_df(dataset)
        range_state: RangeState
        try:
            range_state = RangeEngineFactory.detect(df, range_config if range_config else None)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        # Market regime — deterministic from closed closes
        closes = [c.close for c in dataset.candles if c.is_closed]
        raw_lookback = risk_config.get("regime_lookback")
        if raw_lookback is None:
            raw_lookback = signal_config.get("regime_lookback", 20)
        regime_lookback = 20
        if isinstance(raw_lookback, bool):
            regime_lookback = 20
        elif isinstance(raw_lookback, (int, float)):
            try:
                regime_lookback = int(raw_lookback)
            except Exception:
                regime_lookback = 20
        elif isinstance(raw_lookback, str) and raw_lookback.strip().isdigit():
            regime_lookback = int(raw_lookback)
        if regime_lookback < 4:
            regime_lookback = 20
        raw_thr = signal_config.get("regime_threshold", 0.3)
        regime_threshold = 0.3
        if isinstance(raw_thr, (int, float)) and not isinstance(raw_thr, bool):
            try:
                regime_threshold = float(raw_thr)
            except Exception:
                regime_threshold = 0.3
        if not 0.0 < regime_threshold <= 1.0:
            regime_threshold = 0.3
        try:
            regime = classify_regime(closes, lookback=regime_lookback, threshold=regime_threshold)
        except ValueError:
            regime = MarketRegime.INSUFFICIENT_DATA
        er: float | None = None
        try:
            window = closes[-regime_lookback:] if len(closes) >= regime_lookback else []
            er = efficiency_ratio(window) if window else None
        except Exception:
            er = None

        # Signal — evaluate against last close price
        last_price: float | None = closes[-1] if closes else None
        if ticker and ticker.get("last") is not None and last_price is None:
            last_price = _safe_float(ticker.get("last"))
        signal: Signal
        try:
            engine = RangeSignalEngine(signal_config if signal_config else None)
            price_for_signal = last_price if last_price is not None else 0.0
            # If no price, signal will be NON_TRADABLE or error; we handle
            if last_price is None:
                # create a NONE signal manually by evaluating with is_tradable check
                from signal_engine.base import SignalDirection, SignalReason

                signal = Signal(
                    direction=SignalDirection.NONE,
                    reason=SignalReason.NON_TRADABLE_RANGE,
                    price=0.0,
                    range_high=None,
                    range_low=None,
                    position_in_range=None,
                    confidence=0.0,
                    confirmation=None,
                    metadata={"reason": "no_price_available"},
                )
            else:
                signal = engine.evaluate(
                    price_for_signal,
                    range_state,
                    config=signal_config if signal_config else None,
                )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        # Oscillator metadata (from range_state metadata when oscillator_confirmed)
        osc_value = _safe_float(range_state.metadata.get("oscillator_value"))
        osc_raw = range_state.metadata.get("oscillator")
        osc_type = osc_raw if isinstance(osc_raw, str) else None
        osc_overbought = _safe_float(
            range_state.metadata.get("overbought_threshold")
        )
        osc_oversold = _safe_float(
            range_state.metadata.get("oversold_threshold")
        )
        confirmation_val = range_state.metadata.get("confirmation")
        confirmation_bool: bool | None = (
            confirmation_val if isinstance(confirmation_val, bool) else None
        )

        # Risk preview — only when signal is actionable; uses a default PAPER account
        risk_decision: RiskDecision | None = None
        if signal.is_actionable and last_price is not None:
            # Default PAPER account snapshot — caller can override in future via query
            account = AccountRiskState(
                equity=10000.0,
                available_balance=10000.0,
                peak_equity=10000.0,
                daily_start_equity=10000.0,
                open_positions=(),
                total_exposure=0.0,
                consecutive_losses=0,
                realized_pnl=0.0,
            )
            risk_engine = RiskEngine(risk_config if risk_config else None)
            try:
                risk_decision = risk_engine.evaluate(signal, account, price=last_price)
            except ValueError:
                risk_decision = None

        # Freshness
        now = now_ms if now_ms is not None else int(time.time_ns() // 1_000_000)
        retrieved_at = dataset.retrieved_at_ms or now
        age_ms = now - retrieved_at if retrieved_at else None
        is_stale = age_ms is not None and age_ms > _STALE_THRESHOLD_MS
        has_forming = any(not c.is_closed for c in dataset.candles)
        last_closed_ts = None
        for c in reversed(dataset.candles):
            if c.is_closed:
                last_closed_ts = c.timestamp
                break

        # Build response dict matching AnalysisOut shape
        def _finite_or_none(v: float) -> float | None:
            return None if v is None or not math.isfinite(v) else float(v)

        # Handle NaN bounds
        rh = (
            _finite_or_none(range_state.range_high)
            if not math.isnan(range_state.range_high)
            else None
        )
        rl = (
            _finite_or_none(range_state.range_low)
            if not math.isnan(range_state.range_low)
            else None
        )
        width = None
        if rh is not None and rl is not None:
            width = rh - rl

        risk_payload: dict[str, Any] | None = None
        if risk_decision is not None:
            bc_raw = risk_decision.metadata.get("binding_constraint")
            binding = bc_raw if isinstance(bc_raw, str) else None
            rr = risk_decision.rejection_reason
            risk_payload = {
                "approved": risk_decision.approved,
                "status": risk_decision.status.value,
                "rejection_reason": rr.value if rr else None,
                "entry_price": risk_decision.entry_price,
                "stop_price": risk_decision.stop_price,
                "target_price": risk_decision.target_price,
                "position_quantity": risk_decision.position_quantity,
                "requested_quantity": risk_decision.requested_quantity,
                "position_notional": risk_decision.position_notional,
                "risk_amount": risk_decision.risk_amount,
                "reward_risk_ratio": risk_decision.reward_risk_ratio,
                "fees_estimate": risk_decision.fees_estimate,
                "slippage_estimate": risk_decision.slippage_estimate,
                "leverage": risk_decision.leverage,
                "binding_constraint": binding,
                "metadata": dict(risk_decision.metadata),
            }

        return {
            "symbol": dataset.symbol,
            "timeframe": dataset.timeframe.value,
            "strategy_id": strategy_id,
            "strategy_name": strategy_name,
            "ticker_last": _safe_float(ticker.get("last")) if ticker else None,
            "ticker_bid": _safe_float(ticker.get("bid")) if ticker else None,
            "ticker_ask": _safe_float(ticker.get("ask")) if ticker else None,
            "ticker_timestamp_ms": (
                ticker.get("timestamp")
                if ticker and isinstance(ticker.get("timestamp"), int)
                else None
            ),
            "candles": [
                {
                    "timestamp": c.timestamp,
                    "open": c.open,
                    "high": c.high,
                    "low": c.low,
                    "close": c.close,
                    "volume": c.volume,
                    "is_closed": c.is_closed,
                }
                for c in dataset.candles
            ],
            "quality_issues": sorted(dataset.quality.issue_kinds),
            "is_analysis_safe": dataset.is_analysis_safe,
            "range": {
                "high": rh,
                "low": rl,
                "width": width,
                "status": range_state.status.value,
                "confidence": range_state.confidence,
                "is_tradable": range_state.is_tradable,
                "mode": range_state.mode,
                "metadata": dict(range_state.metadata),
            },
            "regime": {
                "value": regime.value,
                "lookback": regime_lookback,
                "threshold": regime_threshold,
                "efficiency_ratio": er,
            },
            "signal": {
                "direction": signal.direction.value,
                "reason": signal.reason.value,
                "price": (
                    signal.price if signal.price != 0.0 or last_price is not None else None
                ),
                "position_in_range": signal.position_in_range,
                "confidence": signal.confidence,
                "confirmation": signal.confirmation,
                "confirmation_policy": (
                    signal.metadata.get("confirmation_policy")
                    if isinstance(
                        signal.metadata.get("confirmation_policy"), str
                    )
                    else None
                ),
                "range_high": signal.range_high,
                "range_low": signal.range_low,
                "metadata": dict(signal.metadata),
            },
            "oscillator": {
                "value": osc_value,
                "type": osc_type,
                "overbought": osc_overbought,
                "oversold": osc_oversold,
                "is_confirmation": confirmation_bool,
            },
            "risk": risk_payload,
            "freshness": {
                "retrieved_at_ms": retrieved_at,
                "age_ms": age_ms,
                "is_stale": is_stale,
                "has_forming_candle": has_forming,
                "last_closed_timestamp_ms": last_closed_ts,
            },
        }
