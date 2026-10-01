"""Run the existing API contract against a real, disposable PostgreSQL server."""
import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from exchange.credentials import InMemoryCredentialStore
from persistence.migrate_cloud import migrate
from test_journal import test_private_journal_crud, test_all_admin_routes_reject_non_owner  # noqa: F401
from test_observed_ranges import test_saved_range_private_snapshot_and_review  # noqa: F401

# Reuse the contracts, including ownership and password/session behavior.
from test_api import (  # noqa: F401
    TestAuthEndpoints, TestExchangeConnectionEndpoints, TestAdminEndpoints,
    TestMarketAndBacktestEndpoints, TestTradesAndAuditEndpoints,
    TestWatchlistEndpoints, TestStrategyEndpoints,
    test_private_beta_blocks_public_signup_but_keeps_owner_login,
)


@pytest.fixture(scope="module")
def postgres_url(tmp_path_factory):
    pgserver = pytest.importorskip("pgserver")
    server = pgserver.get_server(tmp_path_factory.mktemp("grandblue-pg"), cleanup_mode="delete")
    yield server.get_uri()
    server.cleanup()


@pytest.fixture()
def clean_postgres(postgres_url):
    import psycopg
    # This URL is produced only by our disposable local server, never an env var.
    with psycopg.connect(postgres_url, autocommit=True) as connection:
        connection.execute("DROP SCHEMA IF EXISTS grandblue CASCADE")
    return postgres_url


@pytest.fixture()
def client(clean_postgres):
    with TestClient(create_app(clean_postgres, credential_store=InMemoryCredentialStore())) as client:
        yield client


def test_migration_preserves_private_notes_and_rejects_overwrite(tmp_path, clean_postgres):
    source = tmp_path / "source.db"
    with TestClient(create_app(str(source))) as client:
        response = client.post("/auth/register", json={"email": "owner@example.com", "password": "test-password"})
        headers = {"Authorization": "Bearer " + response.json()["access_token"]}
        note = client.post("/journal", headers=headers, json={
            "title": "Preserved idea", "body": "Support at the lower edge", "category": "idea",
            "symbol": "BTC/USDC:USDC", "timeframe": "4h",
        })
        assert note.status_code == 201, note.text
    counts = migrate(source, clean_postgres)
    assert counts["users"] == counts["journal_entries"] == 1
    with pytest.raises(RuntimeError, match="empty destination"):
        migrate(source, clean_postgres)
    with TestClient(create_app(clean_postgres)) as client:
        response = client.post("/auth/login", json={"email": "owner@example.com", "password": "test-password"})
        assert response.status_code == 200
        headers = {"Authorization": "Bearer " + response.json()["access_token"]}
        assert "Preserved idea" in client.get("/journal", headers=headers).text


def test_alert_dedup_and_state_survive_reconnection(client, clean_postgres):
    from app_layer.services.alerts import AlertService
    alerts = client.app.state.alerts
    assert alerts.record("alice", "edge:1", {"message": "touch"})
    assert alerts.record("alice", "edge:1", {"message": "touch"}) is None
    assert alerts.record("bob", "edge:1", {"message": "touch"})
    assert alerts.changed("alice", "range", "one")
    assert not alerts.changed("alice", "range", "one")
    alerts.mark_seen("alice")
    reopened = AlertService(clean_postgres)
    try:
        assert reopened.record("alice", "edge:1", {}) is None
        assert reopened.events("alice")[0]["seen"]
        assert not reopened.events("bob")[0]["seen"]
        assert reopened.changed("alice", "range", "two")
    finally:
        reopened.close()
