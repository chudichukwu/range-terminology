"""Behavioral tests of the revised range specification."""

import math
from dataclasses import replace
from datetime import UTC
from types import SimpleNamespace

import pytest

from app_layer.services.playbook import range_touch_preset
from backtesting.models import BacktestConfig
from backtesting.regime import MarketRegime
from backtesting.runner import BacktestRunner
from exchange.models import PositionDirection
from market_data.models import CandleDataset, MarketCandle, Timeframe
from range_engine.balanced import (
    DEFAULTS,
    Snapshot,
    Timeline,
    evaluate_entry,
    indicators,
    range_timeline,
    settings,
    trade_plan,
)

BASE = 1_700_000_000_000


def candle(i, o=110, h=111, low=109, c=110, tf=Timeframe.M5):
    return MarketCandle("BTC/USDT", tf, BASE + i * tf.duration_ms, o, h, low, c, 100.0)


def wave(n=120):
    bars = []
    for i in range(n):
        c = 100 + 10 * math.sin(i * math.pi / 6)
        o = 100 + 10 * math.sin((i - 1) * math.pi / 6)
        bars.append(candle(i, o, max(o, c) + 0.2, min(o, c) - 0.2, c, Timeframe.H1))
    return bars


def frozen_context(trend=None):
    snap = Snapshot(
        BASE, "ranging", 100.0, 120.0, 2.0, 10.0, 110.0, 110.0, None, 3, 3, "Confirmed", BASE
    )
    out = {tf: SimpleNamespace(at=lambda t, s=snap: s) for tf in ("1w", "1d", "4h", "1h")}
    if trend:
        bad = replace(snap, state="trending", trend=trend, adx=40)
        out["1d"] = SimpleNamespace(at=lambda t: bad)
    return out


def sfp_bars():
    return [candle(i) for i in range(20)] + [candle(20, 102, 103, 99, 101)]


def test_indicators_wilder_seed_and_trend():
    bars = [candle(i, 100 + i, 102 + i, 99 + i, 101 + i) for i in range(70)]
    ind = indicators(bars)
    assert math.isnan(ind["atr"][13])
    assert ind["atr"][14] == pytest.approx(3)
    assert math.isnan(ind["adx"][26])
    assert ind["adx"][27] == pytest.approx(100)
    assert ind["ema20"][-1] > ind["ema50"][-1]


def test_range_requires_repeated_touches_height_and_balance():
    states = range_timeline(wave(), DEFAULTS)
    valid = [s for s in states if s.valid]
    assert valid
    assert all(min(s.low_touches, s.high_touches) >= 2 for s in valid)
    assert all(s.high - s.low >= 2.5 * s.atr and s.adx < 22 for s in valid)
    narrow = range_timeline(wave(), {**DEFAULTS, "min_height_atr": 100})
    assert not any(s.valid for s in narrow)


def test_breakout_is_not_absorbed_into_a_redrawn_range():
    bars = wave()
    bounds = next(s for s in reversed(range_timeline(bars, DEFAULTS)) if s.valid)
    bars += [
        candle(120, 105, 130, 104, 129, Timeframe.H1),
        candle(121, 129, 132, 128, 131, Timeframe.H1),
    ]
    end = range_timeline(bars, DEFAULTS)[-1]
    assert end.state == "breakout"
    assert end.low == bounds.low and end.high == bounds.high


def test_timeline_has_no_future_leakage():
    bars = wave()
    timeline = Timeline(bars, DEFAULTS)
    cut = 80
    assert timeline.at(bars[cut].close_time_ms) == Timeline(bars[: cut + 1], DEFAULTS).at(
        bars[cut].close_time_ms
    )
    assert timeline.at(bars[cut].timestamp) == timeline.snapshots[cut - 1]


def test_sfp_is_range_boundary_reclaim_and_stops_beyond_wick():
    signal = evaluate_entry(sfp_bars(), frozen_context(), DEFAULTS)
    assert signal["direction"] == "long"
    assert signal["sfp"]["grade"] == "A+"
    assert signal["range_timeframe"] == "4h"
    assert signal["stop"] == pytest.approx(98.25)
    assert signal["tp1"] == 110 and signal["tp2"] == 119.6
    assert trade_plan(signal, DEFAULTS)["approved"]


def test_opposing_daily_trend_blocks_fade():
    signal = evaluate_entry(sfp_bars(), frozen_context("down"), DEFAULTS)
    assert signal["direction"] == "none"
    assert "1d" in signal["reason"]
    assert signal["sfp"] is not None


def test_two_bar_reclaim_and_no_repeated_sfp():
    bars = sfp_bars()[:-1] + [candle(20, 102, 103, 99, 99.8), candle(21, 99.8, 102, 99.5, 101)]
    signal = evaluate_entry(bars, frozen_context(), {**DEFAULTS, "confirmation": "sfp"})
    assert signal["direction"] == "long"
    assert signal["sfp"]["swing_timestamp"] == bars[-2].timestamp
    bars.append(candle(22, 101, 102, 100.5, 101.5))
    assert (
        evaluate_entry(bars, frozen_context(), {**DEFAULTS, "confirmation": "sfp"})["direction"]
        == "none"
    )


def test_volume_gate_and_weighted_reward_risk():
    signal = evaluate_entry(sfp_bars(), frozen_context(), {**DEFAULTS, "volume_multiple": 2.0})
    assert signal["direction"] == "none"
    signal = evaluate_entry(sfp_bars(), frozen_context(), DEFAULTS)
    assert not trade_plan(signal, DEFAULTS, entry=109)["approved"]


def test_bearish_sfp_mirrors_bullish():
    bars = [candle(i) for i in range(20)] + [candle(20, 118, 121, 117, 119)]
    signal = evaluate_entry(bars, frozen_context(), DEFAULTS)
    assert signal["direction"] == "short"
    assert signal["stop"] == 121.75
    assert signal["tp2"] == 100.4


def staged(bars, direction=PositionDirection.LONG, runner_fraction=0):
    config = BacktestConfig(
        symbol="BTC/USDT",
        timeframe="5m",
        start_ms=BASE,
        end_ms=BASE + 100 * 300000,
        initial_capital=10000,
        fee_rate=0,
        slippage_rate=0,
    )
    return BacktestRunner()._simulate_position(
        window=tuple(bars),
        entry_index=0,
        direction=direction,
        quantity=10,
        stop_price=98 if direction == PositionDirection.LONG else 122,
        target_price=110,
        risk_amount=30,
        config=config,
        duration_ms=300000,
        range_high=120,
        range_low=100,
        range_mode="balanced",
        range_confidence=1,
        signal_reason="sfp",
        position_in_range=0.1,
        confirmation=True,
        regime=MarketRegime.RANGING,
        zone="lower_edge",
        trade_seq=1,
        staged_exit=dict(
            runner_fraction=runner_fraction,
            runner_trail_percent=.02,
            tp1_fraction=0.5,
            tp2=119.6 if direction == PositionDirection.LONG else 100.4,
            buffer=0.75,
            hold_closes=2,
        ),
    )


def test_midpoint_partial_then_opposite_edge_closes_all():
    trade, _, pnl = staged(
        [
            candle(0, 101, 108, 100, 107),
            candle(1, 108, 112, 107, 111),
            candle(2, 111, 120, 110, 119),
        ]
    )
    fills = trade.context.extra["exit_fills"]
    assert [f["reason"] for f in fills] == ["partial_target", "tp2"]
    assert [f["quantity"] for f in fills] == [5, 5]
    assert pnl == pytest.approx(5 * 9 + 5 * 18.6)


def test_midpoint_moves_stop_to_entry_and_same_bar_is_conservative():
    trade, _, pnl = staged([candle(0, 101, 112, 100, 111)])
    assert trade.context.extra["exit_fills"][-1]["reason"] == "breakeven_stop"
    assert pnl == 45


def test_held_close_invalidation_before_protective_stop():
    trade, _, _ = staged([candle(0, 101, 102, 98.5, 99), candle(1, 99, 100, 98.5, 99)])
    assert trade.context.extra["exit_fills"][-1]["reason"] == "range_invalidated"


def test_revised_preset_validation():
    preset = range_touch_preset()
    assert settings(preset)["min_reward_risk"] == 2
    with pytest.raises(ValueError):
        settings({"risk_config": {"tp1_fraction": 1}})


def test_multitimeframe_replay_executes_next_open_and_preserves_context():
    from app_layer.services.playbook import range_touch_preset
    from backtesting.balanced import replay_balanced

    preset = range_touch_preset()
    preset["risk_config"]["runner_fraction"] = 0
    entry_bars = [candle(i, 100, 101, 99, 100) for i in range(20)]
    entry_bars += [
        candle(20, 92, 93, 89, 91),
        candle(21, 92, 96, 91, 95),
        candle(22, 95, 103, 94, 102),
        candle(23, 102, 111, 101, 109),
    ]
    datasets = {"5m": CandleDataset("BTC/USDT", Timeframe.M5, tuple(entry_bars))}
    for tf in (Timeframe.W1, Timeframe.D1, Timeframe.H4, Timeframe.H1):
        template = wave()
        last_valid = max(i for i, s in enumerate(range_timeline(template, DEFAULTS)) if s.valid)
        template = template[: last_valid + 1]
        final = BASE - tf.duration_ms
        bars = tuple(
            replace(b, timeframe=tf, timestamp=final - (len(template) - 1 - i) * tf.duration_ms)
            for i, b in enumerate(template)
        )
        datasets[tf.value] = CandleDataset("BTC/USDT", tf, bars)
    config = BacktestConfig(
        symbol="BTC/USDT",
        timeframe="5m",
        start_ms=BASE,
        end_ms=BASE + 24 * 300000,
        initial_capital=10000,
        **preset,
        fee_rate=0,
        slippage_rate=0,
    )
    result = replay_balanced(datasets, config)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_price == 92
    assert trade.opened_at_ms == entry_bars[21].timestamp
    assert trade.context.extra["range_timeframe"] == "4h"
    assert all(
        t <= entry_bars[20].close_time_ms for t in trade.context.extra["context_asof"].values()
    )
    assert trade.context.extra["exit_fills"][0]["quantity"] == pytest.approx(trade.quantity * 0.5)
    assert trade.context.extra["exit_fills"][-1]["reason"] == "tp2"
    changed = dict(datasets)
    revised = list(datasets["1w"].candles)
    revised[0] = replace(revised[0], volume=101)
    changed["1w"] = replace(datasets["1w"], candles=tuple(revised))
    assert replay_balanced(changed, config).run_id != result.run_id


def test_short_midpoint_partial_then_final_target():
    trade, _, pnl = staged(
        [
            candle(0, 119, 120, 112, 113),
            candle(1, 113, 114, 108, 109),
            candle(2, 109, 110, 100, 101),
        ],
        PositionDirection.SHORT,
    )
    assert pnl == pytest.approx(5 * 9 + 5 * 18.6)
    assert trade.context.extra["exit_fills"][-1]["reason"] == "tp2"


def test_live_api_shape_and_multiframe_gap_suppression():
    from api.schemas.analysis import AnalysisOut
    from app_layer.services.balanced_analysis import analyze_balanced

    now = BASE + 200 * 604800000
    datasets = {}
    for tf in (Timeframe.W1, Timeframe.D1, Timeframe.H4, Timeframe.H1, Timeframe.M5):
        bars = tuple(
            replace(b, timeframe=tf, timestamp=now - (120 - i) * tf.duration_ms)
            for i, b in enumerate(wave())
        )
        datasets[tf.value] = CandleDataset("BTC/USDT", tf, bars)
    markets = SimpleNamespace(candles=lambda symbol, tf, **kw: datasets[tf])
    result = analyze_balanced(
        markets, None, "BTC/USDT", "5m", range_touch_preset(), None, "Test", 200, now
    )
    parsed = AnalysisOut(**result)
    assert set(parsed.timeframe_context) == {"1w", "1d", "4h", "1h"}
    assert parsed.is_analysis_safe
    original = datasets["1h"]
    datasets["1h"] = replace(original, candles=original.candles[:70] + original.candles[71:])
    result = analyze_balanced(
        markets, None, "BTC/USDT", "5m", range_touch_preset(), None, "Test", 200, now
    )
    assert not result["is_analysis_safe"]
    assert result["signal"]["direction"] == "none"
    assert any("1h" in issue for issue in result["quality_issues"])


def test_context_history_excludes_week_still_forming_at_replay_end():
    from datetime import datetime

    from app_layer.services.backtests import closed_history_end

    end = int(datetime(2026, 9, 23, tzinfo=UTC).timestamp() * 1000)
    monday = int(datetime(2026, 9, 21, tzinfo=UTC).timestamp() * 1000)
    assert closed_history_end(end, Timeframe.W1) == monday
    assert closed_history_end(end, Timeframe.D1) == end
    assert closed_history_end(monday, Timeframe.W1) == monday


def test_reclaim_does_not_revive_held_breakout():
    bars = [candle(i) for i in range(20)]
    bars += [candle(20, 102, 103, 98, 99), candle(21, 99, 100, 98, 99)]
    bars += [candle(i, 99, 100, 98, 99) for i in range(22, 26)]
    bars += [candle(26, 99, 102, 98, 101)]
    signal = evaluate_entry(bars, frozen_context(), DEFAULTS)
    assert signal["direction"] == "none"
    assert signal["state"] == "breakout"


@pytest.mark.parametrize('tf', ['1m', '5m', '15m', '1h', '4h', '1d'])
def test_chart_timeframe_sfp_does_not_require_hourly_range(tf):
    contexts = frozen_context()
    own = contexts['1h']
    empty = Snapshot(BASE, 'transition', reason='No hourly range')
    contexts['4h'] = contexts['1h'] = SimpleNamespace(at=lambda t: empty)
    contexts[tf] = own
    signal = evaluate_entry(sfp_bars(), contexts, DEFAULTS, range_timeframes=(tf,))
    assert signal['sfp']['range_timeframe'] == tf
    assert signal['sfp']['direction'] == 'bullish'


@pytest.mark.parametrize('tf', ['1m', '1h', '1d'])
def test_chart_analysis_returns_own_range_and_older_sfp(tf, monkeypatch):
    from app_layer.services import balanced_analysis as module
    snap = frozen_context()['1h'].at(BASE)
    bars = sfp_bars() + [candle(i) for i in range(21, 70)]
    frame = Timeframe(tf)
    bars = tuple(replace(b, timeframe=frame, timestamp=BASE + i * frame.duration_ms)
                 for i, b in enumerate(bars))
    now = bars[-1].close_time_ms
    def dataset(symbol, key, **kw):
        t = Timeframe(key)
        rows = bars if key == tf else tuple(
            replace(b, timeframe=t, timestamp=now - (len(bars)-i)*t.duration_ms)
            for i, b in enumerate(bars))
        return CandleDataset(symbol, t, rows)
    def timeline(rows, cfg):
        own = rows[0].timeframe.value == tf
        state = snap if own else replace(snap, low=50, high=200)
        return SimpleNamespace(bars=rows, at=lambda t: state)
    monkeypatch.setattr(module, 'Timeline', timeline)
    result = module.analyze_balanced(SimpleNamespace(candles=dataset), None, 'BTC/USDT',
                                    tf, range_touch_preset(), None, 'Test', 200, now)
    assert result['range']['low'] == 100
    assert result['range']['metadata']['range_timeframe'] == tf
    assert any(e['timestamp'] == bars[20].timestamp for e in result['swing_failures'])


def test_swing_sfp_visible_without_valid_range_and_not_repeated():
    import pandas as pd

    from signal_engine.structure import swing_failures

    rows = [dict(timestamp=i, high=h, low=0, close=h-1)
            for i, h in enumerate([3, 4, 8, 4, 3, 9, 9])]
    rows[5]['close'] = rows[6]['close'] = 7
    events = swing_failures(pd.DataFrame(rows), recent=100)
    assert any(e['timestamp'] == 5 and e['direction'] == 'bearish' for e in events)
    assert not any(e['timestamp'] == 6 and e['direction'] == 'bearish' for e in events)


def test_outer_clusters_win_over_internal_congestion():
    from range_engine.balanced import _cluster
    assert _cluster([110]*10 + [120,120.1,150], .5, outer='high')[0] == pytest.approx(120.05)
    assert _cluster([110]*10 + [100,100.1,80], .5, outer='low')[0] == pytest.approx(100.05)


def test_broken_range_reclaims_same_boundaries_without_rewriting_history():
    bars = wave()
    original = range_timeline(bars, DEFAULTS)[-1]
    bars += [candle(120, 100, 101, 70, 71, Timeframe.H1),
             candle(121, 71, 73, 69, 70, Timeframe.H1)]
    broken = range_timeline(bars, DEFAULTS)
    assert broken[-1].state == 'breakout'
    bars += [candle(122, 70, 103, 69, 100, Timeframe.H1)]
    result = range_timeline(bars, DEFAULTS)
    assert result[:-1] == broken
    assert result[-1].reclaimed
    assert (result[-1].low, result[-1].high) == (original.low, original.high)
    assert result[-1].established == bars[-1].close_time_ms
    # Reclaim does not waive balance/trend filters or imply an approved trade.
    assert result[-1].established > original.established


def test_local_range_survives_high_adx_but_strict_policy_rejects(monkeypatch):
    import range_engine.balanced as module
    original = module.indicators
    def high_adx(bars):
        out = original(bars)
        out['adx'][54:] = 40
        return out
    monkeypatch.setattr(module, 'indicators', high_adx)
    contextual = range_timeline(wave(), DEFAULTS)
    strict = range_timeline(wave(), {**DEFAULTS, 'range_policy': 'strict'})
    assert any(s.valid and s.adx == 40 for s in contextual)
    assert not any(s.valid for s in strict)
    assert contextual[:80] == range_timeline(wave()[:80], DEFAULTS)


def test_runner_allocations_and_next_candle_trailing():
    bars = [candle(0,101,108,100,107), candle(1,108,112,107,111),
            candle(2,111,122,110,121), candle(3,121,130,120,129),
            candle(4,129,130,125,126)]
    trade, _, pnl = staged(bars, runner_fraction=.2)
    fills = trade.context.extra['exit_fills']
    assert [f['reason'] for f in fills] == ['partial_target','tp2_partial','runner_stop']
    assert [f['quantity'] for f in fills] == pytest.approx([5,3,2])
    assert fills[-1]['price'] == pytest.approx(129*.98)
    assert pnl == pytest.approx(5*9+3*18.6+2*(129*.98-101))
    # At candle 3, its low is below the stop derived from its close; that new stop
    # must not be applied until candle 4.
    assert fills[-1]['timestamp'] == bars[4].close_time_ms


def test_short_runner_and_end_of_data_account_for_every_unit():
    bars = [candle(0,119,120,112,113), candle(1,113,114,108,109),
            candle(2,109,110,98,99), candle(3,99,100,90,91), candle(4,91,95,90,94)]
    trade, _, _ = staged(bars, PositionDirection.SHORT, runner_fraction=.2)
    fills = trade.context.extra['exit_fills']
    assert fills[-1]['reason'] == 'runner_stop'
    assert fills[-1]['price'] == pytest.approx(91*1.02)
    assert sum(f['quantity'] for f in fills) == pytest.approx(10)
    trade, _, _ = staged(bars[:3], PositionDirection.SHORT, runner_fraction=.2)
    assert trade.context.extra['exit_fills'][-1]['reason'] == 'end_of_data'
    assert sum(f['quantity'] for f in trade.context.extra['exit_fills']) == pytest.approx(10)


def test_runner_cannot_inflate_reward_risk_and_invalid_allocations_rejected():
    signal = evaluate_entry(sfp_bars(), frozen_context(), DEFAULTS)
    baseline = trade_plan(signal, DEFAULTS)['reward_risk_ratio']
    with_runner = trade_plan(signal, {**DEFAULTS,'runner_fraction':.2})
    assert with_runner['reward_risk_ratio'] < baseline
    for value in (.5, .8, -1):
        with pytest.raises(ValueError):
            settings({'risk_config':{'runner_fraction':value}})


def test_midpoint_events_use_existing_boundaries_and_are_causal():
    from range_engine.context import range_observations
    snap = frozen_context()['1h'].at(BASE)
    timeline = SimpleNamespace(at=lambda t: snap)
    bars = [candle(0,105,106,104,105),candle(1,108,111,105,106),
            candle(2,106,113,105,112),candle(3,112,113,106,107)]
    events = range_observations(bars,timeline,DEFAULTS)
    assert [e['kind'] for e in events] == ['midpoint_rejection','midpoint_reclaim','midpoint_lost']
    assert range_observations(bars[:3],timeline,DEFAULTS) == events[:2]
    unconfirmed = SimpleNamespace(at=lambda t: replace(snap,established=0))
    assert range_observations(bars,unconfirmed,DEFAULTS) == []


def test_prior_poi_excludes_range_and_future_bars():
    from range_engine.context import nearby_levels
    bars = wave()
    snap = replace(frozen_context()['1h'].at(BASE), low=89.8, high=110.2,
                   origin=bars[70].timestamp)
    original = nearby_levels(bars[:71],snap,DEFAULTS)
    assert {e['kind'] for e in original} == {'prior_support','prior_resistance'}
    assert nearby_levels(bars,snap,DEFAULTS) == original
    assert all(e['timestamp'] < snap.origin for e in original)
