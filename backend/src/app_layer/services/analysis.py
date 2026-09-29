"""Pair analysis service — orchestrates existing domain engines, no new domain logic.

Exposes RangeState + MarketRegime + Signal + (optional) RiskDecision + oscillator
metadata for a symbol/timeframe via the already-tested engines. The frontend
calls this for dashboard rendering; it never re-derives these values.
"""

from __future__ import annotations

import math
import time
from dataclasses import replace
from typing import Any

import pandas as pd

from app_layer.errors import ValidationError
from app_layer.services.markets import MarketDataFacade
from app_layer.services.playbook import range_touch_preset
from app_layer.services.strategies import StrategyConfigService
from backtesting.regime import MarketRegime, classify_regime, efficiency_ratio
from market_data.models import CandleDataset
from market_data.validation import validate_sequence
from range_engine.base import RangeState
from range_engine.factory import RangeEngineFactory
from risk_engine.base import AccountRiskState, RiskDecision
from risk_engine.engine import RiskEngine
from signal_engine.base import Signal
from signal_engine.engine import RangeSignalEngine
from signal_engine.structure import swing_failures, touch_signal

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
        payload = (
            self._strategies.get(actor, strategy_id).payload()
            if strategy_id
            else range_touch_preset()
        )
        if payload.get("range_config", {}).get("mode") == "balanced":
            from app_layer.services.balanced_analysis import analyze_balanced

            name = (
                self._strategies.get(actor, strategy_id).name
                if strategy_id
                else "Confirmed range · starting settings"
            )
            return analyze_balanced(
                self._markets, actor, symbol, timeframe, payload, strategy_id, name, limit, now_ms
            )
        # --- fetch market data (delegates validation to facade) ---
        dataset: CandleDataset = self._markets.candles(
            symbol, timeframe, limit=limit, include_current=True
        )
        ticker: dict[str, Any] | None = None
        try:
            ticker = self._markets.ticker(symbol)
        except Exception:
            ticker = None  # ticker is best-effort; analysis proceeds

        # --- resolve strategy configs (if provided) ---
        preset = range_touch_preset()
        range_config = preset["range_config"]
        signal_config = preset["signal_config"]
        risk_config = preset["risk_config"]
        strategy_name: str | None = "Range touch · starting settings"
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
                if signal_config.get("entry_mode") == "touch" and dataset.candles:
                    current = dataset.candles[-1]
                    # A completed last candle must not contribute to its own levels.
                    before = df if not current.is_closed else df.iloc[:-1]
                    range_state = RangeEngineFactory.detect(before, range_config or None)
                    signal = touch_signal(
                        {
                            "open": current.open,
                            "high": current.high,
                            "low": current.low,
                            "close": current.close,
                        },
                        range_state,
                        signal_config,
                    )
                else:
                    signal = engine.evaluate(
                        price_for_signal, range_state, config=signal_config or None
                    )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        closed_quality = validate_sequence(
            dataset.symbol, dataset.timeframe, dataset.closed_candles
        ).report
        quality_issues = set(closed_quality.issue_kinds) | (
            set(dataset.quality.issue_kinds) - {"unclosed_candle_present"}
        )
        if quality_issues:
            from signal_engine.base import SignalDirection, SignalReason

            signal = replace(
                signal,
                direction=SignalDirection.NONE,
                reason=SignalReason.NON_TRADABLE_RANGE,
                confidence=0.0,
                metadata={**signal.metadata, "blocked_by": "data_quality"},
            )

        # Oscillator metadata (from range_state metadata when oscillator_confirmed)
        osc_value = _safe_float(range_state.metadata.get("oscillator_value"))
        osc_raw = range_state.metadata.get("oscillator")
        osc_type = osc_raw if isinstance(osc_raw, str) else None
        osc_overbought = _safe_float(range_state.metadata.get("overbought_threshold"))
        osc_oversold = _safe_float(range_state.metadata.get("oversold_threshold"))
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
                risk_decision = risk_engine.evaluate(signal, account, price=signal.price)
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

        if (
            last_closed_ts is None
            or now > last_closed_ts + 2 * dataset.timeframe.duration_ms + _STALE_THRESHOLD_MS
        ):
            is_stale = True
        if is_stale:
            from signal_engine.base import SignalDirection, SignalReason

            signal = replace(
                signal,
                direction=SignalDirection.NONE,
                reason=SignalReason.NON_TRADABLE_RANGE,
                confidence=0.0,
                metadata={**signal.metadata, "blocked_by": "stale_history"},
            )
            risk_decision = None
        elif signal.is_actionable and signal_config.get("entry_mode") == "touch":
            # A touch that has already breached its invalidation is no longer actionable.
            stop = (
                None
                if risk_decision is None
                else (risk_decision.stop_price or risk_decision.metadata.get("stop_price"))
            )
            current = dataset.candles[-1]
            if isinstance(stop, (int, float)) and (
                (signal.direction.value == "long" and current.low <= stop)
                or (signal.direction.value == "short" and current.high >= stop)
            ):
                from signal_engine.base import SignalDirection, SignalReason

                signal = replace(
                    signal,
                    direction=SignalDirection.NONE,
                    reason=SignalReason.NON_TRADABLE_RANGE,
                    confidence=0.0,
                    metadata={**signal.metadata, "blocked_by": "invalidation_breached"},
                )
                risk_decision = None

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
            "swing_failures": swing_failures(df),
            "symbol": dataset.symbol,
            "timeframe": dataset.timeframe.value,
            "strategy_id": strategy_id,
            "strategy_name": strategy_name,
            "ticker_last": _safe_float(ticker.get("last")) if ticker else None,
            "ticker_bid": _safe_float(ticker.get("bid")) if ticker else None,
            "ticker_ask": _safe_float(ticker.get("ask")) if ticker else None,
            "ticker_timestamp_ms": (
                ticker.get("timestamp_ms")
                if ticker and isinstance(ticker.get("timestamp_ms"), int)
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
            "quality_issues": sorted(quality_issues),
            "is_analysis_safe": not quality_issues,
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
                "price": (signal.price if signal.price != 0.0 or last_price is not None else None),
                "position_in_range": signal.position_in_range,
                "confidence": signal.confidence,
                "confirmation": signal.confirmation,
                "confirmation_policy": (
                    signal.metadata.get("confirmation_policy")
                    if isinstance(signal.metadata.get("confirmation_policy"), str)
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
