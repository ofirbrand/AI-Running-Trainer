"""Tests for the direct-Anthropic AI backend (AI_BACKEND=api).

The anthropic client is faked at the ``agent_api._client`` seam; assertions
pin the client-facing event schema to exact parity with the SDK backend.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from app.services import agent_api, agent_service

from .conftest import FAKE_PLAN


def collect(agen):
    async def _run():
        return [event async for event in agen]

    return asyncio.run(_run())


# --------------------------------------------------------------------------- #
# Fake anthropic client
# --------------------------------------------------------------------------- #


def tool_use_block(name: str, input_: dict, block_id: str = "tu_1"):
    return SimpleNamespace(type="tool_use", name=name, input=input_, id=block_id)


def start_event(block):
    return SimpleNamespace(type="content_block_start", content_block=block)


def thinking_event(text: str):
    return SimpleNamespace(
        type="content_block_delta",
        delta=SimpleNamespace(type="thinking_delta", thinking=text),
    )


def text_event(text: str):
    return SimpleNamespace(
        type="content_block_delta",
        delta=SimpleNamespace(type="text_delta", text=text),
    )


class FakeStream:
    def __init__(self, events, final):
        self._events = events
        self._final = final

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def __aiter__(self):
        async def gen():
            for event in self._events:
                yield event

        return gen()

    async def get_final_message(self):
        return self._final


class FakeMessages:
    def __init__(self, turns):
        self.turns = list(turns)  # list of (events, final_message)
        self.calls: list[dict] = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        events, final = self.turns.pop(0)
        return FakeStream(events, final)


def fake_client(monkeypatch, turns) -> FakeMessages:
    messages = FakeMessages(turns)
    monkeypatch.setattr(agent_api, "_client", lambda: SimpleNamespace(messages=messages))
    monkeypatch.setattr(agent_api, "_ensure_api_key", lambda: None)
    return messages


# --------------------------------------------------------------------------- #
# stream_agent
# --------------------------------------------------------------------------- #


def test_stream_agent_happy_path_event_schema(monkeypatch):
    block = tool_use_block("submit_plan", {"plan": json.dumps(FAKE_PLAN)})
    events = [start_event(block), thinking_event("Pondering..."), text_event("Here goes.")]
    final = SimpleNamespace(stop_reason="tool_use", content=[block])
    fake_client(monkeypatch, [(events, final)])

    out = collect(agent_api.stream_agent("sys", "user", "claude-sonnet-4-5", "medium"))

    assert out == [
        {"type": "step", "label": "Submitting the finished plan…"},
        {"type": "thinking", "delta": "Pondering..."},
        {"type": "text", "delta": "Here goes."},
        {"type": "plan", "plan": FAKE_PLAN},
    ]


def test_stream_agent_text_fallback_extracts_json(monkeypatch):
    events = [text_event("No tool for me: " + json.dumps(FAKE_PLAN))]
    final = SimpleNamespace(stop_reason="end_turn", content=[])
    fake_client(monkeypatch, [(events, final)])

    out = collect(agent_api.stream_agent("sys", "user", "claude-sonnet-4-5", "medium"))
    assert out[-1]["type"] == "plan"
    assert out[-1]["plan"] == FAKE_PLAN


def test_stream_agent_no_plan_raises_exact_message(monkeypatch):
    final = SimpleNamespace(stop_reason="end_turn", content=[])
    fake_client(monkeypatch, [([text_event("nothing structured here")], final)])

    with pytest.raises(agent_service.AgentError) as excinfo:
        collect(agent_api.stream_agent("sys", "user", "claude-sonnet-4-5", "medium"))
    assert "The AI did not return a structured plan" in str(excinfo.value)


def test_stream_agent_multi_turn_loop(monkeypatch):
    other = tool_use_block("other_tool", {}, "tu_other")
    turn1 = ([start_event(other)], SimpleNamespace(stop_reason="tool_use", content=[other]))
    submit = tool_use_block("submit_plan", {"plan": FAKE_PLAN}, "tu_submit")
    turn2 = ([start_event(submit)], SimpleNamespace(stop_reason="tool_use", content=[submit]))
    messages = fake_client(monkeypatch, [turn1, turn2])

    out = collect(agent_api.stream_agent("sys", "user", "claude-sonnet-4-5", "medium"))

    assert out[-1] == {"type": "plan", "plan": FAKE_PLAN}
    assert len(messages.calls) == 2
    # The second request replays the assistant turn plus the tool_result.
    second_messages = messages.calls[1]["messages"]
    assert second_messages[0] == {"role": "user", "content": "user"}
    assert second_messages[1]["role"] == "assistant"
    assert second_messages[2]["role"] == "user"
    assert second_messages[2]["content"][0]["type"] == "tool_result"


def test_run_agent_returns_plan(monkeypatch):
    block = tool_use_block("submit_plan", {"plan": FAKE_PLAN})
    final = SimpleNamespace(stop_reason="tool_use", content=[block])
    fake_client(monkeypatch, [([start_event(block)], final)])

    plan = asyncio.run(agent_api.run_agent("sys", "user", "claude-sonnet-4-5", "medium"))
    assert plan == FAKE_PLAN


# --------------------------------------------------------------------------- #
# Thinking / effort mapping
# --------------------------------------------------------------------------- #


def test_thinking_kwargs_adaptive_models():
    kwargs = agent_api._thinking_kwargs("claude-opus-4-8", "high")
    assert kwargs["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert kwargs["output_config"] == {"effort": "high"}

    kwargs = agent_api._thinking_kwargs("claude-sonnet-4-6", "medium")
    assert kwargs["thinking"] == {"type": "adaptive"}
    assert kwargs["output_config"] == {"effort": "medium"}


def test_thinking_kwargs_budget_models():
    assert agent_api._thinking_kwargs("claude-sonnet-4-5", "high") == {
        "thinking": {"type": "enabled", "budget_tokens": 12000}
    }
    assert agent_api._thinking_kwargs("claude-sonnet-4-5", "minimal") == {}


# --------------------------------------------------------------------------- #
# Dispatcher routing (AI_BACKEND=api)
# --------------------------------------------------------------------------- #


def test_dispatchers_route_to_api_backend(monkeypatch):
    monkeypatch.setattr(agent_service.settings, "ai_backend", "api")

    async def fake_run(system, prompt, model, effort):
        return {"via": "api"}

    async def fake_stream(system, prompt, model, effort):
        yield {"type": "plan", "plan": {"via": "api"}}

    async def fake_chat(system, prompt, model):
        return "api says hi"

    monkeypatch.setattr(agent_api, "run_agent", fake_run)
    monkeypatch.setattr(agent_api, "stream_agent", fake_stream)
    monkeypatch.setattr(agent_api, "chat_once", fake_chat)
    monkeypatch.setattr(agent_service, "_ensure_api_key", lambda: None)

    assert asyncio.run(agent_service._run_agent("s", "u", "m", "e")) == {"via": "api"}
    events = collect(agent_service._stream_agent("s", "u", "m", "e"))
    assert events == [{"type": "plan", "plan": {"via": "api"}}]
    reply = asyncio.run(agent_service.chat_reply([{"role": "user", "content": "hi"}], {}, "m"))
    assert reply == "api says hi"


def test_is_available_uses_api_backend(monkeypatch):
    monkeypatch.setattr(agent_service.settings, "ai_backend", "api")
    monkeypatch.setattr(agent_api, "is_available", lambda: True)
    assert agent_service.is_available() is True
    monkeypatch.setattr(agent_api, "is_available", lambda: False)
    assert agent_service.is_available() is False
