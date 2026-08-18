"""Direct Anthropic API backend for the coach agent (AI_BACKEND=api).

Serverless-friendly alternative to the Claude Agent SDK path in
``agent_service`` (the SDK spawns a local Node CLI subprocess, which is
unavailable on Vercel). Reproduces the same behavior — one restricted
``submit_plan`` tool, an agentic loop capped at 12 turns, and the exact
client-facing event schema (``thinking``/``text`` deltas, ``step`` labels,
terminal ``plan``) — using the ``anthropic`` SDK's Messages API.
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

from ..config import get_settings
from .agent_service import (
    REASONING_BUDGET,
    SUBMIT_PLAN_DESCRIPTION,
    AgentError,
    _coerce_plan_arg,
    _ensure_api_key,
    _extract_json,
    _step_label,
)

settings = get_settings()

MAX_TURNS = 12  # mirrors the SDK path's max_turns
MAX_TOKENS = 64000  # room for thinking + a large plan JSON; ≤ every model's cap

SUBMIT_PLAN_TOOL = {
    "name": "submit_plan",
    "description": SUBMIT_PLAN_DESCRIPTION,
    "input_schema": {
        "type": "object",
        "properties": {"plan": {"type": "string"}},
        "required": ["plan"],
    },
}

# Model families that use adaptive thinking (budget_tokens is rejected there).
# The newer families default thinking display to "omitted", so we opt into
# "summarized" to keep streaming the thinking deltas the UI renders.
_ADAPTIVE_DISPLAY_FAMILIES = ("opus-5", "opus-4-8", "sonnet-5", "fable-5")
_ADAPTIVE_FAMILIES = ("opus-5", "sonnet-5", "fable-5")
_EFFORT_MAP = {"minimal": "low", "low": "low", "medium": "medium", "high": "high", "max": "max"}


def is_available() -> bool:
    if not (settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")):
        return False
    try:
        import anthropic  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def _client() -> Any:
    """Build the async Anthropic client (monkeypatched in tests)."""
    import anthropic  # lazy import

    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key or None)


def _thinking_kwargs(model: str, effort: str) -> dict[str, Any]:
    """Model-aware reasoning config mirroring the SDK path's REASONING_BUDGET."""
    if any(f in model for f in _ADAPTIVE_DISPLAY_FAMILIES):
        return {
            "thinking": {"type": "adaptive", "display": "summarized"},
            "output_config": {"effort": _EFFORT_MAP.get(effort, "high")},
        }
    if any(f in model for f in _ADAPTIVE_FAMILIES):
        return {
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": _EFFORT_MAP.get(effort, "high")},
        }
    budget = REASONING_BUDGET.get(effort, 0)
    if budget:
        return {"thinking": {"type": "enabled", "budget_tokens": budget}}
    return {}


async def stream_agent(
    system_prompt: str, user_prompt: str, model: str, effort: str
) -> AsyncIterator[dict[str, Any]]:
    """Run the agent loop, yielding the same events as the SDK ``_stream_agent``:
    ``thinking``/``text`` deltas, ``step`` labels, then ``{"type": "plan", ...}``.
    """
    _ensure_api_key()
    client = _client()

    captured: dict[str, Any] = {}
    text_chunks: list[str] = []
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]

    try:
        for _ in range(MAX_TURNS):
            async with client.messages.stream(
                model=model,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                tools=[SUBMIT_PLAN_TOOL],
                messages=messages,
                **_thinking_kwargs(model, effort),
            ) as stream:
                async for event in stream:
                    etype = getattr(event, "type", None)
                    if etype == "content_block_start":
                        block = getattr(event, "content_block", None)
                        if getattr(block, "type", None) == "tool_use":
                            yield {
                                "type": "step",
                                "label": _step_label(getattr(block, "name", None)),
                            }
                    elif etype == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        dtype = getattr(delta, "type", None)
                        if dtype == "thinking_delta" and getattr(delta, "thinking", None):
                            yield {"type": "thinking", "delta": delta.thinking}
                        elif dtype == "text_delta" and getattr(delta, "text", None):
                            text_chunks.append(delta.text)
                            yield {"type": "text", "delta": delta.text}
                response = await stream.get_final_message()

            if response.stop_reason == "tool_use":
                tool_results: list[dict[str, Any]] = []
                for block in response.content:
                    if getattr(block, "type", None) != "tool_use":
                        continue
                    if block.name == "submit_plan":
                        plan = _coerce_plan_arg((block.input or {}).get("plan"))
                        if plan is not None:
                            captured["plan"] = plan
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": "Plan received. Thank you.",
                            }
                        )
                    else:
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": f"Unknown tool: {block.name}",
                                "is_error": True,
                            }
                        )
                if "plan" in captured:
                    # The plan is in hand; skip the closing courtesy round trip.
                    break
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
                continue
            if response.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": response.content})
                continue
            break  # end_turn / max_tokens / refusal
    except AgentError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise AgentError(f"AI plan generation failed: {exc}") from exc

    if "plan" not in captured:
        fallback = _extract_json("\n".join(text_chunks))
        if fallback is not None:
            captured["plan"] = fallback
    if "plan" not in captured:
        raise AgentError("The AI did not return a structured plan. Please try again.")

    yield {"type": "plan", "plan": captured["plan"]}


async def run_agent(
    system_prompt: str, user_prompt: str, model: str, effort: str
) -> dict[str, Any]:
    """Blocking variant: consume ``stream_agent`` and return the plan dict."""
    plan: dict[str, Any] | None = None
    async for event in stream_agent(system_prompt, user_prompt, model, effort):
        if event.get("type") == "plan":
            plan = event["plan"]
    if plan is None:  # unreachable: stream_agent raises or yields a plan
        raise AgentError("The AI did not return a structured plan. Please try again.")
    return plan


async def chat_once(system: str, prompt: str, model: str) -> str:
    """Single conversational reply (the API-backend counterpart of chat_reply)."""
    _ensure_api_key()
    client = _client()
    try:
        response = await client.messages.create(
            model=model,
            max_tokens=2000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:  # noqa: BLE001
        raise AgentError(f"AI chat failed: {exc}") from exc
    chunks = [
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text" and getattr(block, "text", None)
    ]
    return "\n".join(chunks).strip() or "Got it."
