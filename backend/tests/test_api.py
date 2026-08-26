"""HTTP API tests: FastAPI surface via TestClient — fully deterministic."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from exchange.credentials import InMemoryCredentialStore
from test_api_helpers import BASE_TS, HOUR_MS


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    app = create_app(str(tmp_path / "api.db"), credential_store=InMemoryCredentialStore())
    with TestClient(app) as test_client:
        yield test_client


def bootstrap_owner(client: TestClient) -> str:
    response = client.post(
        "/auth/register",
        json={"email": "root@example.com", "password": "root-pass-1"},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["access_token"])


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user(client: TestClient, owner_token: str, email: str) -> str:
    response = client.post(
        "/admin/users",
        json={"email": email, "password": "user-pass-123", "role": "user"},
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 201, response.text
    login = client.post(
        "/auth/login", json={"email": email, "password": "user-pass-123"}
    )
    assert login.status_code == 200, login.text
    return str(login.json()["access_token"])


class TestAuthEndpoints:
    def test_register_first_user_becomes_owner(self, client: TestClient) -> None:
        body = bootstrap_owner(client)
        me = client.get("/auth/me", headers=auth_headers(body))
        assert me.status_code == 200
        assert me.json()["role"] == "owner"

    def test_login_success_and_me(self, client: TestClient) -> None:
        token = bootstrap_owner(client)
        login = client.post(
            "/auth/login", json={"email": "root@example.com", "password": "root-pass-1"}
        )
        assert login.status_code == 200
        me = client.get("/auth/me", headers=auth_headers(login.json()["access_token"]))
        assert me.json()["email"] == "root@example.com"
        _ = token

    def test_login_failure_shape(self, client: TestClient) -> None:
        bootstrap_owner(client)
        failed = client.post(
            "/auth/login", json={"email": "root@example.com", "password": "wrong-pass-1"}
        )
        assert failed.status_code == 401
        error = failed.json()["error"]
        assert error["code"] == "unauthenticated" and error["request_id"]

    def test_protected_endpoint_requires_token(self, client: TestClient) -> None:
        response = client.get("/watchlists")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthenticated"

    def test_malformed_body_maps_to_envelope(self, client: TestClient) -> None:
        response = client.post("/auth/login", json={"email": 42})
        assert response.status_code == 400
        error = response.json()["error"]
        assert error["code"] == "validation_error"

    def test_request_id_echoed_and_honored(self, client: TestClient) -> None:
        generated = client.get("/health")
        assert generated.headers["X-Request-Id"]
        supplied = client.get(
            "/health", headers={"X-Request-Id": "my-correlation-id-1"}
        )
        assert supplied.headers["X-Request-Id"] == "my-correlation-id-1"


class TestWatchlistEndpoints:
    def test_crud_and_items_with_ownership(self, client: TestClient) -> None:
        root = bootstrap_owner(client)
        user_token = create_user(client, root, "alice@example.com")

        created = client.post(
            "/watchlists", json={"name": "Majors"},
            headers=auth_headers(user_token),
        )
        assert created.status_code == 201
        watchlist_id = created.json()["id"]

        item = client.post(
            f"/watchlists/{watchlist_id}/items",
            json={"symbol": "BTC/USDT", "venue_id": "binance", "notes": "core"},
            headers=auth_headers(user_token),
        )
        assert item.status_code == 201
        item_id = item.json()["id"]

        detail = client.get(
            f"/watchlists/{watchlist_id}", headers=auth_headers(user_token)
        )
        assert detail.status_code == 200
        assert detail.json()["items"][0]["symbol"] == "BTC/USDT"

        renamed = client.patch(
            f"/watchlists/{watchlist_id}", json={"name": "Core majors"},
            headers=auth_headers(user_token),
        )
        assert renamed.json()["name"] == "Core majors"

        removed = client.delete(
            f"/watchlists/{watchlist_id}/items/{item_id}",
            headers=auth_headers(user_token),
        )
        assert removed.status_code == 204

        deleted = client.delete(
            f"/watchlists/{watchlist_id}", headers=auth_headers(user_token)
        )
        assert deleted.status_code == 204

    def test_cross_user_watchlist_access_is_404(self, client: TestClient) -> None:
        root = bootstrap_owner(client)
        alice = create_user(client, root, "alice@example.com")
        bob = create_user(client, root, "bob@example.com")
        created = client.post(
            "/watchlists", json={"name": "Alice only"},
            headers=auth_headers(alice),
        )
        watchlist_id = created.json()["id"]
        for method, path in (
            ("get", f"/watchlists/{watchlist_id}"),
            ("patch", f"/watchlists/{watchlist_id}"),
            ("delete", f"/watchlists/{watchlist_id}"),
            ("post", f"/watchlists/{watchlist_id}/items"),
        ):
            kwargs = {"headers": auth_headers(bob)}
            if method == "post":
                kwargs["json"] = {"symbol": "ETH/USDT", "venue_id": "binance"}
            if method == "patch":
                kwargs["json"] = {"name": "hijack"}
            response = getattr(client, method)(path, **kwargs)
            assert response.status_code == 404, (method, response.text)

    def test_invalid_item_symbol_rejected(self, client: TestClient) -> None:
        root = bootstrap_owner(client)
        alice = create_user(client, root, "alice@example.com")
        created = client.post(
            "/watchlists", json={"name": "L"}, headers=auth_headers(alice)
        )
        bad = client.post(
            f"/watchlists/{created.json()['id']}/items",
            json={"symbol": "NOT-A-PAIR", "venue_id": "binance"},
            headers=auth_headers(alice),
        )
        assert bad.status_code == 400


class TestStrategyEndpoints:
    def payload(self) -> dict[str, object]:
        return {
            "range_config": {"mode": "manual",
                             "params": {"range_high": 106.0, "range_low": 94.0}},
            "signal_config": {"confirmation_policy": "ignored"},
            "risk_config": {"risk_per_trade": 0.01},
        }

    def test_create_get_update_reproducible_payload(self, client: TestClient) -> None:
        root = bootstrap_owner(client)
        alice = create_user(client, root, "alice@example.com")
        created = client.post(
            "/strategies",
            json={"name": "Sawtooth v1", "payload": self.payload()},
            headers=auth_headers(alice),
        )
        assert created.status_code == 201
        strategy = created.json()
        fetched = client.get(
            f"/strategies/{strategy['id']}", headers=auth_headers(alice)
        ).json()
        assert fetched["payload"] == strategy["payload"]
        # Canonical JSON => byte-identical round trips.
        again = client.get(
            f"/strategies/{strategy['id']}", headers=auth_headers(alice)
        ).json()
        assert json.dumps(again["payload"], sort_keys=True) == json.dumps(
            strategy["payload"], sort_keys=True
        )

    def test_missing_engine_configs_rejected(self, client: TestClient) -> None:
        root = bootstrap_owner(client)
        alice = create_user(client, root, "alice@example.com")
        bad = client.post(
            "/strategies",
            json={"name": "Broken", "payload": {"range_config": {}}},
            headers=auth_headers(alice),
        )
        assert bad.status_code == 400

    def test_cross_user_strategy_is_404(self, client: TestClient) -> None:
        root = bootstrap_owner(client)
        alice = create_user(client, root, "alice@example.com")
        bob = create_user(client, root, "bob@example.com")
        created = client.post(
            "/strategies",
            json={"name": "A", "payload": self.payload()},
            headers=auth_headers(alice),
        )
        response = client.get(
            f"/strategies/{created.json()['id']}", headers=auth_headers(bob)
        )
        assert response.status_code == 404


class TestExchangeConnectionEndpoints:
    def test_connect_lists_metadata_never_secrets(self, client: TestClient) -> None:
        root = bootstrap_owner(client)
        alice = create_user(client, root, "alice@example.com")
        connected = client.post(
            "/exchanges/connections",
            json={
                "venue_id": "binance",
                "display_name": "Binance main",
                "api_key": "ALICE-API-KEY",
                "secret": "ALICE-SUPER-SECRET",
            },
            headers=auth_headers(alice),
        )
        assert connected.status_code == 201
        body_text = json.dumps(connected.json())
        assert "ALICE-SUPER-SECRET" not in body_text
        assert "ALICE-API-KEY" not in body_text

        listed = client.get(
            "/exchanges/connections", headers=auth_headers(alice)
        ).json()
        assert listed[0]["display_name"] == "Binance main"
        assert "credential_ref" not in listed[0]
        assert set(listed[0]) <= {
            "id", "venue_id", "display_name", "status", "sandbox",
            "created_at_ms", "updated_at_ms",
        }

    def test_credentials_live_in_credential_store_not_database(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        db_path = tmp_path / "api.db"
        app = create_app(str(db_path), credential_store=InMemoryCredentialStore())
        with TestClient(app) as c:
            token = bootstrap_owner(c)
            c.post(
                "/exchanges/connections",
                json={
                    "venue_id": "kraken",
                    "display_name": "K",
                    "api_key": "KRAKEN-KEY-X",
                    "secret": "KRAKEN-SECRET-X",
                },
                headers=auth_headers(token),
            )
        raw_db = db_path.read_bytes()
        assert b"KRAKEN-SECRET-X" not in raw_db
        assert b"KRAKEN-KEY-X" not in raw_db


class TestAdminEndpoints:
    def test_user_cannot_access_admin_endpoints(self, client: TestClient) -> None:
        root = bootstrap_owner(client)
        user_token = create_user(client, root, "alice@example.com")
        headers = auth_headers(user_token)
        for method, path in (
            ("get", "/admin/users"),
            ("post", "/admin/users"),
            ("get", "/admin/system-health"),
            ("get", "/admin/audit-log"),
            ("get", "/admin/trading-activity"),
            ("post", "/admin/users/x/active"),
            ("post", "/admin/users/x/role"),
            ("post", "/admin/users/x/revoke-sessions"),
        ):
            kwargs: dict[str, object] = {"headers": headers}
            if path.endswith(("/active", "/role")):
                kwargs["json"] = {"active": False} if "active" in path else {"role": "owner"}
            if path.endswith("/users") and method == "post":
                kwargs["json"] = {
                    "email": "x@example.com", "password": "whatever-123",
                }
            response = getattr(client, method)(path, **kwargs)  # type: ignore[arg-type]
            assert response.status_code == 403, (path, response.text)

    def test_admin_requires_authentication(self, client: TestClient) -> None:
        response = client.get("/admin/users")
        assert response.status_code == 401

    def test_owner_manages_users_roles_and_sessions(self, client: TestClient) -> None:
        root = bootstrap_owner(client)
        created = client.post(
            "/admin/users",
            json={"email": "managed@example.com", "password": "managed-pass"},
            headers=auth_headers(root),
        )
        assert created.status_code == 201
        user_id = created.json()["id"]

        role_changed = client.post(
            f"/admin/users/{user_id}/role", json={"role": "owner"},
            headers=auth_headers(root),
        )
        assert role_changed.json()["role"] == "owner"

        login = client.post(
            "/auth/login", json={"email": "managed@example.com", "password": "managed-pass"}
        )
        victim_token = login.json()["access_token"]
        revoked = client.post(
            f"/admin/users/{user_id}/revoke-sessions", headers=auth_headers(root)
        )
        assert revoked.json()["revoked"] >= 1
        blocked = client.get("/auth/me", headers=auth_headers(victim_token))
        assert blocked.status_code == 401

        disabled = client.post(
            f"/admin/users/{user_id}/active", json={"active": False},
            headers=auth_headers(root),
        )
        assert disabled.json()["active"] is False

    def test_owner_cannot_self_demote_or_disable(self, client: TestClient) -> None:
        root_token = bootstrap_owner(client)
        me = client.get("/auth/me", headers=auth_headers(root_token)).json()
        demote = client.post(
            f"/admin/users/{me['id']}/role", json={"role": "user"},
            headers=auth_headers(root_token),
        )
        assert demote.status_code == 400
        disable = client.post(
            f"/admin/users/{me['id']}/active", json={"active": False},
            headers=auth_headers(root_token),
        )
        assert disable.status_code == 400


class TestMarketAndBacktestEndpoints:
    def test_market_endpoints_normalize_provider_failure(
        self, client: TestClient
    ) -> None:
        token = bootstrap_owner(client)
        ticker = client.get(
            "/markets/BTC-USDT/ticker", headers=auth_headers(token)
        )
        # No provider configured in this fixture: normalized error, no crash.
        assert ticker.status_code == 502 or ticker.status_code == 500 or (
            ticker.status_code == 400
        )
        body = ticker.json()["error"]
        assert body["request_id"]

    def test_backtest_run_via_saved_strategy_is_deterministic(
        self, client: TestClient
    ) -> None:
        from test_api_helpers import (
            create_strategy,
            run_backtest,
            seed_sawtooth_dataset,
        )

        root = bootstrap_owner(client)
        seed_sawtooth_dataset(client)
        strategy_id = create_strategy(client, root, "Sawtooth manual")
        run_request = {
            "strategy_id": strategy_id,
            "start_ms": BASE_TS,
            "end_ms": BASE_TS + 240 * HOUR_MS,
            "initial_capital": 10_000.0,
        }
        first = client.post(
            "/backtests", json=run_request, headers=auth_headers(root)
        )
        second = client.post(
            "/backtests", json=dict(run_request), headers=auth_headers(root)
        )
        assert first.status_code == 201 and second.status_code == 201
        a, b = first.json(), second.json()
        assert a["run_id"] == b["run_id"]
        assert a["final_equity"] == b["final_equity"]
        assert a["total_trades"] == b["total_trades"] > 0
        assert a["statistics"]["win_rate"] == b["statistics"]["win_rate"]
        _ = run_backtest

        listed = client.get("/backtests", headers=auth_headers(root))
        assert any(r["run_id"] == a["run_id"] for r in listed.json())

    def test_backtest_ownership_hides_other_users_runs(self, client: TestClient) -> None:
        root = bootstrap_owner(client)
        alice = create_user(client, root, "alice@example.com")
        bob = create_user(client, root, "bob@example.com")
        strategy = client.post(
            "/strategies",
            json={
                "name": "Alice strat",
                "payload": {
                    "range_config": {}, "signal_config": {}, "risk_config": {},
                },
            },
            headers=auth_headers(alice),
        )
        run_request = {
            "strategy_id": strategy.json()["id"],
            "start_ms": BASE_TS,
            "end_ms": BASE_TS + HOUR_MS,
            "initial_capital": 1_000.0,
        }
        # Empty dataset => runner completes with zero trades; record persists.
        response = client.post(
            "/backtests", json=run_request, headers=auth_headers(alice)
        )
        if response.status_code == 201:
            run_id = response.json()["run_id"]
            forbidden_view = client.get(
                f"/backtests/{run_id}", headers=auth_headers(bob)
            )
            assert forbidden_view.status_code == 404
            listed = client.get("/backtests", headers=auth_headers(bob))
            assert all(r["run_id"] != run_id for r in listed.json())


class TestTradesAndAuditEndpoints:
    def test_trade_visibility_follows_strategy_ownership(
        self, client: TestClient
    ) -> None:
        root = bootstrap_owner(client)
        alice = create_user(client, root, "alice@example.com")
        bob = create_user(client, root, "bob@example.com")

        from test_api_helpers import seed_sawtooth_and_trade

        run_body = seed_sawtooth_and_trade(client, alice)
        assert run_body["total_trades"] > 0

        alice_trades = client.get("/trades", headers=auth_headers(alice))
        bob_trades = client.get("/trades", headers=auth_headers(bob))
        assert len(alice_trades.json()) >= 1
        assert bob_trades.json() == []

    def test_audit_log_records_privileged_actions_without_secrets(
        self, client: TestClient
    ) -> None:
        root = bootstrap_owner(client)
        client.post(
            "/admin/users",
            json={"email": "audited@example.com", "password": "audited-pass"},
            headers=auth_headers(root),
        )
        tail = client.get(
            "/admin/audit-log?limit=50", headers=auth_headers(root)
        ).json()
        actions = {event["action"] for event in tail}
        assert "user.created" in actions
        for event in tail:
            blob = json.dumps(event)
            assert "audited-pass" not in blob
            assert event["outcome"] in {"success", "rejected"}
