"""The lightweight scanner response must preserve full chart decisions."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from test_balanced_range import BASE, wave, range_touch_preset, CandleDataset, Timeframe
from app_layer.services.balanced_analysis import analyze_balanced


@pytest.mark.parametrize("timeframe", ["1m", "15m", "1h", "4h", "1d", "1w"])
@pytest.mark.parametrize("quality", ["complete", "gap", "stale"])
def test_summary_preserves_decisions(timeframe, quality):
    now = BASE + 200 * Timeframe.W1.duration_ms
    datasets = {}
    for key in dict.fromkeys(("1w", "1d", "4h", "1h", timeframe)):
        tf = Timeframe(key)
        bars = tuple(replace(b, timeframe=tf, timestamp=now - (120-i)*tf.duration_ms)
                     for i, b in enumerate(wave()))
        if quality == "gap" and key == "1h":
            bars = bars[:70] + bars[71:]
        if quality == "stale":
            bars = bars[:-3]
        datasets[key] = CandleDataset("BTC/USDT", tf, bars)
    markets = SimpleNamespace(candles=lambda symbol, tf, **kw: datasets[tf])
    args = (markets, None, "BTC/USDT", timeframe, range_touch_preset(), None, "Test", 200, now)
    full = analyze_balanced(*args)
    brief = analyze_balanced(*args, summary=True)
    for key in full.keys() - {"candles", "swing_failures", "range_events"}:
        assert brief[key] == full[key], key
    assert brief["candles"] == full["candles"][-1:]
    last = full["freshness"]["last_closed_timestamp_ms"]
    assert brief["swing_failures"] == [e for e in full["swing_failures"] if e["timestamp"] == last]
    assert brief["range_events"] == []
    if quality != "complete":
        assert brief["signal"]["direction"] == "none"


def test_summary_keeps_latest_sfp_and_omits_older_sweeps(monkeypatch):
    from test_balanced_range import frozen_context, sfp_bars, candle
    from app_layer.services import balanced_analysis as module

    snap = frozen_context()["1h"].at(BASE)
    monkeypatch.setattr(module, "_closed_timeline",
                        lambda rows, cfg: SimpleNamespace(bars=rows, at=lambda t: snap))
    for trailing_bars in (0, 5):
        rows = sfp_bars() + [candle(i) for i in range(21, 21 + trailing_bars)]
        now = rows[-1].close_time_ms
        def dataset(symbol, key, **kwargs):
            tf = Timeframe(key)
            bars = tuple(replace(b, timeframe=tf, timestamp=now - (len(rows)-i)*tf.duration_ms)
                         for i, b in enumerate(rows))
            return CandleDataset(symbol, tf, bars)
        args = (SimpleNamespace(candles=dataset), None, "BTC/USDT", "5m",
                range_touch_preset(), None, "Test", 200, now)
        full = analyze_balanced(*args)
        brief = analyze_balanced(*args, summary=True)
        assert any(e.get("grade") == "A+" for e in full["swing_failures"])
        assert brief["market_state"] == full["market_state"]
        assert brief["swing_failures"] == [e for e in full["swing_failures"]
                                             if e["timestamp"] == rows[-1].timestamp]
        assert bool(brief["swing_failures"]) == (trailing_bars == 0)
