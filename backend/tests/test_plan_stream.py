"""SSE streaming endpoints: live agent events end with a materialized plan."""
import json
from datetime import date, timedelta

import pytest

from tests.conftest import FAKE_PLAN, auth_headers


def _future_date(days: int = 56) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


@pytest.fixture
def mock_stream_agent(monkeypatch):
    """Patch the single streaming integration point with a scripted run."""
    from app.services import agent_service

    async def fake_stream_agent(system, user, model, effort):
        yield {"type": "thinking", "delta": "Planning the base phase…"}
        yield {"type": "text", "delta": "Here is your plan."}
        yield {"type": "step", "label": "Submitting the finished plan…"}
        yield {"type": "plan", "plan": FAKE_PLAN}

    monkeypatch.setattr(agent_service, "_stream_agent", fake_stream_agent)
    monkeypatch.setattr(agent_service, "is_available", lambda: True)
    return agent_service


def _parse_sse(text: str) -> list[dict]:
    events: list[dict] = []
    for block in text.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:].strip()))
    return events


def test_create_plan_stream(client, mock_stream_agent):
    headers = auth_headers(client)
    resp = client.post(
        "/api/plans/stream",
        headers=headers,
        json={
            "distance_label": "10K",
            "target_date": _future_date(),
            "goal_type": "time",
            "goal_value": "45:00",
            "days_available": ["Sunday", "Tuesday", "Thursday"],
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(resp.text)
    types = [e["type"] for e in events]
    assert types[0] == "prompt"  # full prompt streamed first
    assert {"thinking", "text", "step"} <= set(types)
    assert types[-1] == "done"

    done = events[-1]
    assert isinstance(done["plan_id"], int)
    assert isinstance(done["version_id"], int)
    # The prompt event carries the real assembled system + user prompts.
    prompt = events[0]
    assert prompt["system"] and prompt["user"]

    # Plan persisted as a draft with one version.
    plan = client.get(f"/api/plans/{done['plan_id']}", headers=headers).json()
    assert plan["status"] == "draft"
    assert len(plan["versions"]) == 1
    assert plan["versions"][0]["status"] == "draft"


def test_manual_update_stream(client, mock_stream_agent):
    headers = auth_headers(client)
    created = _parse_sse(
        client.post(
            "/api/plans/stream",
            headers=headers,
            json={
                "distance_label": "10K",
                "target_date": _future_date(),
                "days_available": ["Sunday"],
            },
        ).text
    )
    done = created[-1]
    plan_id, version_id = done["plan_id"], done["version_id"]

    # Approve so there is an active base to update.
    client.post(f"/api/plans/{plan_id}/versions/{version_id}/approve", headers=headers)

    resp = client.post(
        f"/api/plans/{plan_id}/manual-update/stream",
        headers=headers,
        json={"request_text": "Move long runs to Saturday."},
    )
    assert resp.status_code == 200, resp.text
    events = _parse_sse(resp.text)
    assert events[-1]["type"] == "done"
    assert events[-1]["update_recommended"] is True
    assert isinstance(events[-1]["proposed_version_id"], int)
