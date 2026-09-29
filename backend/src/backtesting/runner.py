"""BacktestRunner: deterministic chronological replay through the LIVE engines.

ANTI-LOOK-AHEAD DESIGN (non-negotiable contract of this module):

1. The dataset is filtered to CLOSED candles once, up front (Phase 6
   semantics; forming candles never enter history).
2. At replay step ``i`` the strategy sees exactly ``frame.iloc[:i+1]`` —
   every engine input is a prefix slice of one prebuilt frame. Future rows
   physically cannot reach a detector, the signal engine or the risk engine.
3. Decisions use only data through candle ``i``'s close. Close-mode fills at
   the next open. Touch-mode tests those fixed boundaries against the next
   candle; ambiguous two-edge bars and gap entries are skipped. Stop-first
   resolution applies, and touch bars are never awarded an uncertain target.
4. Range/oscillator/regime values are recomputed per step from the visible
   prefix; nothing is carried backward from later bars.
5. A position occupies the replay until its exit bar; overlapping entries are
   impossible by construction (single-position simulation).
6. Legacy full-exit mode discards unfinished positions. Runner mode marks
   remaining quantity at the final close and records an end_of_data exit.
7. Runner trailing stops use prior closes only; ambiguous same-bar target
   and new runner-stop touches resolve conservatively at the runner stop.

Performance: one DataFrame is built up front; each step passes a prefix
slice. Detectors validate/copy internally as they always do.
"""

import hashlib
import json
import math
from collections.abc import Mapping

import pandas as pd

from backtesting.models import (
    ENGINE_VERSION,
    BacktestConfig,
    BacktestResult,
    EquityPoint,
    ZoneObservation,
)
from backtesting.regime import MarketRegime, classify_regime
from backtesting.simulation import resolve_protective_exit, simulate_entry_fill, wilder_atr
from exchange.models import PositionDirection
from market_data.models import CandleDataset, MarketCandle
from persistence.models import (
    StoredTrade,
    TradeContext,
    TradeResult,
    TradeStatus,
)
from persistence.statistics import compute_trade_statistics
from range_engine.base import RangeState, get_int
from risk_engine.base import AccountRiskState, RiskDecision, RiskDecisionStatus
from risk_engine.engine import RiskEngine
from signal_engine.base import SignalDirection
from signal_engine.engine import RangeSignalEngine
from signal_engine.structure import touch_signal

_ZONE_LOWER = "lower_edge"
_ZONE_MIDDLE = "middle"
_ZONE_UPPER = "upper_edge"
_ZONE_OUTSIDE = "outside"

_OHLCV_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


class BacktestRunner:
    """Replays closed-candle history through the existing strategy engines."""

    def replay(self, dataset: CandleDataset, config: BacktestConfig) -> BacktestResult:
        """Run one deterministic backtest over ``dataset`` per ``config``."""
        self._validate_inputs(dataset, config)
        window = tuple(
            candle
            for candle in dataset.candles
            if candle.is_closed and config.start_ms <= candle.timestamp < config.end_ms
        )
        full_frame = self._build_frame(window)
        run_id = self._run_id(config, window)

        equity = config.initial_capital
        peak = equity
        consecutive_losses = 0
        daily_start_equity = equity
        current_day: int | None = None
        equity_curve: list[EquityPoint] = []
        trades: list[StoredTrade] = []
        observations: list[ZoneObservation] = []
        regime_counts: dict[str, int] = {regime.value: 0 for regime in MarketRegime}
        zone_counts: dict[str, int] = {
            _ZONE_LOWER: 0,
            _ZONE_MIDDLE: 0,
            _ZONE_UPPER: 0,
            _ZONE_OUTSIDE: 0,
            "no_range": 0,
        }
        decisions = 0
        trade_seq = 0

        signal_engine = RangeSignalEngine(dict(config.signal_config))
        risk_engine = RiskEngine()
        duration_ms = config.resolved_timeframe.duration_ms

        index = max(0, config.warmup_candles - 1)
        while index < len(window) - 1:  # need one future bar for the entry fill
            history = full_frame.iloc[: index + 1]
            candle = window[index]
            decision_ts = candle.close_time_ms

            day = decision_ts // 86_400_000
            if current_day != day:
                current_day = day
                daily_start_equity = equity

            regime = classify_regime(
                [float(value) for value in history["close"]],
                lookback=config.regime_lookback,
                threshold=config.regime_threshold,
            )
            regime_counts[regime.value] += 1

            range_state = detect_range_state(history, dict(config.range_config))
            zone = self._zone_of(candle.close, range_state.range_low, range_state.range_high)
            if not range_state.is_tradable or zone is None:
                zone_counts["no_range"] += 1
                observations.append(
                    ZoneObservation(decision_ts, regime, range_state.status.value, None, False)
                )
                index += 1
                continue
            zone_counts[zone] += 1
            observations.append(
                ZoneObservation(decision_ts, regime, range_state.status.value, zone, True)
            )

            touch_mode = config.signal_config.get("entry_mode") == "touch"
            next_bar = window[index + 1]
            signal = (
                touch_signal(
                    {
                        "open": next_bar.open,
                        "high": next_bar.high,
                        "low": next_bar.low,
                        "close": next_bar.close,
                    },
                    range_state,
                    config.signal_config,
                )
                if touch_mode
                else signal_engine.evaluate(candle.close, range_state)
            )
            if signal.direction is SignalDirection.NONE:
                index += 1
                continue
            decisions += 1

            account = AccountRiskState(
                equity=equity,
                available_balance=equity,
                peak_equity=peak,
                daily_start_equity=daily_start_equity,
                consecutive_losses=consecutive_losses,
            )
            try:
                decision = risk_engine.evaluate(
                    signal,
                    account,
                    price=signal.price,
                    atr=self._atr_if_required(config, history),
                    symbol=config.symbol,
                    config=config.effective_risk_config,
                )
            except ValueError:
                # Structurally unusable inputs (e.g., 'atr' stop method without
                # computable ATR): treat as an evaluated non-trade this bar.
                decisions -= 1
                index += 1
                continue
            if not decision.approved or decision.status is not RiskDecisionStatus.APPROVED:
                index += 1
                continue

            direction = (
                PositionDirection.LONG
                if signal.direction is SignalDirection.LONG
                else PositionDirection.SHORT
            )
            outcome = self._simulate_position(
                window=window,
                entry_index=index + 1,
                direction=direction,
                quantity=self._decision_quantity(decision),
                stop_price=self._require(decision.stop_price, "stop"),
                target_price=self._require(decision.target_price, "target"),
                risk_amount=self._require(decision.risk_amount, "risk amount"),
                config=config,
                duration_ms=duration_ms,
                range_high=_finite_or_none(range_state.range_high),
                range_low=_finite_or_none(range_state.range_low),
                range_mode=str(range_state.mode),
                range_confidence=range_state.confidence,
                signal_reason=signal.reason.value,
                position_in_range=signal.position_in_range,
                confirmation=signal.confirmation,
                regime=regime,
                zone=zone,
                trade_seq=trade_seq,
                touch_entry=signal.price if touch_mode else None,
                run_id=run_id,
            )
            trade_seq += 1
            if outcome is None:
                break  # data ended mid-position; half-life discarded per rule 6
            trade, exit_index, net_pnl = outcome
            trades.append(trade)
            equity += net_pnl
            peak = max(peak, equity)
            consecutive_losses = consecutive_losses + 1 if net_pnl < 0.0 else 0
            exit_close_ts = window[exit_index].close_time_ms
            equity_curve.append(
                EquityPoint(
                    timestamp_ms=exit_close_ts,
                    equity=equity,
                    peak_equity=peak,
                    drawdown=peak - equity,
                )
            )
            index = exit_index + 1

        statistics = compute_trade_statistics(trades)
        return BacktestResult(
            run_id=self._run_id(config, window),
            config=config,
            config_hash=config.config_hash,
            engine_version=ENGINE_VERSION,
            symbol=config.symbol,
            timeframe=config.resolved_timeframe.value,
            period_start_ms=window[0].timestamp if window else config.start_ms,
            period_end_ms=(window[-1].timestamp + duration_ms if window else config.end_ms),
            candles_replayed=len(window),
            decisions_evaluated=decisions,
            initial_capital=config.initial_capital,
            final_equity=equity,
            peak_equity=peak,
            max_drawdown=max((point.drawdown for point in equity_curve), default=0.0),
            trades=tuple(trades),
            statistics=statistics,
            equity_curve=tuple(equity_curve),
            observations=tuple(observations),
            regime_counts=regime_counts,
            zone_counts=zone_counts,
        )

    # ----- internals -----

    @staticmethod
    def _validate_inputs(dataset: CandleDataset, config: BacktestConfig) -> None:
        if dataset.symbol != config.symbol:
            raise ValueError(
                f"dataset symbol {dataset.symbol!r} != config symbol {config.symbol!r}"
            )
        if dataset.timeframe is not config.resolved_timeframe:
            raise ValueError(
                f"dataset timeframe {dataset.timeframe.value} != config "
                f"timeframe {config.resolved_timeframe.value}"
            )

    @staticmethod
    def _build_frame(window: tuple[MarketCandle, ...]) -> pd.DataFrame:
        rows = [
            {
                "timestamp": candle.timestamp,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": 0.0 if candle.volume is None else candle.volume,
            }
            for candle in window
        ]
        return pd.DataFrame(rows, columns=_OHLCV_COLUMNS)

    @staticmethod
    def _zone_of(price: float, low: float, high: float) -> str | None:
        """Thirds-based zone label for RESEARCH ONLY; trading zones remain
        the Signal Engine's configured edge fractions."""
        if math.isnan(low) or math.isnan(high) or high <= low:
            return None
        width = high - low
        if price < low or price > high:
            return _ZONE_OUTSIDE
        position = (price - low) / width
        if position <= 1.0 / 3.0:
            return _ZONE_LOWER
        if position >= 2.0 / 3.0:
            return _ZONE_UPPER
        return _ZONE_MIDDLE

    @staticmethod
    def _atr_if_required(config: BacktestConfig, history: pd.DataFrame) -> float | None:
        """Wilder ATR strictly from visible candles when risk needs one."""
        if config.effective_risk_config.get("stop_method") != "atr":
            return None
        period = get_int(dict(config.effective_risk_config), "atr_period", 14, minimum=1)
        return wilder_atr(
            [float(value) for value in history["high"]],
            [float(value) for value in history["low"]],
            [float(value) for value in history["close"]],
            period,
        )

    @staticmethod
    def _decision_quantity(decision: RiskDecision) -> float:
        quantity = decision.position_quantity
        assert quantity is not None and quantity > 0.0, "approved decision carries quantity"
        return quantity

    @staticmethod
    def _require(value: float | None, name: str) -> float:
        assert value is not None and value > 0.0, f"approved decision carries {name}"
        return value

    def _simulate_position(
        self,
        *,
        window: tuple[MarketCandle, ...],
        entry_index: int,
        direction: PositionDirection,
        quantity: float,
        stop_price: float,
        target_price: float,
        risk_amount: float,
        config: BacktestConfig,
        duration_ms: int,
        range_high: float | None,
        range_low: float | None,
        range_mode: str,
        range_confidence: float,
        signal_reason: str,
        position_in_range: float | None,
        confirmation: bool | None,
        regime: MarketRegime,
        zone: str | None,
        trade_seq: int,
        touch_entry: float | None = None,
        run_id: str = "",
        staged_exit: dict | None = None,
    ) -> tuple[StoredTrade, int, float] | None:
        """Walk forward from the entry bar until stop/target/end-of-data."""
        entry_bar = window[entry_index]
        entry_open = touch_entry if touch_entry is not None else entry_bar.open
        entry_fill = simulate_entry_fill(direction, entry_open, slippage_rate=config.slippage_rate)
        fees_entry = entry_fill * quantity * config.fee_rate
        slip_entry_cost = abs(entry_fill - entry_open) * quantity
        opened_at = entry_bar.timestamp
        runner = float(config.risk_config.get("runner_fraction", 0.0))
        trail_percent = float(config.risk_config.get("runner_trail_percent", 0.02))
        if staged_exit:
            runner = 1 - staged_exit["tp1_fraction"]
        outside_closes = 0
        remaining = quantity
        exits: list[dict[str, object]] = []
        active_stop = stop_price
        took_partial = False

        for exit_index in range(entry_index, len(window)):
            bar = window[exit_index]
            outcome, exit_fill = resolve_protective_exit(
                direction,
                active_stop,
                (
                    staged_exit["tp2"]
                    if staged_exit
                    else float("inf")
                    if direction is PositionDirection.LONG
                    else 0.0
                )
                if took_partial
                else target_price,
                candle_open=entry_fill
                if touch_entry is not None and exit_index == entry_index
                else bar.open,
                candle_high=bar.high,
                candle_low=bar.low,
                slippage_rate=config.slippage_rate,
            )
            # The entry candle's far extreme may have occurred before the touch.
            # Count its stop, but never award a same-candle target for touch entries.
            if touch_entry is not None and exit_index == entry_index and outcome == "target":
                outcome = None
            if outcome == "target" and runner > 0 and not took_partial:
                partial_qty = quantity * (1 - runner)
                exits.append(
                    {
                        "price": exit_fill,
                        "quantity": partial_qty,
                        "timestamp": bar.close_time_ms,
                        "reason": "partial_target",
                    }
                )
                remaining -= partial_qty
                took_partial = True
                active_stop = (
                    entry_fill
                    if staged_exit
                    else (
                        max(entry_fill, target_price * (1 - trail_percent))
                        if direction is PositionDirection.LONG
                        else min(entry_fill, target_price * (1 + trail_percent))
                    )
                )
                # Conservative ordering when target and the new runner stop share a bar.
                outcome, exit_fill = resolve_protective_exit(
                    direction,
                    active_stop,
                    staged_exit["tp2"]
                    if staged_exit
                    else float("inf")
                    if direction is PositionDirection.LONG
                    else 0.0,
                    candle_open=target_price,
                    candle_high=bar.high,
                    candle_low=bar.low,
                    slippage_rate=config.slippage_rate,
                )
            if staged_exit:
                outside = (
                    bar.close < range_low - staged_exit["buffer"]
                    if direction is PositionDirection.LONG
                    else bar.close > range_high + staged_exit["buffer"]
                )
                outside_closes = outside_closes + 1 if outside else 0
                if outcome is None and outside_closes >= staged_exit["hold_closes"]:
                    outcome = "range_invalidated"
                    exit_fill = bar.close * (
                        1 - config.slippage_rate
                        if direction is PositionDirection.LONG
                        else 1 + config.slippage_rate
                    )
            if outcome is None and exit_index == len(window) - 1 and runner > 0:
                # Realize the residual position at the final close; do not discard its partial P&L.
                outcome = "end_of_data"
                exit_fill = bar.close * (
                    1 - config.slippage_rate
                    if direction is PositionDirection.LONG
                    else 1 + config.slippage_rate
                )
            if outcome is None:
                if took_partial and not staged_exit:
                    # Tighten only for the NEXT candle, avoiding intrabar hindsight.
                    active_stop = (
                        max(active_stop, bar.close * (1 - trail_percent))
                        if direction is PositionDirection.LONG
                        else min(active_stop, bar.close * (1 + trail_percent))
                    )
                continue
            exits.append(
                {
                    "price": exit_fill,
                    "quantity": remaining,
                    "timestamp": bar.close_time_ms,
                    "reason": ("breakeven_stop" if staged_exit else "runner_stop")
                    if took_partial and outcome == "stop"
                    else "tp2"
                    if staged_exit and took_partial and outcome == "target"
                    else outcome,
                }
            )
            exit_fill = sum(float(e["price"]) * float(e["quantity"]) for e in exits) / quantity
            fees_exit = exit_fill * quantity * config.fee_rate
            reference_level = stop_price if outcome == "stop" else target_price
            slip_exit_cost = abs(exit_fill - reference_level) * quantity
            if staged_exit:
                slip_exit_cost = sum(
                    float(e["price"])
                    * float(e["quantity"])
                    * config.slippage_rate
                    / (
                        1 - config.slippage_rate
                        if direction is PositionDirection.LONG
                        else 1 + config.slippage_rate
                    )
                    for e in exits
                )
            sign = 1.0 if direction is PositionDirection.LONG else -1.0
            gross_pnl = sign * (exit_fill - entry_fill) * quantity
            net_pnl = gross_pnl - fees_entry - fees_exit
            result = (
                TradeResult.WIN
                if net_pnl > 0.0
                else TradeResult.LOSS
                if net_pnl < 0.0
                else TradeResult.BREAKEVEN
            )
            closed_at = bar.close_time_ms
            context = TradeContext(
                range_mode=range_mode,
                range_high=range_high,
                range_low=range_low,
                range_width=(
                    abs(range_high - range_low)
                    if range_high is not None and range_low is not None
                    else None
                ),
                range_confidence=range_confidence,
                signal_direction=direction.value,
                signal_reason=signal_reason,
                position_in_range=position_in_range,
                confirmation=confirmation,
                stop_distance=abs(entry_fill - stop_price),
                target_distance=abs(target_price - entry_fill),
                risk_percent=None,
                timeframe=config.resolved_timeframe.value,
                strategy_config_version=f"{config.strategy_id}@{config.config_version}",
                extra={
                    "simulated": True,
                    "exit_fills": exits,
                    "run_id": run_id,
                    "entry_mode": "touch" if touch_entry is not None else "close",
                    "runner_fraction": 0.0 if staged_exit else runner,
                    "staged_exit": staged_exit,
                    "regime": regime.value,
                    "zone": zone,
                    "exit_reason": outcome,
                    "fees_entry": round(fees_entry, 12),
                    "fees_exit": round(fees_exit, 12),
                    "slippage_cost": round(slip_entry_cost + slip_exit_cost, 12),
                },
            )
            trade_id = f"bt-{run_id[:16] or config.config_hash[:12]}-{trade_seq:06d}-{outcome}"
            trade = StoredTrade(
                trade_id=trade_id,
                symbol=config.symbol,
                direction=direction,
                quantity=quantity,
                entry_price=round(entry_fill, 12),
                opened_at_ms=opened_at,
                status=TradeStatus.CLOSED,
                execution_ref=None,
                timeframe=config.resolved_timeframe.value,
                exit_price=round(exit_fill, 12),
                closed_at_ms=closed_at,
                realized_pnl=round(net_pnl, 10),
                fees=round(fees_entry + fees_exit, 12),
                slippage=round(slip_entry_cost + slip_exit_cost, 12),
                risk_amount=risk_amount,
                result=result,
                strategy_id=config.strategy_id,
                config_hash=config.config_hash,
                context=context,
                created_at_ms=closed_at,
                updated_at_ms=closed_at,
            )
            return trade, exit_index, net_pnl
        return None

    @staticmethod
    def _run_id(config: BacktestConfig, window: tuple[MarketCandle, ...]) -> str:
        first_ts = getattr(window[0], "timestamp", config.start_ms) if window else config.start_ms
        fingerprint = "|".join(
            [
                config.config_hash,
                config.symbol,
                config.resolved_timeframe.value,
                str(first_ts),
                str(len(window)),
                hashlib.sha256(
                    json.dumps(
                        [(c.timestamp, c.open, c.high, c.low, c.close, c.volume) for c in window],
                        separators=(",", ":"),
                    ).encode()
                ).hexdigest(),
                ENGINE_VERSION,
            ]
        )
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:32]


def detect_range_state(history: pd.DataFrame, range_config: Mapping[str, object]) -> RangeState:
    """Thin indirection so the replay depends only on the public factory."""
    from range_engine.factory import RangeEngineFactory

    return RangeEngineFactory.detect(history, dict(range_config))


def _finite_or_none(value: float) -> float | None:
    return None if math.isnan(value) else value
