import sqlite3

import pytest

from api.production import create_production_app


def test_production_refuses_missing_database(tmp_path, monkeypatch):
    path = tmp_path / "missing.db"
    monkeypatch.setenv("RANGE_DB_PATH", str(path))
    with pytest.raises(RuntimeError, match="restored database"):
        create_production_app()
    assert not path.exists()


def test_production_refuses_database_without_owner(tmp_path, monkeypatch):
    path = tmp_path / "empty.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE users (role TEXT, active INTEGER)")
    monkeypatch.setenv("RANGE_DB_PATH", str(path))
    with pytest.raises(RuntimeError, match="active owner"):
        create_production_app()


def test_production_defaults_to_closed_signup(tmp_path, monkeypatch):
    from api.app import create_app
    from fastapi.testclient import TestClient

    path = tmp_path / "restored.db"
    # Track restoration even if this variable was initially absent.
    monkeypatch.setenv("GRANDBLUE_PRIVATE_BETA", "0")
    monkeypatch.delenv("GRANDBLUE_PRIVATE_BETA")
    monkeypatch.setenv("GRANDBLUE_ALLOWED_ORIGINS", "")
    with TestClient(create_app(str(path))) as client:
        assert client.post("/auth/register", json={
            "email": "owner@example.com", "password": "test-owner-password",
        }).status_code == 201
    monkeypatch.setenv("RANGE_DB_PATH", str(path))
    with TestClient(create_production_app()) as client:
        assert client.post("/auth/register", json={
            "email": "other@example.com", "password": "test-other-password",
        }).status_code == 403
        assert client.post("/auth/login", json={
            "email": "owner@example.com", "password": "test-owner-password",
        }).status_code == 200
