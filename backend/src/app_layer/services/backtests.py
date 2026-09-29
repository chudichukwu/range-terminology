"""Backtest use case: strategy config + window -> deterministic run.

Pure orchestration: builds a :class:`BacktestConfig` from a stored user
strategy, feeds persisted candles through the Phase 8 ``BacktestRunner``,
persists the run record (with owner) and returns the result. No backtesting
mathematics live here.
"""

import json
import time
import uuid
from collections.abc import Callable

from app_layer.errors import NotFoundError, ValidationError
from app_layer.models import StrategyConfig, User
from app_layer.ports import BacktestServiceStore
from app_layer.services.providers import public_source
from backtesting.models import BacktestConfig, BacktestResult
from backtesting.runner import BacktestRunner
from market_data.models import CandleDataset, HistoricalRequest, Timeframe
from persistence.errors import PersistenceError, PersistenceErrorCode
from persistence.models import BacktestRunRecord
from persistence.statistics import compute_trade_statistics


def closed_history_end(end_ms: int, frame: Timeframe) -> int:
    """Only candles whose entire interval closed by replay end; weekly grid is Monday UTC."""
    offset = 345600000 if frame is Timeframe.W1 else 0
    return ((end_ms - offset) // frame.duration_ms) * frame.duration_ms + offset


def _default_clock() -> int:
    return time.time_ns() // 1_000_000


def _new_id() -> str:
    return uuid.uuid4().hex


def _int_or(value: object, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value


class BacktestService:
    def __init__(
        self,
        runner: BacktestRunner | None = None,
        *,
        candle_repository: BacktestServiceStore,
        run_repository: BacktestServiceStore,
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        self._runner = runner if runner is not None else BacktestRunner()
        self._candles = candle_repository
        self._runs = run_repository
        self._clock_ms = clock_ms if clock_ms is not None else _default_clock

    def _load_window(
        self, symbol: str, timeframe: str, start_ms: int, end_ms: int
    ) -> CandleDataset:
        dataset = self._candles.query_candles(symbol, timeframe, start_ms=start_ms, end_ms=end_ms)
        return dataset

    def run_for_strategy(
        self,
        actor: User,
        strategy: StrategyConfig,
        *,
        start_ms: int,
        end_ms: int,
        initial_capital: float,
        fee_rate: float | None = None,
        slippage_rate: float | None = None,
        symbol: str | None = None,
        timeframe: str | None = None,
        venue: str | None = None,
    ) -> tuple[BacktestResult, BacktestRunRecord]:
        payload = strategy.payload()
        range_config = payload.get("range_config")
        signal_config = payload.get("signal_config")
        risk_config = payload.get("risk_config")
        assert isinstance(range_config, dict)
        assert isinstance(signal_config, dict)
        assert isinstance(risk_config, dict)

        for name in ("start_ms", "end_ms"):
            value = locals()[name]
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValidationError(f"{name} must be a positive integer ms value")
        if start_ms >= end_ms:
            raise ValidationError("start_ms must precede end_ms")
        if initial_capital <= 0.0:
            raise ValidationError("initial_capital must be positive")

        effective_fee = float(fee_rate) if fee_rate is not None else 0.0005
        effective_slippage = float(slippage_rate) if slippage_rate is not None else 0.0002

        timeframe_value = timeframe or str(payload.get("timeframe") or "1h")
        try:
            resolved = Timeframe.parse(timeframe_value)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        config = BacktestConfig(
            symbol=symbol or str(payload.get("symbol") or "BTC/USDT"),
            timeframe=resolved,
            start_ms=start_ms,
            end_ms=end_ms,
            initial_capital=float(initial_capital),
            range_config=range_config,
            signal_config=signal_config,
            risk_config={**risk_config, **({"data_source": venue} if venue else {})},
            strategy_id=strategy.id,
            config_version=f"cfg-{strategy.schema_version}",
            warmup_candles=max(2, _int_or(payload.get("warmup_candles"), 30)),
            fee_rate=effective_fee,
            slippage_rate=effective_slippage,
        )

        balanced = range_config.get("mode") == "balanced"
        if balanced:
            from backtesting.balanced import replay_balanced
            from range_engine.balanced import CONTEXT_TIMEFRAMES, ENTRY_TIMEFRAMES, settings

            cfg = settings(payload)
            if resolved.value not in ENTRY_TIMEFRAMES:
                raise ValidationError(
                    "Choose 1m, 5m or 15m for entry replay. Higher timeframes load automatically."
                )
            datasets = {}
            for tf in (*CONTEXT_TIMEFRAMES, resolved.value):
                frame = Timeframe.parse(tf)
                warmup = 60 if tf in ("1w", "1d") else int(cfg["lookback"]) + 60
                begin = max(1, start_ms - warmup * frame.duration_ms)
                closed_end = closed_history_end(end_ms, frame)
                if (end_ms - begin) // frame.duration_ms + 1 > 5000:
                    raise ValidationError(
                        "Choose a shorter period: 5,000 candles including warm-up per timeframe"
                    )
                if venue:
                    source = public_source(venue)
                    with source.lock:
                        ds = source.service.get_historical(
                            HistoricalRequest(
                                config.symbol, frame, start_ms=begin, end_ms=closed_end, limit=5000
                            )
                        )
                else:
                    ds = self._load_window(config.symbol, tf, begin, closed_end)
                if (
                    not ds.is_analysis_safe
                    or len([b for b in ds.closed_candles if b.close_time_ms <= start_ms]) < 55
                ):
                    raise ValidationError(
                        f"Incomplete {tf} context history. Choose a newer market/window or another source."
                    )
                datasets[tf] = ds
            result = replay_balanced(datasets, config)
        elif venue:
            count = (end_ms - start_ms) // resolved.duration_ms + 1
            if count > 5000:
                raise ValidationError("Choose a shorter period: at most 5,000 candles per run")
            source = public_source(venue)
            with source.lock:
                dataset = source.service.get_historical(
                    HistoricalRequest(
                        config.symbol, resolved, start_ms=start_ms, end_ms=end_ms, limit=5000
                    )
                )
            if not dataset.is_analysis_safe:
                raise ValidationError(
                    "The source did not return complete closed history for this period. "
                    "Choose a shorter or more recent window."
                )
        else:
            dataset = self._load_window(config.symbol, resolved.value, start_ms, end_ms)
        if not balanced and len(dataset.candles) <= config.warmup_candles:
            raise ValidationError(
                "Not enough historical candles after warm-up to run this backtest"
            )
        if not balanced:
            result = self._runner.replay(dataset, config)
        stats = compute_trade_statistics(result.trades)
        record = BacktestRunRecord(
            run_id=result.run_id,
            config_hash=result.config_hash,
            symbol=result.symbol,
            timeframe=result.timeframe,
            period_start_ms=result.period_start_ms,
            period_end_ms=result.period_end_ms,
            initial_capital=result.initial_capital,
            final_equity=result.final_equity,
            peak_equity=result.peak_equity,
            max_drawdown=result.max_drawdown,
            total_trades=len(result.trades),
            stats_json=json.dumps(
                {
                    "win_rate": stats.win_rate,
                    "average_r": stats.average_r,
                    "profit_factor": stats.profit_factor,
                    "expectancy": stats.expectancy,
                    "total_realized_pnl": stats.total_realized_pnl,
                    "max_drawdown": stats.max_drawdown,
                },
                sort_keys=True,
            ),
            config_json=config.to_json(),
            engine_version=result.engine_version,
            created_at_ms=self._clock_ms(),
            owner_user_id=actor.id,
        )
        try:
            self._runs.save_run(record)
        except PersistenceError as exc:
            if exc.code is not PersistenceErrorCode.INTEGRITY_ERROR:
                raise
            # Identical replay of the same data+config: deterministic runs
            # produce the same run_id; keep the original persisted record.
            existing = self._runs.get_run(record.run_id)
            assert existing is not None
            record = existing

        # Persist simulated trades as research facts (flagged ``simulated``
        # in their context). Re-runs stay idempotent: identical inputs
        # reproduce identical trade ids, which are skipped on conflict.
        for trade in result.trades:
            try:
                self._runs.record_trade(trade)
            except PersistenceError as exc:
                if exc.code is not PersistenceErrorCode.INTEGRITY_ERROR:
                    raise
        return result, record

    def get_run(self, actor: User, run_id: str) -> BacktestRunRecord:
        found = self._runs.get_run(run_id)
        if found is None or (found.owner_user_id != actor.id and actor.role.value != "owner"):
            raise NotFoundError("backtest run not found")
        return found

    def list_runs(self, actor: User) -> tuple[BacktestRunRecord, ...]:
        if actor.role.value == "owner":
            return self._runs.list_runs()
        return self._runs.list_runs(owner_user_id=actor.id)
