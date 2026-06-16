"""Pytest fixtures: isolated DB + a FastAPI test client with AI/Garmin mocked."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.main import app

FAKE_PLAN = {
    "structure_explanation": "Build an aerobic base, then sharpen before the goal.",
    "full_explanation": "A short sample plan used in tests.",
    "change_summary": None,
    "workout_types": [
        {"name": "Easy Run", "description": "Conversational-pace aerobic run."},
        {"name": "Long Run", "description": "The week's key endurance run."},
    ],
    "weeks": [
        {
            "week_no": 1,
            "focus": "base",
            "workouts": [
                {
                    "weekday": 0,
                    "workout_type": "Long Run",
                    "goal": "10 km easy",
                    "how_to": "Keep it conversational.",
                    "details": {"distance_km": 10},
                },
                {
                    "weekday": 2,
                    "workout_type": "Tempo",
                    "goal": "5 km @ threshold",
                    "how_to": "Comfortably hard.",
                    "details": {},
                },
            ],
        },
        {
            "week_no": 2,
            "focus": "build",
            "workouts": [
                {
                    "weekday": 0,
                    "workout_type": "Long Run",
                    "goal": "12 km easy",
                    "how_to": "",
                    "details": {},
                }
            ],
        },
    ],
}


@pytest.fixture
def db_session_factory(tmp_path):
    db_file = tmp_path / "test.sqlite3"
    engine = create_engine(
        f"sqlite:///{db_file}", connect_args={"check_same_thread": False}, future=True
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture
def client(db_session_factory):
    def override_get_db():
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # No `with` block => Starlette lifespan (scheduler/init_db) does not run.
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_agent(monkeypatch):
    """Patch the single AI integration point to return a deterministic plan."""
    from app.services import agent_service

    async def fake_run_agent(system, prompt, model, effort):
        return FAKE_PLAN

    monkeypatch.setattr(agent_service, "_run_agent", fake_run_agent)
    monkeypatch.setattr(agent_service, "is_available", lambda: True)

    async def fake_chat(messages, context, ai_model):
        return "Sure — noted those changes."

    monkeypatch.setattr(agent_service, "chat_reply", fake_chat)
    return agent_service


def auth_headers(client: TestClient, email: str = "runner@example.com") -> dict[str, str]:
    resp = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "password123",
            "profile": {"name": "Test Runner", "personal_records": []},
        },
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
