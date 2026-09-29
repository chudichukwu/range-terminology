"""Dataset coverage endpoint — authoritative facts only."""

from pathlib import Path

from fastapi.testclient import TestClient

from api.app import create_app
from exchange.credentials import InMemoryCredentialStore


def _client(tmp_path: Path) -> TestClient:
    app = create_app(str(tmp_path / "ds.db"), credential_store=InMemoryCredentialStore())
    return TestClient(app)


def test_datasets_requires_auth(tmp_path: Path) -> None:
    c = _client(tmp_path)
    r = c.get("/datasets")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthenticated"


def test_datasets_empty_for_new_user(tmp_path: Path) -> None:
    c = _client(tmp_path)
    r = c.post("/auth/register", json={"email": "owner@example.com", "password": "secret123"})
    assert r.status_code == 201
    tok = r.json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    r = c.get("/datasets", headers=h)
    assert r.status_code == 200
    assert r.json() == []


def test_datasets_returns_persisted_summary(tmp_path: Path) -> None:
    c = _client(tmp_path)
    r = c.post("/auth/register", json={"email": "owner2@example.com", "password": "secret123"})
    tok = r.json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    # Initially empty
    assert c.get("/datasets", headers=h).json() == []
    # Ingest is via candle repository directly — simulate via internal store
    # Use app container to ingest a dataset, then verify it appears
    from market_data.models import CandleDataset, DataQualityReport, MarketCandle, Timeframe

    # Retrieve app to get store
    # Create a minimal dataset and ingest via store
    app = c.app  # type: ignore[attr-defined]
    container = app.state.container  # type: ignore[attr-defined]
    dataset = CandleDataset(
        symbol="BTC/USDT",
        timeframe=Timeframe.H1,
        candles=(
            MarketCandle(
                symbol="BTC/USDT",
                timeframe=Timeframe.H1,
                timestamp=1_000_000,
                open=100,
                high=110,
                low=90,
                close=105,
                volume=10,
                is_closed=True,
            ),
            MarketCandle(
                symbol="BTC/USDT",
                timeframe=Timeframe.H1,
                timestamp=1_003_600_000,
                open=105,
                high=115,
                low=95,
                close=110,
                volume=12,
                is_closed=True,
            ),
        ),
        quality=DataQualityReport(),
        retrieved_at_ms=2_000_000,
    )
    container.store.ingest_dataset(dataset, source="binance")
    r = c.get("/datasets", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    row = body[0]
    assert row["symbol"] == "BTC/USDT"
    assert row["timeframe"] == "1h"
    assert row["source"] == "binance"
    assert row["candle_count"] == 2
    assert row["quality_status"] in ("clean", "warnings")
    assert row["first_timestamp_ms"] == 1_000_000
    assert row["last_timestamp_ms"] == 1_003_600_000
    # issues is sanitized list, empty for clean dataset
    assert isinstance(row["issues"], list)
    assert row["issues"] == []


def test_datasets_warning_with_gap_timestamps(tmp_path: Path) -> None:
    c = _client(tmp_path)
    r = c.post("/auth/register", json={"email": "owner3@example.com", "password": "secret123"})
    tok = r.json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    from market_data.models import (
        CandleDataset,
        DataQualityReport,
        MarketCandle,
        QualityIssue,
        Timeframe,
    )

    app = c.app  # type: ignore[attr-defined]
    container = app.state.container  # type: ignore[attr-defined]
    report = DataQualityReport(
        issues=(
            QualityIssue(
                kind="gap",
                detail="missing candles",
                gap_start_ms=2_000_000,
                gap_end_ms=3_600_000,
            ),
        )
    )
    dataset = CandleDataset(
        symbol="ETH/USDT",
        timeframe=Timeframe.H1,
        candles=(
            MarketCandle(
                symbol="ETH/USDT",
                timeframe=Timeframe.H1,
                timestamp=10_000_000,
                open=200,
                high=210,
                low=190,
                close=205,
                volume=5,
                is_closed=True,
            ),
        ),
        quality=report,
        retrieved_at_ms=20_000_000,
    )
    container.store.ingest_dataset(dataset, source="kraken")
    r = c.get("/datasets", headers=h)
    assert r.status_code == 200
    body = r.json()
    row = next(x for x in body if x["symbol"] == "ETH/USDT")
    assert row["quality_status"] == "warnings"
    assert len(row["issues"]) == 1
    iss = row["issues"][0]
    assert iss["kind"] == "gap"
    assert iss["detail"] == "missing candles"
    assert iss["gap_start_ms"] == 2_000_000
    assert iss["gap_end_ms"] == 3_600_000
    # index may be null
    assert "index" in iss


def test_datasets_missing_diagnostics_remain_valid(tmp_path: Path) -> None:
    # A clean ingest without issues must not cause failure and returns empty issues
    c = _client(tmp_path)
    r = c.post("/auth/register", json={"email": "owner4@example.com", "password": "secret123"})
    tok = r.json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    from market_data.models import CandleDataset, DataQualityReport, MarketCandle, Timeframe

    app = c.app  # type: ignore[attr-defined]
    container = app.state.container  # type: ignore[attr-defined]
    dataset = CandleDataset(
        symbol="SOL/USDT",
        timeframe=Timeframe.D1,
        candles=(
            MarketCandle(
                symbol="SOL/USDT",
                timeframe=Timeframe.D1,
                timestamp=100_000,
                open=10,
                high=12,
                low=9,
                close=11,
                volume=100,
                is_closed=True,
            ),
        ),
        quality=DataQualityReport(issues=()),
        retrieved_at_ms=200_000,
    )
    container.store.ingest_dataset(dataset, source="binance")
    r = c.get("/datasets", headers=h)
    assert r.status_code == 200
    row = next(x for x in r.json() if x["symbol"] == "SOL/USDT")
    assert row["issues"] == []
    assert row["quality_status"] == "clean"


def test_datasets_non_owner_can_read_global(tmp_path: Path) -> None:
    c = _client(tmp_path)
    # owner creates dataset
    r = c.post("/auth/register", json={"email": "owner5@example.com", "password": "secret123"})
    tok_owner = r.json()["access_token"]
    h_owner = {"Authorization": f"Bearer {tok_owner}"}
    from market_data.models import CandleDataset, DataQualityReport, MarketCandle, Timeframe

    app = c.app  # type: ignore[attr-defined]
    container = app.state.container  # type: ignore[attr-defined]
    dataset = CandleDataset(
        symbol="AVAX/USDT",
        timeframe=Timeframe.H1,
        candles=(
            MarketCandle(
                symbol="AVAX/USDT",
                timeframe=Timeframe.H1,
                timestamp=5_000_000,
                open=20,
                high=22,
                low=19,
                close=21,
                volume=50,
                is_closed=True,
            ),
        ),
        quality=DataQualityReport(),
        retrieved_at_ms=6_000_000,
    )
    container.store.ingest_dataset(dataset, source="binance")
    # create non-owner user via owner
    r = c.post(
        "/admin/users",
        json={"email": "user@example.com", "password": "secret123", "role": "user"},
        headers=h_owner,
    )
    assert r.status_code == 201
    r = c.post("/auth/login", json={"email": "user@example.com", "password": "secret123"})
    tok_user = r.json()["access_token"]
    h_user = {"Authorization": f"Bearer {tok_user}"}
    r = c.get("/datasets", headers=h_user)
    assert r.status_code == 200
    symbols = [x["symbol"] for x in r.json()]
    assert "AVAX/USDT" in symbols
