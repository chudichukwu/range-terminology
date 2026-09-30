"""Multi-timeframe replay: as-of joins only, confirmed entry then next-open fill."""

import hashlib
import json
from collections import Counter
from dataclasses import replace

from backtesting.models import ENGINE_VERSION, BacktestResult, EquityPoint
from backtesting.regime import MarketRegime
from backtesting.runner import BacktestRunner
from exchange.models import PositionDirection
from persistence.statistics import compute_trade_statistics
from range_engine.balanced import (
    CONTEXT_TIMEFRAMES,
    ENTRY_TIMEFRAMES,
    Timeline,
    evaluate_entry,
    settings,
    trade_plan,
)


def replay_balanced(datasets, config):
    cfg = settings(
        dict(
            range_config=config.range_config,
            signal_config=config.signal_config,
            risk_config=config.risk_config,
        )
    )
    tf = config.resolved_timeframe.value
    if tf not in ENTRY_TIMEFRAMES:
        raise ValueError(
            "Confirmed range replay needs 1m, 5m or 15m entry candles; "
            "1H/4H and daily/weekly are loaded automatically"
        )
    timelines = {key: Timeline(ds.closed_candles, cfg) for key, ds in datasets.items()}
    if any(key not in timelines for key in CONTEXT_TIMEFRAMES):
        raise ValueError("Weekly, daily, 4H and 1H histories are required")
    bars = timelines[tf].bars
    digest = hashlib.sha256(
        json.dumps(
            {
                key: [(b.timestamp, b.open, b.high, b.low, b.close, b.volume) for b in tl.bars]
                for key, tl in sorted(timelines.items())
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    run_id = hashlib.sha256((config.config_hash + digest).encode()).hexdigest()[:32]
    equity = peak = config.initial_capital
    trades, curve = [], [EquityPoint(config.start_ms, equity, peak, 0.0)]
    counts = Counter()
    i = 20
    while i < len(bars) - 1:
        bar = bars[i]
        if bar.close_time_ms < config.start_ms:
            i += 1
            continue
        if bars[i + 1].timestamp >= config.end_ms:
            break
        signal = evaluate_entry(bars[: i + 1], timelines, cfg)
        counts[signal["state"]] += 1
        if signal["direction"] == "none":
            i += 1
            continue
        direction = (
            PositionDirection.LONG if signal["direction"] == "long" else PositionDirection.SHORT
        )
        sign = 1 if direction is PositionDirection.LONG else -1
        entry = bars[i + 1].open * (1 + sign * config.slippage_rate)
        plan = trade_plan(signal, cfg, equity, config.fee_rate, config.slippage_rate, entry)
        if not plan["approved"]:
            i += 1
            continue
        snap = signal["snapshot"]
        # Shared fill resolver: stop-first ordering and partial accounting.
        out = BacktestRunner()._simulate_position(
            window=tuple(b for b in bars if b.timestamp < config.end_ms),
            entry_index=i + 1,
            direction=direction,
            quantity=plan["position_quantity"],
            stop_price=signal["stop"],
            target_price=signal["tp1"],
            risk_amount=plan["risk_amount"],
            config=config,
            duration_ms=config.resolved_timeframe.duration_ms,
            range_high=snap.high,
            range_low=snap.low,
            range_mode="balanced",
            range_confidence=min(1.0, min(snap.low_touches, snap.high_touches) / 3),
            signal_reason=signal["reason"],
            position_in_range=(signal["entry"] - snap.low) / (snap.high - snap.low),
            confirmation=True,
            regime=MarketRegime.RANGING,
            zone="lower_edge" if sign == 1 else "upper_edge",
            trade_seq=len(trades) + 1,
            run_id=run_id,
            staged_exit=dict(
                tp1_fraction=cfg["tp1_fraction"],
                runner_fraction=cfg["runner_fraction"],
                runner_trail_percent=cfg["runner_trail_percent"],
                tp2=signal["tp2"],
                buffer=snap.atr * cfg["breakout_buffer_atr"],
                hold_closes=cfg["hold_closes"],
            ),
        )
        if not out:
            break
        trade, exit_index, pnl = out
        trade = replace(
            trade,
            context=replace(
                trade.context,
                extra={
                    **trade.context.extra,
                    "entry_mode": "confirmed",
                    "range_timeframe": signal["range_timeframe"],
                    "confirmation_timestamp": bar.timestamp,
                    "context_asof": {k: v.time for k, v in signal["contexts"].items()},
                },
            ),
        )
        trades.append(trade)
        equity += pnl
        peak = max(peak, equity)
        curve.append(EquityPoint(trade.closed_at_ms, equity, peak, peak - equity))
        i = exit_index + 1
        if equity <= 0:
            break
    stats = compute_trade_statistics(trades)
    return BacktestResult(
        run_id=run_id,
        config=config,
        config_hash=config.config_hash,
        engine_version=ENGINE_VERSION,
        symbol=config.symbol,
        timeframe=tf,
        period_start_ms=config.start_ms,
        period_end_ms=config.end_ms,
        candles_replayed=sum(config.start_ms <= b.timestamp < config.end_ms for b in bars),
        decisions_evaluated=sum(counts.values()),
        initial_capital=config.initial_capital,
        final_equity=equity,
        peak_equity=peak,
        max_drawdown=max(p.drawdown for p in curve),
        trades=tuple(trades),
        statistics=stats,
        equity_curve=tuple(curve),
        observations=(),
        regime_counts=dict(counts),
        zone_counts={},
    )
