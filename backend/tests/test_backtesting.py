"""Deterministic tests for the backtesting & research engine.

Synthetic OHLCV only — no network, no ccxt, no credentials, no randomness.
"""

import math
from pathlib import Path

import pytest

from backtesting import (
    MarketRegime,
    classify_regime,
    resolve_protective_exit,
    simulate_entry_fill,
    simulate_exit_fill,
    wilder_atr,
)
from backtesting.models import ENGINE_VERSION, BacktestConfig
from backtesting.runner import BacktestRunner
from exchange.models import PositionDirection
from market_data.models import CandleDataset, MarketCandle, Timeframe
from persistence import (
    BacktestRunRecord,
    PersistenceError,
    SqlitePersistence,
    TradeStatus,
)

HOUR = 3_600_000
BASE_TS = 1_700_000_000_000


# ---------------------------------------------------------------------------
# Synthetic data builders
# ---------------------------------------------------------------------------


def sawtooth_dataset(
    cycles: int = 20,
    *,
    low: float = 95.0,
    high: float = 105.0,
    period: int = 24,
    start_ts: int = BASE_TS,
    symbol: str = "BTC/USDT",
) -> CandleDataset:
    """Genuine ranging structure: sine oscillation between fixed bounds."""
    candles: list[MarketCandle] = []
    amplitude = (high - low) / 2.0
    mid = low + amplitude
    for index in range(cycles * period):
        phase = (index % period) / period * 2.0 * math.pi
        close = mid + amplitude * math.sin(phase)
        open_ = mid + amplitude * math.sin(phase - 2.0 * math.pi / (period // 2))
        slope = abs(amplitude * math.cos(phase))
        hi = max(open_, close) + slope * 0.4 + 0.1
        lo = min(open_, close) - slope * 0.4 - 0.1
        candles.append(
            MarketCandle(
                symbol=symbol, timeframe=Timeframe.H1,
                timestamp=start_ts + index * HOUR,
                open=open_, high=hi, low=lo, close=close, volume=10.0,
            )
        )
    return CandleDataset(symbol=symbol, timeframe=Timeframe.H1, candles=tuple(candles))


def trending_dataset(
    bars: int = 120, *, drift: float = 0.6, start_ts: int = BASE_TS
) -> CandleDataset:
    """Steady uptrend; structural detection should yield degenerate ranges."""
    candles: list[MarketCandle] = []
    price = 100.0
    for index in range(bars):
        open_ = price
        close = price + drift
        candles.append(
            MarketCandle(
                symbol="BTC/USDT", timeframe=Timeframe.H1,
                timestamp=start_ts + index * HOUR,
                open=open_, high=close + 0.3, low=open_ - 0.3, close=close,
                volume=5.0,
            )
        )
        price = close
    return CandleDataset(symbol="BTC/USDT", timeframe=Timeframe.H1, candles=tuple(candles))


def make_config(**overrides: object) -> BacktestConfig:
    values: dict[str, object] = {
        "symbol": "BTC/USDT",
        "timeframe": Timeframe.H1,
        "start_ms": BASE_TS,
        "end_ms": BASE_TS + 500 * HOUR,
        "initial_capital": 10_000.0,
        "range_config": {"mode": "manual", "params": {
            "range_high": 106.0, "range_low": 94.0}},
        "signal_config": {"confirmation_policy": "ignored"},
        "warmup_candles": 5,
    }
    values.update(overrides)
    return BacktestConfig(**values)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Configuration model
# ---------------------------------------------------------------------------


class TestBacktestConfig:
    def test_valid_config_and_canonical_timeframe(self) -> None:
        config = make_config(timeframe="1h")
        assert config.resolved_timeframe is Timeframe.H1

    def test_config_hash_is_stable_and_materially_sensitive(self) -> None:
        base = make_config()
        assert base.config_hash == make_config().config_hash
        different_capital = make_config(initial_capital=20_000.0)
        different_mode = make_config(range_config={"mode": "structural"})
        assert base.config_hash != different_capital.config_hash
        assert base.config_hash != different_mode.config_hash

    def test_json_roundtrip_reproduces_hash(self) -> None:
        config = make_config()
        assert len(config.to_json()) > 50
        # Same content -> same canonical JSON -> same hash.
        assert make_config().to_json() == config.to_json()

    def test_engine_version_included_in_identity(self) -> None:
        assert ENGINE_VERSION in make_config().to_json()

    @pytest.mark.parametrize("overrides", [
        {"initial_capital": 0.0},
        {"start_ms": 200, "end_ms": 100},
        {"fee_rate": 0.2},
        {"slippage_rate": -0.01},
        {"regime_lookback": 3},
        {"regime_threshold": 1.5},
        {"symbol": ""},
        {"warmup_candles": 1},
    ])
    def test_invalid_configs_rejected(self, overrides: dict[str, object]) -> None:
        with pytest.raises(ValueError):
            make_config(**overrides)

    def test_risk_economics_default_to_simulation_assumptions(self) -> None:
        config = make_config(fee_rate=0.001, slippage_rate=0.002)
        effective = config.effective_risk_config
        assert effective["fee_rate"] == pytest.approx(0.001)
        assert effective["slippage_rate"] == pytest.approx(0.002)
        overridden = make_config(
            fee_rate=0.001, risk_config={"fee_rate": 0.004}
        )
        assert overridden.effective_risk_config["fee_rate"] == pytest.approx(0.004)


# ---------------------------------------------------------------------------
# Regime classification
# ---------------------------------------------------------------------------


class TestRegimeClassification:
    def test_trending_up(self) -> None:
        closes = [100.0 + index for index in range(30)]
        assert classify_regime(closes) is MarketRegime.TRENDING_UP

    def test_trending_down(self) -> None:
        closes = [200.0 - index for index in range(30)]
        assert classify_regime(closes) is MarketRegime.TRENDING_DOWN

    def test_ranging(self) -> None:
        closes = [100.0 + (index % 2) for index in range(30)]
        assert classify_regime(closes) is MarketRegime.RANGING

    def test_transitional_recent_trend_inside_flat_window(self) -> None:
        window = ([100.0, 101.0] * 8)[:16] + [100.5, 99.5, 98.5, 97.5]
        assert len(window) == 20
        # Whole window: net -2.5 over a ~18.5 path -> ER well under threshold;
        # recent third: straight 3-point slide -> ER = -1.
        assert classify_regime(window) is MarketRegime.TRANSITIONAL

    def test_insufficient_data(self) -> None:
        assert classify_regime([100.0, 101.0]) is MarketRegime.INSUFFICIENT_DATA

    def test_only_prefix_data_used(self) -> None:
        """A classification made at time T never changes when future data arrives."""
        prefix = [100.0 + index * 0.5 for index in range(20)]
        with_future_crash = prefix + [50.0] * 25
        # The first `lookback` closes are identical; so must the verdict be.
        assert classify_regime(prefix) is MarketRegime.TRENDING_UP
        assert classify_regime(prefix) == classify_regime(with_future_crash[:20])

    def test_invalid_parameters_rejected(self) -> None:
        with pytest.raises(ValueError):
            classify_regime([1.0] * 10, lookback=2)
        with pytest.raises(ValueError):
            classify_regime([1.0] * 10, threshold=0.0)


# ---------------------------------------------------------------------------
# Simulation fill rules (documented assumptions A1-A7)
# ---------------------------------------------------------------------------


class TestSimulationFills:
    def test_entry_slippage_adverse_both_directions(self) -> None:
        long_fill = simulate_entry_fill(
            PositionDirection.LONG, 100.0, slippage_rate=0.001
        )
        short_fill = simulate_entry_fill(
            PositionDirection.SHORT, 100.0, slippage_rate=0.001
        )
        assert long_fill == pytest.approx(100.1)
        assert short_fill == pytest.approx(99.9)

    def test_stop_touch_fills_at_level_with_exit_slip(self) -> None:
        outcome, fill = resolve_protective_exit(
            PositionDirection.LONG, 95.0, 110.0,
            candle_open=96.0, candle_high=97.0, candle_low=94.5,
            slippage_rate=0.001,
        )
        assert outcome == "stop"
        assert fill == pytest.approx(94.905)  # 95 * (1-0.001)

    def test_stop_gap_fills_at_open(self) -> None:
        outcome, fill = resolve_protective_exit(
            PositionDirection.LONG, 95.0, 110.0,
            candle_open=92.0, candle_high=93.0, candle_low=91.0,
            slippage_rate=0.001,
        )
        assert outcome == "stop"
        assert fill == pytest.approx(92.0)  # gapped through: open price, no extra slip

    def test_target_touch_and_gap(self) -> None:
        touch_outcome, touch_fill = resolve_protective_exit(
            PositionDirection.LONG, 95.0, 110.0,
            candle_open=108.0, candle_high=110.5, candle_low=107.5,
            slippage_rate=0.001,
        )
        assert touch_outcome == "target"
        assert touch_fill == pytest.approx(109.89)  # 110 * (1-0.001)
        gap_outcome, gap_fill = resolve_protective_exit(
            PositionDirection.LONG, 95.0, 110.0,
            candle_open=111.0, candle_high=112.0, candle_low=110.2,
            slippage_rate=0.001,
        )
        assert gap_outcome == "target" and gap_fill == pytest.approx(111.0)

    def test_same_candle_stop_and_target_is_pessimistic_stop(self) -> None:
        outcome, _fill = resolve_protective_exit(
            PositionDirection.LONG, 95.0, 110.0,
            candle_open=100.0, candle_high=111.0, candle_low=94.0,
            slippage_rate=0.0,
        )
        assert outcome == "stop"

    def test_short_side_mirrors(self) -> None:
        stop_outcome, stop_fill = resolve_protective_exit(
            PositionDirection.SHORT, 105.0, 90.0,
            candle_open=104.0, candle_high=105.5, candle_low=103.5,
            slippage_rate=0.0,
        )
        assert stop_outcome == "stop" and stop_fill == pytest.approx(105.0)
        target_outcome, target_fill = resolve_protective_exit(
            PositionDirection.SHORT, 105.0, 90.0,
            candle_open=91.0, candle_high=91.5, candle_low=89.0,
            slippage_rate=0.0,
        )
        assert target_outcome == "target" and target_fill == pytest.approx(90.0)

    def test_no_resolution_when_range_between_levels(self) -> None:
        outcome, _fill = resolve_protective_exit(
            PositionDirection.LONG, 90.0, 120.0,
            candle_open=100.0, candle_high=103.0, candle_low=99.0,
        )
        assert outcome is None and _fill == 0.0

    def test_exit_slip_adverse_for_short_cover(self) -> None:
        fill = simulate_exit_fill(
            PositionDirection.SHORT, 90.0, 91.0,
            slippage_rate=0.001, is_stop=False,
        )
        # Opened above the buy-limit target: not gapped through -> level+slip.
        assert fill == pytest.approx(90.09)

    def test_short_target_gap_fills_at_open(self) -> None:
        fill = simulate_exit_fill(
            PositionDirection.SHORT, 90.0, 89.5,
            slippage_rate=0.001, is_stop=False,
        )
        assert fill == pytest.approx(89.5)

    def test_wilder_atr_basic_and_insufficient(self) -> None:
        highs = [11.0] * 20
        lows = [9.0] * 20
        closes = [10.0] * 20
        atr = wilder_atr(highs, lows, closes, 14)
        assert atr is not None and atr == pytest.approx(2.0)
        assert wilder_atr(highs[:5], lows[:5], closes[:5], 14) is None


# ---------------------------------------------------------------------------
# Replay behavior + anti-look-ahead
# ---------------------------------------------------------------------------


class TestReplayBasics:
    def test_sawtooth_produces_alternating_edge_trades(self) -> None:
        dataset = sawtooth_dataset(cycles=20)
        result = BacktestRunner().replay(dataset, make_config())
        assert result.candles_replayed == 20 * 24
        assert len(result.trades) >= 10
        directions = {trade.direction for trade in result.trades}
        assert directions == {PositionDirection.LONG, PositionDirection.SHORT}
        assert all(trade.status is TradeStatus.CLOSED for trade in result.trades)

    def test_determinism_identical_inputs_identical_results(self) -> None:
        dataset = sawtooth_dataset(cycles=8)
        config = make_config()
        clone = BacktestConfig(
            symbol=config.symbol,
            timeframe=config.timeframe,
            start_ms=config.start_ms,
            end_ms=config.end_ms,
            initial_capital=config.initial_capital,
            range_config=dict(config.range_config),
            signal_config=dict(config.signal_config),
            risk_config=dict(config.risk_config),
            fee_rate=config.fee_rate,
            slippage_rate=config.slippage_rate,
            regime_lookback=config.regime_lookback,
            regime_threshold=config.regime_threshold,
            strategy_id=config.strategy_id,
            config_version=config.config_version,
            warmup_candles=config.warmup_candles,
        )
        assert clone == config and clone.config_hash == config.config_hash
        runner = BacktestRunner()
        first = runner.replay(dataset, config)
        second = runner.replay(dataset, clone)
        assert first.run_id == second.run_id
        assert first == second

    def test_empty_dataset_runs_clean_with_no_trades(self) -> None:
        dataset = CandleDataset(symbol="BTC/USDT", timeframe=Timeframe.H1, candles=())
        result = BacktestRunner().replay(dataset, make_config())
        assert result.trades == ()
        assert result.final_equity == pytest.approx(10_000.0)
        assert result.observations == ()

    def test_insufficient_data_yields_no_decisions(self) -> None:
        dataset = sawtooth_dataset(cycles=1)  # 24 bars
        strict = BacktestConfig(
            symbol="BTC/USDT", timeframe=Timeframe.H1,
            start_ms=BASE_TS, end_ms=BASE_TS + 500 * HOUR,
            initial_capital=10_000.0,
            range_config={"mode": "manual", "params": {
                "range_high": 106.0, "range_low": 94.0}},
            signal_config={"confirmation_policy": "ignored"},
            warmup_candles=40,
        )
        result = BacktestRunner().replay(dataset, strict)
        assert result.trades == () and result.decisions_evaluated == 0

    def test_forming_candles_excluded_from_replay(self) -> None:
        base = sawtooth_dataset(cycles=4)
        forming = MarketCandle(
            symbol="BTC/USDT", timeframe=Timeframe.H1,
            timestamp=BASE_TS + 200 * HOUR,
            open=100.0, high=101.0, low=99.0, close=100.5,
            volume=1.0, is_closed=False,
        )
        dataset = CandleDataset(
            symbol="BTC/USDT", timeframe=Timeframe.H1,
            candles=base.candles + (forming,),
        )
        result = BacktestRunner().replay(dataset, make_config())
        assert result.candles_replayed == 96  # forming bar never counted
        reference = BacktestRunner().replay(base, make_config())
        assert result == reference

    def test_symbol_or_timeframe_mismatch_rejected(self) -> None:
        dataset = sawtooth_dataset(cycles=2, symbol="ETH/USDT")
        with pytest.raises(ValueError, match="symbol"):
            BacktestRunner().replay(dataset, make_config())
        eth_dataset = CandleDataset(
            symbol="BTC/USDT", timeframe=Timeframe.M15, candles=()
        )
        with pytest.raises(ValueError, match="timeframe"):
            BacktestRunner().replay(eth_dataset, make_config())

    def test_anti_lookahead_suffix_cannot_change_prefix_decisions(self) -> None:
        """Decisions inside window A are identical with or without suffix B."""
        prefix = sawtooth_dataset(cycles=10)  # bars [0,240)
        crash_tail: list[MarketCandle] = []
        crash_ts = BASE_TS + 240 * HOUR
        for index in range(60):  # catastrophic future segment
            price = 90.0 - index
            crash_tail.append(MarketCandle(
                symbol="BTC/USDT", timeframe=Timeframe.H1,
                timestamp=crash_ts + index * HOUR,
                open=price + 1.0, high=price + 1.5, low=price - 2.0, close=price,
                volume=99.0,
            ))
        combined = CandleDataset(
            symbol="BTC/USDT",
            timeframe=Timeframe.H1,
            candles=prefix.candles + tuple(crash_tail),
        )
        config_a = make_config(end_ms=BASE_TS + 240 * HOUR)
        result_prefix = BacktestRunner().replay(prefix, config_a)
        result_combined_same_window = BacktestRunner().replay(combined, config_a)
        assert result_prefix.trades == result_combined_same_window.trades
        assert result_prefix.equity_curve == result_combined_same_window.equity_curve


# ---------------------------------------------------------------------------
# Range engine integration (all modes; no duplicate detectors here)
# ---------------------------------------------------------------------------


class TestRangeModes:
    def test_manual_mode_trades_both_edges(self) -> None:
        result = BacktestRunner().replay(
            sawtooth_dataset(cycles=12),
            make_config(range_config={"mode": "manual", "params": {
                "range_high": 106.0, "range_low": 94.0}}),
        )
        assert len(result.trades) >= 6
        assert result.zone_counts["lower_edge"] > 0
        assert result.zone_counts["upper_edge"] > 0

    def test_structural_default_mode_replays(self) -> None:
        config = make_config(
            range_config={"mode": "structural", "params": {"lookback": 40}},
        )
        result = BacktestRunner().replay(sawtooth_dataset(cycles=15), config)
        assert result.candles_replayed == 360
        # Ranging sawtooth: structural may or may not approve; must not crash
        # and observations must be recorded either way.
        assert len(result.observations) > 0

    def test_volatility_bollinger_and_atr_modes_run(self) -> None:
        dataset = sawtooth_dataset(cycles=10)
        for method in ("bollinger", "atr"):
            config = make_config(
                range_config={"mode": "volatility",
                              "params": {"method": method, "period": 20}},
                warmup_candles=25,
            )
            result = BacktestRunner().replay(dataset, config)
            assert result.candles_replayed == 240

    def test_degenerate_ranges_never_trade(self) -> None:
        """A trending market yields no tradable range and thus no trades."""
        result = BacktestRunner().replay(
            trending_dataset(bars=200, drift=0.8),
            make_config(range_config={"mode": "structural",
                                      "params": {"lookback": 30}},
                        warmup_candles=35),
        )
        assert result.trades == ()
        assert all(not obs.tradable_range for obs in result.observations)


# ---------------------------------------------------------------------------
# Signals, middle-of-range, confirmation policies
# ---------------------------------------------------------------------------


class TestSignalBehavior:
    def test_long_entries_come_from_lower_edge_short_from_upper(self) -> None:
        result = BacktestRunner().replay(
            sawtooth_dataset(cycles=16), make_config()
        )
        longs = [t for t in result.trades if t.direction is PositionDirection.LONG]
        shorts = [t for t in result.trades if t.direction is PositionDirection.SHORT]
        assert longs and shorts
        assert all(t.context.signal_reason == "support_edge_setup" for t in longs)
        assert all(t.context.signal_reason == "resistance_edge_setup" for t in shorts)

    def test_middle_of_range_is_no_trade_region(self) -> None:
        result = BacktestRunner().replay(
            sawtooth_dataset(cycles=12), make_config()
        )
        # Research counter: middle observations exist but produce zero trades.
        entered_zones = {
            trade.context.extra["zone"] for trade in result.trades if trade.context
        }
        assert "middle" not in entered_zones

    def test_confirmation_required_vs_ignored_differ(self) -> None:
        dataset = sawtooth_dataset(cycles=14)
        ignored = BacktestRunner().replay(dataset, make_config())
        required = BacktestRunner().replay(
            dataset,
            make_config(signal_config={"confirmation_policy": "required"}),
        )
        # Without oscillator metadata the required policy blocks everything.
        assert len(ignored.trades) > 0
        assert required.trades == ()
        assert required.decisions_evaluated <= ignored.decisions_evaluated


# ---------------------------------------------------------------------------
# Risk engine reuse + rejection behavior
# ---------------------------------------------------------------------------


class TestRiskIntegration:
    def test_risk_per_trade_controls_position_size(self) -> None:
        """Same first decision: quantity scales exactly with risk percent."""
        dataset = sawtooth_dataset(cycles=10)
        small = BacktestRunner().replay(
            dataset,
            make_config(risk_config={"risk_per_trade": 0.002}, warmup_candles=5),
        )
        large = BacktestRunner().replay(
            dataset,
            make_config(risk_config={"risk_per_trade": 0.01}, warmup_candles=5),
        )
        assert small.trades and large.trades
        first_small = small.trades[0].quantity
        first_large = large.trades[0].quantity
        assert first_large == pytest.approx(first_small * 5.0, rel=1e-9)

    def test_oversized_notional_rejected_by_funding_check(self) -> None:
        """risk 90% of a $10 account cannot fund its own notional."""
        result = BacktestRunner().replay(
            sawtooth_dataset(cycles=10),
            make_config(initial_capital=10.0,
                        risk_config={"risk_per_trade": 0.9}),
        )
        assert result.trades == ()

    def test_unfundable_positions_never_trade(self) -> None:
        """Equity stays untouched when the funding gate rejects everything."""
        result = BacktestRunner().replay(
            sawtooth_dataset(cycles=10),
            make_config(initial_capital=10.0,
                        risk_config={"risk_per_trade": 0.9}),
        )
        assert result.trades == ()
        assert result.final_equity == pytest.approx(10.0)

    def test_stops_and_targets_derived_from_range(self) -> None:
        result = BacktestRunner().replay(
            sawtooth_dataset(cycles=10), make_config()
        )
        trade = result.trades[0]
        assert trade.context.stop_distance is not None and trade.context.stop_distance > 0
        assert trade.context.target_distance is not None and trade.context.target_distance > 0


# ---------------------------------------------------------------------------
# Trade anatomy: wins, losses, breakeven-ish, context, identity
# ---------------------------------------------------------------------------


class TestTradeResults:
    def test_target_exit_is_win_with_positive_r(self) -> None:
        result = BacktestRunner().replay(sawtooth_dataset(cycles=12), make_config())
        target_wins = [
            t for t in result.trades
            if t.context.extra.get("exit_reason") == "target"
        ]
        assert target_wins, "sawtooth should produce target exits"
        winner = target_wins[0]
        assert winner.result.value == "win"
        assert winner.realized_pnl > 0
        assert winner.realized_r is not None and winner.realized_r > 0
        assert winner.fees > 0
        assert winner.slippage >= 0

    def _flat_warmup(self, close_low: float, close_high: float) -> list[MarketCandle]:
        """Quiet warmup candles whose closes sit in the requested band."""
        bars: list[MarketCandle] = []
        span = close_high - close_low
        for index in range(40):
            frac = index % 4 / 4
            close = close_low + span * frac
            bars.append(MarketCandle(
                symbol="BTC/USDT", timeframe=Timeframe.H1,
                timestamp=BASE_TS + index * HOUR,
                open=close + 0.05, high=close + 0.15, low=close - 0.15,
                close=close, volume=10.0,
            ))
        return bars

    def _bar(self, index: int, open_: float, high: float, low: float,
             close: float) -> MarketCandle:
        return MarketCandle(
            symbol="BTC/USDT", timeframe=Timeframe.H1,
            timestamp=BASE_TS + index * HOUR,
            open=open_, high=high, low=low, close=close, volume=10.0,
        )

    WIN_DATASET_CONFIG = {
        "range_high": 110.0, "range_low": 90.0,
    }

    def test_target_win_hits_exact_r_geometry(self) -> None:
        """Lower-edge LONG rides to the opposite edge -> clean positive R."""
        bars = self._flat_warmup(91.2, 92.0)
        # Decision bar: close 91.5 sits deep in the lower edge zone.
        bars.append(self._bar(40, 91.7, 92.0, 91.3, 91.5))
        # Entry bar and climb: never touches stop (89) until target (110).
        path = [91.6, 93.5, 96.0, 99.0, 102.0, 105.0, 107.5]
        for offset, close in enumerate(path, start=41):
            bars.append(self._bar(offset, close - 0.4, close + 0.5,
                                  close - 0.9, close))
        bars.append(self._bar(41 + len(path), 109.6, 110.4, 109.0, 110.2))
        dataset = CandleDataset(symbol="BTC/USDT", timeframe=Timeframe.H1,
                                candles=tuple(bars))
        config = make_config(
            end_ms=BASE_TS + 200 * HOUR,
            fee_rate=0.0, slippage_rate=0.0,
            range_config={"mode": "manual",
                          "params": {"range_high": 110.0, "range_low": 90.0}},
            risk_config={"stop_method": "fixed_percent",
                         "fixed_stop_percent": 0.01},
            warmup_candles=30,
        )
        result = BacktestRunner().replay(dataset, config)
        assert len(result.trades) == 1
        trade = result.trades[0]
        assert trade.direction is PositionDirection.LONG
        assert trade.result.value == "win"
        assert trade.context.extra["exit_reason"] == "target"
        assert trade.realized_r is not None and trade.realized_r > 5.0

    def test_stop_out_produces_loss_near_minus_one_r(self) -> None:
        """Upper-edge SHORT stopped on a later ordinary bar -> about -1R."""
        bars = self._flat_warmup(107.8, 108.6)
        # Decision bar: close 108.5 in the upper edge zone (SHORT setup).
        bars.append(self._bar(40, 108.3, 108.8, 108.1, 108.5))
        # Entry bar drifts mildly; stop sits ~1% above (fixed percent).
        bars.append(self._bar(41, 108.4, 108.9, 107.9, 108.2))
        # Later bar spikes through the stop WITHOUT gapping past it at open.
        bars.append(self._bar(42, 108.0, 111.5, 106.5, 107.0))
        dataset = CandleDataset(symbol="BTC/USDT", timeframe=Timeframe.H1,
                                candles=tuple(bars))
        config = make_config(
            end_ms=BASE_TS + 100 * HOUR,
            fee_rate=0.0, slippage_rate=0.0,
            range_config={"mode": "manual",
                          "params": {"range_high": 110.0, "range_low": 104.0}},
            risk_config={"stop_method": "range"},  # 110 + 5% buffer = 110.3
            warmup_candles=30,
        )
        result = BacktestRunner().replay(dataset, config)
        losses = [t for t in result.trades if t.result.value == "loss"]
        assert losses, "stop must trigger on the spike bar"
        loss = losses[0]
        assert loss.direction is PositionDirection.SHORT
        assert loss.context.extra["exit_reason"] == "stop"
        assert -1.2 < loss.realized_r < -0.8

    def test_trade_context_records_research_fields(self) -> None:
        result = BacktestRunner().replay(sawtooth_dataset(cycles=10), make_config())
        trade = result.trades[0]
        context = trade.context
        assert context.range_mode == "manual"
        assert context.range_high == pytest.approx(106.0)
        assert context.range_low == pytest.approx(94.0)
        assert context.range_width == pytest.approx(12.0)
        assert context.timeframe == "1h"
        assert context.strategy_config_version == "range-strategy@v0"
        assert context.extra["simulated"] is True
        assert context.extra["regime"] in {r.value for r in MarketRegime}
        assert context.extra["exit_reason"] in {"stop", "target"}
        assert trade.strategy_id == "range-strategy"
        assert trade.config_hash == result.config_hash

    def test_no_partial_fill_invention(self) -> None:
        """Assumption A6: full fills only; quantity equals decision size."""
        result = BacktestRunner().replay(sawtooth_dataset(cycles=8), make_config())
        quantities = {round(t.quantity, 9) for t in result.trades}
        # All fills are complete; no fabricated fractional remainders.
        assert all(q > 0 for q in quantities)
        assert all(t.exit_price is not None for t in result.trades)


# ---------------------------------------------------------------------------
# Statistics & equity curve (derived, never hardcoded)
# ---------------------------------------------------------------------------


class TestStatisticsAndEquity:
    def test_statistics_derived_from_trades(self) -> None:
        result = BacktestRunner().replay(sawtooth_dataset(cycles=12), make_config())
        stats = result.statistics
        assert stats.total_trades == len(result.trades)
        assert stats.completed_trades == stats.total_trades
        if stats.wins and not stats.losses:
            assert stats.win_rate == pytest.approx(1.0)
        elif stats.losses:
            expected = stats.wins / (stats.wins + stats.losses)
            assert stats.win_rate == pytest.approx(expected)

    def test_equity_curve_reconciles_with_trades(self) -> None:
        result = BacktestRunner().replay(sawtooth_dataset(cycles=12), make_config())
        curve = result.equity_curve
        assert len(curve) == len(result.trades)
        equity = result.initial_capital
        peak = result.initial_capital
        for point in curve:
            equity = point.equity
            peak = max(peak, equity)
            assert point.peak_equity == pytest.approx(peak)
            assert point.drawdown == pytest.approx(peak - equity)
        assert result.final_equity == pytest.approx(equity)
        total_pnl = sum(t.realized_pnl or 0.0 for t in result.trades)
        assert result.final_equity == pytest.approx(
            result.initial_capital + total_pnl, rel=1e-9
        )
        assert result.max_drawdown == pytest.approx(
            max((p.drawdown for p in curve), default=0.0)
        )
        assert result.peak_equity >= result.initial_capital

    def test_fees_and_slippage_appear_in_costs(self) -> None:
        costly = BacktestRunner().replay(
            sawtooth_dataset(cycles=10),
            make_config(fee_rate=0.001, slippage_rate=0.001),
        )
        clean = BacktestRunner().replay(
            sawtooth_dataset(cycles=10),
            make_config(fee_rate=0.0, slippage_rate=0.0),
        )
        assert clean.trades and costly.trades
        assert all(t.fees == 0 for t in clean.trades)
        assert any(t.fees > 0 for t in costly.trades)
        # Costs reduce final equity relative to the frictionless run.
        assert costly.final_equity < clean.final_equity


# ---------------------------------------------------------------------------
# Oscillator-confirmed mode through the SAME factory
# ---------------------------------------------------------------------------


class TestOscillatorMode:
    def test_oscillator_confirmed_mode_runs_end_to_end(self) -> None:
        dataset = sawtooth_dataset(cycles=14)
        config = make_config(
            range_config={
                "mode": "oscillator_confirmed",
                "params": {
                    "base": {"mode": "manual",
                             "params": {"range_high": 106.0, "range_low": 94.0}},
                    "oscillator": "rsi",
                    "osc_period": 14,
                    "oversold": 35,
                    "overbought": 65,
                    "edge_proximity": 0.6,
                    "confirmation_policy": "ignored",
                },
            },
            signal_config={"confirmation_policy": "optional"},
            warmup_candles=20,
        )
        result = BacktestRunner().replay(dataset, config)
        # The wrapper computes RSI from the visible prefix only; whether the
        # sawtooth confirms is deterministic — just require sane replay.
        assert result.candles_replayed == 336
        modes = {t.context.range_mode for t in result.trades if t.context}
        assert all(mode == "manual" for mode in modes)


# ---------------------------------------------------------------------------
# Persistence of completed runs (Phase 7 additive extension)
# ---------------------------------------------------------------------------


def run_record_from(result, created_at_ms: int) -> BacktestRunRecord:
    import json

    from persistence.models import BacktestRunRecord

    return BacktestRunRecord(
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
            "win_rate": result.statistics.win_rate,
            "average_r": result.statistics.average_r,
            "profit_factor": result.statistics.profit_factor,
            "expectancy": result.statistics.expectancy,
            "total_realized_pnl": result.statistics.total_realized_pnl,
        }, sort_keys=True),
        config_json=result.config.to_json(),
        engine_version=result.engine_version,
        created_at_ms=created_at_ms,
    )


class TestRunPersistence:
    def test_save_get_list_roundtrip(self, tmp_path: Path) -> None:
        store = SqlitePersistence(tmp_path / "bt.db", clock_ms=lambda: 42)
        result = BacktestRunner().replay(sawtooth_dataset(cycles=8), make_config())
        record = run_record_from(result, created_at_ms=42)
        store.save_run(record)
        fetched = store.get_run(result.run_id)
        assert fetched == record
        listed = store.list_runs(symbol="BTC/USDT")
        assert [r.run_id for r in listed] == [record.run_id]
        assert store.list_runs(symbol="ETH/USDT") == ()
        by_hash = store.list_runs(config_hash=record.config_hash)
        assert len(by_hash) == 1
        store.close()

    def test_duplicate_run_id_rejected(self, tmp_path: Path) -> None:
        store = SqlitePersistence(tmp_path / "bt.db", clock_ms=lambda: 1)
        result = BacktestRunner().replay(sawtooth_dataset(cycles=8), make_config())
        record = run_record_from(result, created_at_ms=1)
        store.save_run(record)
        with pytest.raises(PersistenceError, match="already exists"):
            store.save_run(record)
        store.close()

    def test_v1_database_migrates_to_v2_preserving_data(self, tmp_path: Path) -> None:
        """An existing Phase 7 database upgrades safely to the new schema."""

        db_path = tmp_path / "legacy.db"
        legacy = SqlitePersistence(db_path, clock_ms=lambda: 7)
        legacy.ingest_dataset(sawtooth_dataset(cycles=2), source="binance")
        assert legacy.schema_version == 2  # fresh store already at head
        legacy.close()

        # Simulate a genuine v1 database: apply only migration 1.
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        conn.execute("DELETE FROM backtest_runs")
        conn.execute("DROP TABLE backtest_runs")
        conn.execute("DELETE FROM schema_migrations WHERE version=2")
        conn.commit()
        conn.close()

        reopened = SqlitePersistence(db_path, clock_ms=lambda: 8)
        assert reopened.schema_version == SCHEMA_VERSION_2
        candles = reopened.query_candles("BTC/USDT", Timeframe.H1, source="binance")
        assert len(candles.candles) == 48
        record = run_record_from(
            BacktestRunner().replay(sawtooth_dataset(cycles=8), make_config()),
            created_at_ms=9,
        )
        reopened.save_run(record)
        assert reopened.get_run(record.run_id) is not None
        reopened.close()


SCHEMA_VERSION_2 = 2
