"""Shared seeding helpers for API tests."""

import math

from fastapi.testclient import TestClient

HOUR_MS = 3_600_000
BASE_TS = 1_700_000_000_000


def seed_sawtooth_dataset(client: TestClient, *, cycles: int = 10) -> None:
    from market_data.models import CandleDataset, MarketCandle, Timeframe

    container = client.app.state.container
    candles = []
    for index in range(24 * cycles):
        phase = (index % 24) / 24 * 2 * math.pi
        close = 100 + 5 * math.sin(phase)
        open_ = 100 + 5 * math.sin(phase - math.pi / 6)
        hi = max(open_, close) + 1.6
        lo = min(open_, close) - 1.6
        candles.append(MarketCandle(
            symbol="BTC/USDT", timeframe=Timeframe.H1,
            timestamp=BASE_TS + index * HOUR_MS,
            open=open_, high=hi, low=lo, close=close, volume=10.0,
        ))
    store = container.store
    store.ingest_dataset(
        CandleDataset(symbol="BTC/USDT", timeframe=Timeframe.H1,
                      candles=tuple(candles)),
        source="binance",
    )


def create_strategy(client: TestClient, token: str, name: str) -> str:
    response = client.post(
        "/strategies",
        json={
            "name": name,
            "payload": {
                "symbol": "BTC/USDT",
                "timeframe": "1h",
                "warmup_candles": 10,
                "range_config": {"mode": "manual", "params": {
                    "range_high": 106.0, "range_low": 94.0}},
                "signal_config": {"confirmation_policy": "ignored"},
                "risk_config": {"risk_per_trade": 0.01},
            },
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def run_backtest(client: TestClient, token: str, strategy_id: str) -> dict:
    response = client.post(
        "/backtests",
        json={
            "strategy_id": strategy_id,
            "start_ms": BASE_TS,
            "end_ms": BASE_TS + 240 * HOUR_MS,
            "initial_capital": 10_000.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


def seed_sawtooth_and_trade(client: TestClient, token: str) -> dict:
    """Persist candles, then run a backtest that produces real trades."""
    seed_sawtooth_dataset(client)
    strategy_id = create_strategy(client, token, "Owned strat")
    return run_backtest(client, token, strategy_id)
