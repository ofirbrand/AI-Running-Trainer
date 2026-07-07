"""Tests for the Garmin DB token store (GARMIN_TOKEN_STORE=db)."""
from __future__ import annotations

import json
from pathlib import Path

from app.models import GarminConnection, User
from app.services import garmin_service

# Realistic-shaped blob, long enough (>512 chars) that garminconnect's
# login() treats it as token data rather than a path.
FAKE_BLOB = json.dumps(
    {
        "di_token": "t" * 400,
        "di_refresh_token": "r" * 400,
        "di_client_id": "client-id",
    }
)


class FakeInner:
    def __init__(self, blob: str):
        self._blob = blob

    def dumps(self) -> str:
        return self._blob


class FakeGarmin:
    """Mimics garminconnect.Garmin's token surface (client.dumps, no garth)."""

    def __init__(self, blob: str):
        self.garth = None
        self.client = FakeInner(blob)


def make_user(db) -> User:
    user = User(email="runner@example.com", password_hash="hash")
    db.add(user)
    db.commit()
    return user


def test_store_tokens_db_mode_creates_row(db_session_factory, monkeypatch):
    monkeypatch.setattr(garmin_service.settings, "garmin_token_store", "db")
    db = db_session_factory()
    user = make_user(db)

    garmin_service._store_tokens(db, user.id, "g@example.com", FakeGarmin(FAKE_BLOB))

    conn = db.query(GarminConnection).filter_by(user_id=user.id).one()
    assert conn.token_data == FAKE_BLOB
    assert conn.token_dir == "db"
    assert conn.garmin_email == "g@example.com"


def test_token_source_prefers_blob_in_db_mode(db_session_factory, monkeypatch):
    conn = GarminConnection(user_id=1, garmin_email="g@e.com", token_dir="/tmp/x", token_data=FAKE_BLOB)

    monkeypatch.setattr(garmin_service.settings, "garmin_token_store", "db")
    assert garmin_service._token_source(conn) == FAKE_BLOB

    monkeypatch.setattr(garmin_service.settings, "garmin_token_store", "file")
    assert garmin_service._token_source(conn) == Path("/tmp/x")


def test_token_source_falls_back_to_dir_without_blob(monkeypatch):
    monkeypatch.setattr(garmin_service.settings, "garmin_token_store", "db")
    conn = GarminConnection(user_id=1, garmin_email="g@e.com", token_dir="/tmp/x", token_data=None)
    assert garmin_service._token_source(conn) == Path("/tmp/x")


def test_repersist_if_changed(db_session_factory, monkeypatch):
    monkeypatch.setattr(garmin_service.settings, "garmin_token_store", "db")
    db = db_session_factory()
    user = make_user(db)
    conn = GarminConnection(
        user_id=user.id, garmin_email="g@e.com", token_dir="db", token_data=FAKE_BLOB
    )
    db.add(conn)
    db.commit()

    # Same blob: no write.
    garmin_service._repersist_if_changed(db, conn, FakeGarmin(FAKE_BLOB))
    db.refresh(conn)
    assert conn.token_data == FAKE_BLOB

    # Refreshed tokens: persisted back to the row.
    new_blob = FAKE_BLOB.replace("client-id", "client-id-2")
    garmin_service._repersist_if_changed(db, conn, FakeGarmin(new_blob))
    db.refresh(conn)
    assert conn.token_data == new_blob


def test_repersist_noop_in_file_mode(db_session_factory, monkeypatch):
    monkeypatch.setattr(garmin_service.settings, "garmin_token_store", "file")
    db = db_session_factory()
    user = make_user(db)
    conn = GarminConnection(
        user_id=user.id, garmin_email="g@e.com", token_dir="/tmp/x", token_data=FAKE_BLOB
    )
    db.add(conn)
    db.commit()

    garmin_service._repersist_if_changed(db, conn, FakeGarmin("something else " * 50))
    db.refresh(conn)
    assert conn.token_data == FAKE_BLOB


def test_dump_blob_probes_client_dumps():
    assert garmin_service._dump_blob(FakeGarmin(FAKE_BLOB)) == FAKE_BLOB
