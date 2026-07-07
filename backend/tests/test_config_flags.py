"""Tests for the deployment toggles: DB URL normalization, registration gate,
and the cron-triggered internal daily-sync endpoint."""
from __future__ import annotations

from app.config import Settings
from app.routers import auth as auth_router
from app.services import scheduler


def test_postgres_url_normalized_to_psycopg():
    s = Settings(database_url="postgres://user:pw@host/db")
    assert s.resolved_database_url == "postgresql+psycopg://user:pw@host/db"

    s = Settings(database_url="postgresql://user:pw@host/db")
    assert s.resolved_database_url == "postgresql+psycopg://user:pw@host/db"


def test_explicit_driver_url_passes_through():
    url = "postgresql+psycopg://user:pw@host/db"
    assert Settings(database_url=url).resolved_database_url == url


def test_sqlite_url_still_resolved_to_absolute(tmp_path):
    s = Settings(database_url=f"sqlite:///{tmp_path}/x.sqlite3")
    assert s.resolved_database_url == f"sqlite:///{tmp_path}/x.sqlite3"


def register_payload(email: str = "gate@example.com") -> dict:
    return {
        "email": email,
        "password": "password123",
        "profile": {"name": "Gate Tester", "personal_records": []},
    }


def test_registration_gate(client, monkeypatch):
    monkeypatch.setattr(auth_router.settings, "allow_registration", False)
    resp = client.post("/api/auth/register", json=register_payload())
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Registration is disabled."

    monkeypatch.setattr(auth_router.settings, "allow_registration", True)
    resp = client.post("/api/auth/register", json=register_payload())
    assert resp.status_code == 201


def test_daily_sync_disabled_without_secret(client, monkeypatch):
    monkeypatch.delenv("CRON_SECRET", raising=False)
    resp = client.get("/api/internal/daily-sync")
    assert resp.status_code == 503


def test_daily_sync_rejects_bad_bearer(client, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cret")
    resp = client.get("/api/internal/daily-sync")
    assert resp.status_code == 401
    resp = client.get(
        "/api/internal/daily-sync", headers={"Authorization": "Bearer wrong"}
    )
    assert resp.status_code == 401


def test_daily_sync_runs_with_correct_bearer(client, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cret")
    called = {}

    def fake_sync_all_users():
        called["yes"] = True

    monkeypatch.setattr(scheduler, "sync_all_users", fake_sync_all_users)
    resp = client.get(
        "/api/internal/daily-sync", headers={"Authorization": "Bearer s3cret"}
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    assert called.get("yes") is True
