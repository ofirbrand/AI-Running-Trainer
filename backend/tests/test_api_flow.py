"""End-to-end API tests with AI + Garmin mocked."""
from datetime import date, datetime, timedelta

from app.models import Activity, User
from app.services.week import week_start
from tests.conftest import auth_headers


def _future_date(days: int = 56) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def test_register_login_me(client):
    headers = auth_headers(client)
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "runner@example.com"


def test_duplicate_email_rejected(client):
    auth_headers(client, "dup@example.com")
    resp = client.post(
        "/api/auth/register",
        json={"email": "dup@example.com", "password": "password123", "profile": {}},
    )
    assert resp.status_code == 409


def test_requires_auth(client):
    assert client.get("/api/plans").status_code == 401


def test_profile_update(client):
    headers = auth_headers(client)
    resp = client.put(
        "/api/profile",
        headers=headers,
        json={"name": "New Name", "weight_kg": 70, "personal_records": [{"distance": "5K", "time": "20:00"}]},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"
    assert resp.json()["personal_records"][0]["distance"] == "5K"


def test_metric_upsert_and_prefill(client):
    headers = auth_headers(client)
    client.put(
        "/api/garmin/metrics",
        headers=headers,
        json={"key": "vo2max", "value": 52, "unit": "ml/kg/min"},
    )
    pre = client.get("/api/plans/prefill", headers=headers)
    assert pre.status_code == 200
    assert pre.json()["prefill"]["vo2max"]["value"] == 52


def test_settings_roundtrip(client):
    headers = auth_headers(client)
    resp = client.put(
        "/api/settings",
        headers=headers,
        json={"ai_model": "claude-opus-4-5", "reasoning_effort": "high"},
    )
    assert resp.status_code == 200
    got = client.get("/api/settings", headers=headers)
    assert got.json()["ai_model"] == "claude-opus-4-5"
    assert got.json()["reasoning_effort"] == "high"


def test_create_plan_requires_ai(client, monkeypatch):
    from app.services import agent_service

    monkeypatch.setattr(agent_service, "is_available", lambda: False)
    headers = auth_headers(client)
    resp = client.post(
        "/api/plans",
        headers=headers,
        json={"distance_label": "10K", "target_date": _future_date(), "days_available": ["Sunday"]},
    )
    assert resp.status_code == 503  # AI not configured (not mocked here)


def test_full_plan_lifecycle(client, mock_agent, db_session_factory):
    headers = auth_headers(client)

    # Create (generate draft).
    resp = client.post(
        "/api/plans",
        headers=headers,
        json={
            "distance_label": "10K",
            "target_date": _future_date(),
            "goal_type": "time",
            "goal_value": "45:00",
            "days_available": ["Sunday", "Tuesday", "Thursday"],
        },
    )
    assert resp.status_code == 201, resp.text
    plan = resp.json()
    plan_id = plan["id"]
    assert plan["status"] == "draft"
    assert len(plan["versions"]) == 1
    draft_version = plan["versions"][0]
    assert draft_version["status"] == "draft"
    assert len(draft_version["planned_workouts"]) == 3  # 2 in week 1 + 1 in week 2

    # Tracking before approval should fail.
    assert client.get(f"/api/plans/{plan_id}/tracking", headers=headers).status_code == 400

    # Approve.
    approve = client.post(
        f"/api/plans/{plan_id}/versions/{draft_version['id']}/approve", headers=headers
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "active"
    assert approve.json()["active_version_id"] == draft_version["id"]

    # Tracking now works.
    track = client.get(f"/api/plans/{plan_id}/tracking", headers=headers)
    assert track.status_code == 200
    body = track.json()
    assert body["num_weeks"] >= 2
    assert len(body["days"]) == 7

    # Manual update produces a proposed version.
    upd = client.post(
        f"/api/plans/{plan_id}/manual-update",
        headers=headers,
        json={"request_text": "Move long runs to Saturday."},
    )
    assert upd.status_code == 200
    assert upd.json()["update_recommended"] is True
    proposed_id = upd.json()["proposed_version_id"]
    assert proposed_id is not None

    # Approve the proposed update -> it becomes active.
    approve2 = client.post(
        f"/api/plans/{plan_id}/versions/{proposed_id}/approve", headers=headers
    )
    assert approve2.status_code == 200
    assert approve2.json()["active_version_id"] == proposed_id

    # Restore the original version.
    restore = client.post(
        f"/api/plans/{plan_id}/versions/{draft_version['id']}/restore", headers=headers
    )
    assert restore.status_code == 200
    assert restore.json()["active_version_id"] != draft_version["id"]  # a clone is activated
    assert restore.json()["status"] == "active"


def test_weekly_update_no_change(client, mock_agent):
    headers = auth_headers(client)
    resp = client.post(
        "/api/plans",
        headers=headers,
        json={"distance_label": "5K", "target_date": _future_date(), "days_available": ["Sunday"]},
    )
    plan = resp.json()
    version_id = plan["versions"][0]["id"]
    client.post(f"/api/plans/{plan['id']}/versions/{version_id}/approve", headers=headers)

    # FAKE_PLAN has change_summary=None -> treated as "no change".
    weekly = client.post(f"/api/plans/{plan['id']}/weekly-update", headers=headers)
    assert weekly.status_code == 200
    assert weekly.json()["update_recommended"] is False


def test_chat_then_confirm_changes(client, mock_agent):
    headers = auth_headers(client)
    resp = client.post(
        "/api/plans",
        headers=headers,
        json={"distance_label": "10K", "target_date": _future_date(), "days_available": ["Sunday"]},
    )
    plan_id = resp.json()["id"]

    chat = client.post(
        f"/api/plans/{plan_id}/chat",
        headers=headers,
        json={"messages": [{"role": "user", "content": "Make Mondays a rest day."}]},
    )
    assert chat.status_code == 200
    assert chat.json()["role"] == "assistant"

    confirm = client.post(
        f"/api/plans/{plan_id}/confirm-changes",
        headers=headers,
        json={"requests": ["Make Mondays a rest day."]},
    )
    assert confirm.status_code == 200
    assert confirm.json()["proposed_version_id"] is not None


def test_sync_without_connection_fails(client):
    headers = auth_headers(client)
    assert client.post("/api/garmin/sync", headers=headers).status_code == 400


def test_list_activities_empty(client):
    headers = auth_headers(client)
    resp = client.get("/api/garmin/activities", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_activities_returns_newest_first(client, db_session_factory):
    headers = auth_headers(client)
    db = db_session_factory()
    user = db.query(User).first()
    db.add_all(
        [
            Activity(
                user_id=user.id,
                garmin_activity_id="a-old",
                activity_date=date.today() - timedelta(days=5),
                start_time=datetime.now() - timedelta(days=5),
                activity_type="running",
                name="Old run",
                distance_m=5000,
                duration_s=1500,
            ),
            Activity(
                user_id=user.id,
                garmin_activity_id="a-new",
                activity_date=date.today(),
                start_time=datetime.now(),
                activity_type="cycling",
                name="New ride",
                distance_m=20000,
                duration_s=3600,
            ),
        ]
    )
    db.commit()
    db.close()

    resp = client.get("/api/garmin/activities", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert [a["name"] for a in body] == ["New ride", "Old run"]

    latest = client.get("/api/garmin/activities", headers=headers, params={"limit": 1})
    assert len(latest.json()) == 1
    assert latest.json()[0]["name"] == "New ride"


def test_fetch_activities_without_connection_fails(client):
    headers = auth_headers(client)
    resp = client.post(
        "/api/garmin/activities/fetch",
        headers=headers,
        json={"start": date.today().isoformat(), "end": date.today().isoformat()},
    )
    assert resp.status_code == 400


def test_activity_detail(client, db_session_factory):
    headers = auth_headers(client)
    db = db_session_factory()
    user = db.query(User).first()
    act = Activity(
        user_id=user.id,
        garmin_activity_id="detail-1",
        activity_date=date.today(),
        start_time=datetime.now(),
        activity_type="running",
        name="Morning run",
        distance_m=8000,
        duration_s=2400,
        avg_hr=150,
        max_hr=172,
        calories=540,
        raw={"elevationGain": 42, "locationName": "Tel Aviv"},
    )
    db.add(act)
    db.commit()
    activity_id = act.id
    db.close()

    resp = client.get(f"/api/garmin/activities/{activity_id}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Morning run"
    assert body["max_hr"] == 172
    assert body["calories"] == 540
    assert body["raw"]["elevationGain"] == 42

    # Missing activity -> 404.
    assert client.get("/api/garmin/activities/999999", headers=headers).status_code == 404

    # Another user cannot read it -> 404.
    other = auth_headers(client, "other@example.com")
    assert client.get(f"/api/garmin/activities/{activity_id}", headers=other).status_code == 404
