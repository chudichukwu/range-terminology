"""Behavioral coverage for the range-touch workflow (no network required)."""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from app_layer.services.alerts import AlertService
from backtesting.runner import BacktestRunner
from market_data.models import CandleDataset, MarketCandle, Timeframe
from range_engine.base import RangeState, RangeStatus
from range_engine.factory import RangeEngineFactory
from risk_engine.base import AccountRiskState
from risk_engine.engine import RiskEngine
from signal_engine.base import SignalDirection
from signal_engine.engine import RangeSignalEngine
from signal_engine.structure import swing_failures, touch_signal
from test_backtesting import BASE_TS, HOUR, make_config, sawtooth_dataset


def state():
    return RangeState(110, 100, "manual", 1, {}, RangeStatus.VALID)


def test_touch_entry_uses_boundary_not_candle_close():
    s = touch_signal(
        {"open": 105, "high": 108, "low": 99, "close": 107},
        state(),
        {"confirmation_policy": "ignored"},
    )
    assert s.direction is SignalDirection.LONG
    assert s.price == 100


@pytest.mark.parametrize(
    "bar",
    [
        {"open": 105, "high": 111, "low": 99, "close": 106},
        {"open": 105, "high": 109, "low": 101, "close": 102},
        {"open": 98, "high": 103, "low": 97, "close": 101},
    ],
)
def test_ambiguous_untouched_or_gap_entries_are_not_fabricated(bar):
    assert touch_signal(bar, state()).direction is SignalDirection.NONE


@pytest.mark.parametrize(("price", "expected"), [(100, 98), (110, 112.2)])
def test_invalidation_is_two_percent_of_boundary_not_range_width(price, expected):
    sig = RangeSignalEngine({"confirmation_policy": "ignored"}).evaluate(price, state())
    risk = RiskEngine(
        {
            "stop_method": "range_percent",
            "fixed_stop_percent": 0.02,
            "min_reward_risk": 0.1,
            "max_leverage": 3,
        }
    ).evaluate(
        sig,
        AccountRiskState(
            equity=10000, available_balance=10000, peak_equity=10000, daily_start_equity=10000
        ),
    )
    assert risk.approved
    assert risk.stop_price == pytest.approx(expected)


def test_repeated_touch_gate_counts_boundary_touches():
    d = sawtooth_dataset(cycles=5)
    df = d.to_dataframe()
    valid = RangeEngineFactory.detect(df, {"min_touches": 2, "touch_tolerance": 0.05})
    assert valid.is_tradable
    assert valid.metadata["high_touches"] >= 2
    blocked = RangeEngineFactory.detect(df, {"min_touches": 20})
    assert not blocked.is_tradable
    assert blocked.metadata["reason"] == "awaiting_repeated_touches"


def test_swing_failure_is_sweep_close_and_uses_only_prior_confirmed_pivot():
    highs = [102, 104, 110, 105, 103, 104, 111, 105]
    df = pd.DataFrame(
        {
            "timestamp": [BASE_TS + i * HOUR for i in range(8)],
            "open": [100] * 8,
            "high": highs,
            "low": [98] * 8,
            "close": [101.0] * 8,
            "volume": [1] * 8,
        }
    )
    events = swing_failures(df.iloc[:7])
    assert events == [
        {
            "direction": "bearish",
            "level": 110.0,
            "timestamp": BASE_TS + 6 * HOUR,
            "swing_timestamp": BASE_TS + 2 * HOUR,
        }
    ]
    extended = swing_failures(df)
    assert events[0] in extended
    df.loc[6, "close"] = 110.5
    assert swing_failures(df.iloc[:7]) == []


def test_weekly_candle_close_uses_full_week():
    c = MarketCandle("BTC/USDT", Timeframe.W1, 345600000, 100, 110, 90, 105)
    assert c.close_time_ms == 950400000


def touch_replay(bars, runner=0.25):
    candles = tuple(
        MarketCandle("BTC/USDT", Timeframe.H1, BASE_TS + i * HOUR, *bar)
        for i, bar in enumerate(bars)
    )
    d = CandleDataset("BTC/USDT", Timeframe.H1, candles)
    cfg = make_config(
        warmup_candles=2,
        range_config={"mode": "manual", "range_low": 100, "range_high": 110},
        signal_config={"entry_mode": "touch", "confirmation_policy": "ignored"},
        risk_config={
            "stop_method": "range_percent",
            "fixed_stop_percent": 0.02,
            "min_reward_risk": 0.1,
            "max_leverage": 3,
            "runner_fraction": runner,
            "runner_trail_percent": 0.02,
        },
        fee_rate=0,
        slippage_rate=0,
    )
    return BacktestRunner().replay(d, cfg)


def test_partial_target_and_runner_account_for_all_quantity():
    result = touch_replay(
        [
            (105, 107, 103, 105),
            (105, 107, 103, 105),
            (105, 106, 100, 102),
            (103, 111, 102, 110),
            (111, 116, 109, 115),
            (115, 116, 112, 113),
        ]
    )
    assert len(result.trades) == 1
    trade = result.trades[0]
    fills = trade.context.extra["exit_fills"]
    assert fills[0]["reason"] == "partial_target"
    assert sum(f["quantity"] for f in fills) == pytest.approx(trade.quantity)
    assert fills[0]["quantity"] == pytest.approx(trade.quantity * 0.75)
    assert trade.realized_pnl == pytest.approx(
        sum((f["price"] - 100) * f["quantity"] for f in fills)
    )
    assert result.final_equity == pytest.approx(10000 + trade.realized_pnl)


def test_touch_entry_stops_when_same_bar_breaches_invalidation():
    result = touch_replay(
        [(105, 107, 103, 105), (105, 107, 103, 105), (105, 108, 97, 101), (102, 106, 101, 103)]
    )
    assert len(result.trades) == 1
    assert result.trades[0].exit_price == 98
    assert result.trades[0].realized_pnl < 0


def test_open_runner_marked_at_end_of_data_not_discarded():
    result = touch_replay(
        [(105, 107, 103, 105), (105, 107, 103, 105), (105, 106, 100, 102), (108, 111, 108, 110)]
    )
    assert len(result.trades) == 1
    assert result.trades[0].context.extra["exit_fills"][-1]["reason"] == "end_of_data"


def test_alert_dedup_is_durable_and_owner_scoped(tmp_path):
    path = str(tmp_path / "alerts.db")
    a = AlertService(path)
    assert a.record("alice", "edge:1", {"message": "touch"})
    assert a.record("alice", "edge:1", {"message": "touch"}) is None
    assert a.record("bob", "edge:1", {"message": "touch"})
    a.mark_seen("alice")
    assert a.events("alice")[0]["seen"]
    assert not a.events("bob")[0]["seen"]
    a.close()
    reopened = AlertService(path)
    assert reopened.record("alice", "edge:1", {"message": "touch"}) is None
    reopened.close()


def test_alert_api_auth_ownership_and_config_validation(tmp_path):
    with TestClient(create_app(str(tmp_path / "app.db"))) as c:
        assert c.get("/alerts").status_code == 401
        from test_api import auth_headers, bootstrap_owner, create_user

        root = bootstrap_owner(c)
        alice = auth_headers(create_user(c, root, "alice@example.com"))
        bob = auth_headers(create_user(c, root, "bob@example.com"))
        wid = c.post("/watchlists", json={"name": "My list"}, headers=alice).json()["id"]
        body = {"watchlist_id": wid, "timeframes": ["1h", "1w"], "enabled": False}
        assert c.post("/alerts/rules", json=body, headers=bob).status_code == 404
        assert c.post("/alerts/rules", json=body, headers=alice).status_code == 200
        assert len(c.get("/alerts/rules", headers=alice).json()["rules"]) == 1
        assert c.get("/alerts/rules", headers=bob).json()["rules"] == []
        assert (
            c.post("/alerts/rules", json={**body, "timeframes": ["bad"]}, headers=alice).status_code
            == 400
        )


def test_invalid_playbook_rejected_at_save(tmp_path):
    from test_api import auth_headers, bootstrap_owner

    with TestClient(create_app(str(tmp_path / "validation.db"))) as client:
        headers = auth_headers(bootstrap_owner(client))
        bad = {"range_config": {"min_touches": 0}, "signal_config": {}, "risk_config": {}}
        response = client.post("/strategies", json={"name": "Bad", "payload": bad}, headers=headers)
        assert response.status_code == 400


def test_session_reads_and_writes_are_thread_safe(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    from api.dependencies import build_container

    container = build_container(str(tmp_path / "concurrent.db"))
    container.users.create_user("thread@example.test", "Long-password-123")
    user, token = container.users.authenticate("thread@example.test", "Long-password-123")

    def read_and_write(index):
        resolved = container.users.resolve_session(token)
        container.watchlists.create(resolved, f"List {index}")
        return container.users.resolve_session(token).id

    with ThreadPoolExecutor(max_workers=12) as pool:
        assert list(pool.map(read_and_write, range(60))) == [user.id] * 60
    container.store.close()


def test_ticker_cache_expires_and_is_symbol_scoped():
    from unittest.mock import Mock

    from exchange.models import Ticker
    from market_data.service import MarketDataService

    clock = [1000]
    port = Mock()
    port.get_ticker.side_effect = lambda symbol: Ticker(symbol=symbol, last=100)
    service = MarketDataService(port, cache_ttl_ms=100, clock_ms=lambda: clock[0])
    assert service.get_ticker("BTC/USD") == service.get_ticker("BTC/USD")
    service.get_ticker("ETH/USD")
    assert port.get_ticker.call_count == 2
    clock[0] += 101
    service.get_ticker("BTC/USD")
    assert port.get_ticker.call_count == 3
