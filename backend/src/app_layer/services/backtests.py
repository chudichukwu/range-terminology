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
from backtesting.models import BacktestConfig, BacktestResult
from backtesting.runner import BacktestRunner
from market_data.models import CandleDataset, Timeframe
from persistence.errors import PersistenceError, PersistenceErrorCode
from persistence.models import BacktestRunRecord
from persistence.statistics import compute_trade_statistics


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
        dataset = self._candles.query_candles(
            symbol, timeframe, start_ms=start_ms, end_ms=end_ms
        )
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
        effective_slippage = (
            float(slippage_rate) if slippage_rate is not None else 0.0002
        )

        timeframe_value = str(payload.get("timeframe") or "1h")
        resolved = Timeframe.parse(timeframe_value)

        config = BacktestConfig(
            symbol=str(payload.get("symbol") or "BTC/USDT"),
            timeframe=resolved,
            start_ms=start_ms,
            end_ms=end_ms,
            initial_capital=float(initial_capital),
            range_config=range_config,
            signal_config=signal_config,
            risk_config=risk_config,
            strategy_id=strategy.name,
            config_version=f"cfg-{strategy.schema_version}",
            warmup_candles=max(2, _int_or(payload.get("warmup_candles"), 30)),
            fee_rate=effective_fee,
            slippage_rate=effective_slippage,
        )

        dataset = self._load_window(
            config.symbol, resolved.value, start_ms, end_ms
        )
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
            stats_json=json.dumps({
                "win_rate": stats.win_rate,
                "average_r": stats.average_r,
                "profit_factor": stats.profit_factor,
                "expectancy": stats.expectancy,
                "total_realized_pnl": stats.total_realized_pnl,
                "max_drawdown": stats.max_drawdown,
            }, sort_keys=True),
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
        if found is None or (
            found.owner_user_id != actor.id and actor.role.value != "owner"
        ):
            raise NotFoundError("backtest run not found")
        return found

    def list_runs(self, actor: User) -> tuple[BacktestRunRecord, ...]:
        if actor.role.value == "owner":
            return self._runs.list_runs()
        return self._runs.list_runs(owner_user_id=actor.id)
