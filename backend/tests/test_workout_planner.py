"""Ad-hoc workout planner: transient SSE generation + Garmin data loading."""
from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.models import (
    Activity,
    DailyHealth,
    GarminConnection,
    MetricObservation,
    PlanChangeRequest,
    PlannedWorkout,
    PlanVersion,
    TrainingPlan,
    User,
)
from app.routers.workout_planner import _anchor_today, _compute_start_date
from app.schemas import WorkoutPlanRequest
from app.services.week import israeli_weekday, week_start

from tests.conftest import auth_headers


def _fake_workout_plan(weekday: int) -> dict:
    return {
        "structure_explanation": "One quality session that fits your week.",
        "full_explanation": "Anchored on your recent easy pace.",
        "change_summary": None,
        "workout_types": [
            {"name": "Tempo", "description": "Comfortably hard, ~1-hour effort."}
        ],
        "weeks": [
            {
                "week_no": 1,
                "focus": "quality",
                "workouts": [
                    {
                        "weekday": weekday,
                        "workout_type": "Tempo",
                        "goal": "6 km @ threshold",
                        "how_to": "2 km warm-up, 6 km tempo, 1 km cool-down.",
                        "details": {"distance_km": 9},
                    }
                ],
            }
        ],
    }


@pytest.fixture
def mock_workout_stream(monkeypatch):
    """Scripted agent stream that also captures the (model, effort) it was given."""
    from app.services import agent_service

    captured: dict = {}

    def install(plan: dict):
        async def fake_stream_agent(system, user, model, effort):
            captured.update(system=system, user=user, model=model, effort=effort)
            yield {"type": "thinking", "delta": "Checking your recent load…"}
            yield {"type": "text", "delta": "Here you go."}
            yield {"type": "step", "label": "Submitting the finished plan…"}
            yield {"type": "plan", "plan": plan}

        monkeypatch.setattr(agent_service, "_stream_agent", fake_stream_agent)
        monkeypatch.setattr(agent_service, "is_available", lambda: True)
        return captured

    return install


def _parse_sse(text: str) -> list[dict]:
    events: list[dict] = []
    for block in text.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:].strip()))
    return events


def _single_body(**overrides) -> dict:
    body = {
        "mode": "single",
        "day_preference": "today",
        "duration": "45",
        "workout_type": "easy",
        "use_garmin": False,
        "description": "Legs feel fresh, want something fun.",
        "client_today": date.today().isoformat(),
    }
    body.update(overrides)
    return body


def _week_body(**overrides) -> dict:
    body = {
        "mode": "week",
        "sessions_per_week": "4",
        "session_duration": "45-60",
        "week_choice": "next_week",
        "use_garmin": False,
        "description": "Building toward a 10K next month.",
        "client_today": date.today().isoformat(),
    }
    body.update(overrides)
    return body


# --------------------------------------------------------------------------- #
# Generation stream
# --------------------------------------------------------------------------- #


def test_generate_single_stream_shape(client, mock_workout_stream):
    today = date.today()
    mock_workout_stream(_fake_workout_plan(israeli_weekday(today)))
    headers = auth_headers(client)

    resp = client.post("/api/workout-planner/generate", headers=headers, json=_single_body())
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(resp.text)
    types = [e["type"] for e in events]
    assert types[0] == "prompt"
    assert {"thinking", "text", "step"} <= set(types)
    assert types[-1] == "done"

    done = events[-1]
    assert "plan_id" not in done  # transient: nothing to navigate to or store
    version = done["workout_plan"]["version"]
    assert version["status"] == "transient"
    assert version["source"] == "workout_planner"
    assert version["num_weeks"] == 1
    assert version["id"] == 0 and version["plan_id"] == 0

    workouts = version["planned_workouts"]
    assert len(workouts) == 1
    assert workouts[0]["id"] == 1  # synthetic React key
    assert workouts[0]["date"] == today.isoformat()  # "today" preference lands today

    prompt = events[0]
    assert "AD-HOC" in prompt["system"]
    assert "single running workout" in prompt["user"]
    assert "Legs feel fresh" in prompt["user"]


def test_generate_persists_nothing(client, mock_workout_stream, db_session_factory):
    mock_workout_stream(_fake_workout_plan(2))
    headers = auth_headers(client)

    resp = client.post("/api/workout-planner/generate", headers=headers, json=_single_body())
    assert resp.status_code == 200
    assert _parse_sse(resp.text)[-1]["type"] == "done"

    assert client.get("/api/plans", headers=headers).json() == []
    db = db_session_factory()
    try:
        for table in (TrainingPlan, PlanVersion, PlannedWorkout, MetricObservation, PlanChangeRequest):
            count = db.scalar(select(func.count()).select_from(table))
            assert count == 0, f"{table.__tablename__} has {count} rows"
    finally:
        db.close()


def test_generate_week_next_week_dates(client, mock_workout_stream):
    mock_workout_stream(_fake_workout_plan(3))
    headers = auth_headers(client)

    resp = client.post("/api/workout-planner/generate", headers=headers, json=_week_body())
    assert resp.status_code == 200
    version = _parse_sse(resp.text)[-1]["workout_plan"]["version"]
    next_sunday = week_start(date.today()) + timedelta(days=7)
    assert version["start_date"] == next_sunday.isoformat()
    first = date.fromisoformat(version["planned_workouts"][0]["date"])
    assert first >= next_sunday


def test_generate_model_effort_override(client, mock_workout_stream):
    captured = mock_workout_stream(_fake_workout_plan(1))
    headers = auth_headers(client)

    body = _single_body(ai_model="claude-opus-4-8", reasoning_effort="max")
    resp = client.post("/api/workout-planner/generate", headers=headers, json=body)
    assert resp.status_code == 200
    assert captured["model"] == "claude-opus-4-8"
    assert captured["effort"] == "max"

    resp = client.post("/api/workout-planner/generate", headers=headers, json=_single_body())
    assert resp.status_code == 200
    assert captured["model"] == get_settings().default_ai_model
    assert captured["effort"] == get_settings().default_reasoning_effort


def test_generate_validation(client, mock_workout_stream):
    mock_workout_stream(_fake_workout_plan(1))
    headers = auth_headers(client)
    post = lambda body: client.post(  # noqa: E731
        "/api/workout-planner/generate", headers=headers, json=body
    )

    assert post(_single_body(description="   ")).status_code == 422
    assert post(_single_body(workout_type=None)).status_code == 422
    assert post(_week_body(week_choice=None)).status_code == 422
    assert post(_single_body(use_garmin=True)).status_code == 422  # no range given
    assert post(_single_body(ai_model="gpt-4o")).status_code == 422
    assert post(_single_body(reasoning_effort="ultra")).status_code == 422


# --------------------------------------------------------------------------- #
# Date helpers
# --------------------------------------------------------------------------- #


def test_anchor_today_clamps_to_server_date():
    server = date.today()
    assert _anchor_today(None) == server
    assert _anchor_today(server + timedelta(days=1)) == server + timedelta(days=1)
    assert _anchor_today(server - timedelta(days=10)) == server


def test_compute_start_date_saturday_rollover():
    saturday = week_start(date.today()) + timedelta(days=6)
    payload = WorkoutPlanRequest.model_validate(
        _single_body(day_preference="tomorrow", client_today=saturday.isoformat())
    )
    # Tomorrow is Sunday: the workout belongs to the NEXT Israeli week.
    assert _compute_start_date(payload, saturday) == saturday + timedelta(days=1)

    payload = WorkoutPlanRequest.model_validate(
        _week_body(week_choice="this_week", client_today=saturday.isoformat())
    )
    assert _compute_start_date(payload, saturday) == week_start(saturday)


# --------------------------------------------------------------------------- #
# Garmin data endpoint
# --------------------------------------------------------------------------- #


def _connect_garmin_and_seed(db_session_factory, email: str) -> None:
    db = db_session_factory()
    try:
        user = db.scalar(select(User).where(User.email == email))
        db.add(
            GarminConnection(
                user_id=user.id, garmin_email=email, token_dir="db", status="connected"
            )
        )
        today = date.today()
        for i in range(3):
            db.add(
                Activity(
                    user_id=user.id,
                    garmin_activity_id=f"a-{i}",
                    activity_date=today - timedelta(days=i),
                    activity_type="running",
                    distance_m=5000,
                    duration_s=1800,
                )
            )
        for i in range(5):
            db.add(
                DailyHealth(
                    user_id=user.id,
                    date=today - timedelta(days=i),
                    steps=8000,
                    resting_hr=50,
                    sleep_seconds=7 * 3600,
                )
            )
        db.commit()
    finally:
        db.close()


def test_garmin_data_counts(client, db_session_factory, monkeypatch):
    from app.services import garmin_service

    email = "garmin@example.com"
    headers = auth_headers(client, email=email)
    _connect_garmin_and_seed(db_session_factory, email)
    monkeypatch.setattr(
        garmin_service, "fetch_activities_window", lambda db, user, start, end: 3
    )

    start = (date.today() - timedelta(days=7)).isoformat()
    end = date.today().isoformat()
    resp = client.post(
        "/api/workout-planner/garmin-data",
        headers=headers,
        json={"start": start, "end": end},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["activities_count"] == 3
    assert body["health_days"] == 5
    assert body["start"] == start and body["end"] == end


def test_garmin_data_requires_connection(client):
    headers = auth_headers(client)
    resp = client.post(
        "/api/workout-planner/garmin-data",
        headers=headers,
        json={"start": date.today().isoformat(), "end": date.today().isoformat()},
    )
    assert resp.status_code == 400


def test_garmin_data_auth_error_is_409_not_401(client, db_session_factory, monkeypatch):
    """An expired Garmin session must NOT surface as 401 — the frontend's axios
    interceptor logs the user out of the app on any 401."""
    from app.services import garmin_service

    email = "expired@example.com"
    headers = auth_headers(client, email=email)
    _connect_garmin_and_seed(db_session_factory, email)

    def boom(db, user, start, end):
        raise garmin_service.GarminAuthError("Garmin session expired; please reconnect.")

    monkeypatch.setattr(garmin_service, "fetch_activities_window", boom)
    resp = client.post(
        "/api/workout-planner/garmin-data",
        headers=headers,
        json={"start": date.today().isoformat(), "end": date.today().isoformat()},
    )
    assert resp.status_code == 409
    assert "expired" in resp.json()["detail"].lower()


def test_garmin_data_range_validation(client, db_session_factory):
    email = "range@example.com"
    headers = auth_headers(client, email=email)
    _connect_garmin_and_seed(db_session_factory, email)
    today = date.today()

    post = lambda start, end: client.post(  # noqa: E731
        "/api/workout-planner/garmin-data",
        headers=headers,
        json={"start": start.isoformat(), "end": end.isoformat()},
    )
    assert post(today, today - timedelta(days=1)).status_code == 422  # end < start
    assert post(today + timedelta(days=2), today + timedelta(days=3)).status_code == 422
    assert post(today - timedelta(days=400), today).status_code == 422  # too large


# --------------------------------------------------------------------------- #
# Prompt builder
# --------------------------------------------------------------------------- #


def test_build_workout_prompt_sections():
    from app.agent.prompts import build_workout_prompt

    context = {
        "profile": {"name": "Dana"},
        "metrics": {"vo2max": {"value": 50}},
        "activities": [],
        "daily_health": {"days_with_data": 4, "averages": {}, "recent_days": []},
        "request": {"mode": "week", "sessions_per_week": "4"},
        "description": "Feeling strong lately.",
        "calendar": {"today": "2026-08-18", "note": "Plan NEXT week"},
    }
    prompt = build_workout_prompt(context)
    assert "one week of running training" in prompt
    assert "No activities were found" in prompt
    assert "Daily health in the selected range" in prompt
    assert "Feeling strong lately." in prompt
    assert "sessions_per_week" in prompt
    assert "Plan NEXT week" in prompt

    single = build_workout_prompt({"request": {"mode": "single"}, "description": "x"})
    assert "one single running workout" in single
    assert "Garmin activities" not in single  # chat-only mode: no history sections
