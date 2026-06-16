"""Claude Agent SDK service.

Runs the running-coach agent with a single restricted custom tool, ``submit_plan``,
used to capture the structured plan. No filesystem/shell tools are granted. The
``claude_agent_sdk`` package is imported lazily so the rest of the app and the
tests work without it installed (tests monkeypatch ``_run_agent``).
"""
from __future__ import annotations

import dataclasses
import json
import logging
import os
import re
from typing import Any

from ..config import get_settings
from ..schemas import AgentPlan
from ..agent import prompts

logger = logging.getLogger("coach.agent")
settings = get_settings()

REASONING_BUDGET = {"minimal": 0, "low": 2000, "medium": 6000, "high": 12000}

SUBMIT_PLAN_DESCRIPTION = (
    "Submit the final structured training plan. Pass the entire plan as a single "
    "JSON object (or JSON string) with keys: structure_explanation, full_explanation, "
    "change_summary (optional), workout_types (list of {name, description}), and weeks "
    "(list of {week_no, focus, workouts:[{weekday, workout_type, goal, how_to, "
    "details}]}). weekday is 0=Sunday..6=Saturday."
)


class AgentError(Exception):
    pass


class AgentUnavailableError(AgentError):
    pass


def is_available() -> bool:
    if not (settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")):
        return False
    try:
        import claude_agent_sdk  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def _ensure_api_key() -> None:
    key = settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise AgentUnavailableError(
            "ANTHROPIC_API_KEY is not set. Add it to your .env to enable AI plans."
        )
    os.environ.setdefault("ANTHROPIC_API_KEY", key)


def _coerce_plan_arg(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return _extract_json(raw)
    return None


def _option_field_names(options_cls: Any) -> set[str]:
    """Field names supported by the installed ClaudeAgentOptions, if discoverable."""
    try:
        return {f.name for f in dataclasses.fields(options_cls)}
    except TypeError:
        return set()


def _extract_json(text: str) -> dict[str, Any] | None:
    """Best-effort extraction of the last top-level JSON object from text."""
    candidates = re.findall(r"\{.*\}", text, re.DOTALL)
    for chunk in reversed(candidates):
        try:
            return json.loads(chunk)
        except json.JSONDecodeError:
            continue
    return None


async def _run_agent(system_prompt: str, user_prompt: str, model: str, effort: str) -> dict[str, Any]:
    """Run the agent loop and return the captured plan dict.

    This is the single integration point with the Claude Agent SDK and is the
    function monkeypatched in tests.
    """
    _ensure_api_key()
    from claude_agent_sdk import (  # lazy import
        ClaudeAgentOptions,
        create_sdk_mcp_server,
        query,
        tool,
    )

    captured: dict[str, Any] = {}
    text_chunks: list[str] = []

    @tool("submit_plan", SUBMIT_PLAN_DESCRIPTION, {"plan": str})
    async def submit_plan(args: dict[str, Any]) -> dict[str, Any]:
        plan = _coerce_plan_arg(args.get("plan"))
        if plan is not None:
            captured["plan"] = plan
        return {"content": [{"type": "text", "text": "Plan received. Thank you."}]}

    server = create_sdk_mcp_server(name="coach", version="1.0.0", tools=[submit_plan])

    option_kwargs: dict[str, Any] = {
        "system_prompt": system_prompt,
        "mcp_servers": {"coach": server},
        "allowed_tools": ["mcp__coach__submit_plan"],
        "model": model,
        "max_turns": 12,
    }
    field_names = _option_field_names(ClaudeAgentOptions)
    if "setting_sources" in field_names:
        option_kwargs["setting_sources"] = []
    budget = REASONING_BUDGET.get(effort, 0)
    if budget and "max_thinking_tokens" in field_names:
        option_kwargs["max_thinking_tokens"] = budget

    options = ClaudeAgentOptions(**option_kwargs)

    try:
        async for message in query(prompt=user_prompt, options=options):
            for block in getattr(message, "content", []) or []:
                txt = getattr(block, "text", None)
                if txt:
                    text_chunks.append(txt)
    except Exception as exc:  # noqa: BLE001
        raise AgentError(f"AI plan generation failed: {exc}") from exc

    if "plan" not in captured:
        fallback = _extract_json("\n".join(text_chunks))
        if fallback is not None:
            captured["plan"] = fallback

    if "plan" not in captured:
        raise AgentError("The AI did not return a structured plan. Please try again.")
    return captured["plan"]


def _validate(plan_dict: dict[str, Any]) -> AgentPlan:
    try:
        return AgentPlan.model_validate(plan_dict)
    except Exception as exc:  # noqa: BLE001
        raise AgentError(f"AI returned an invalid plan: {exc}") from exc


async def _generate(system_prompt: str, user_prompt: str, ai_model: str, effort: str) -> AgentPlan:
    plan_dict = await _run_agent(system_prompt, user_prompt, ai_model, effort)
    return _validate(plan_dict)


# --------------------------------------------------------------------------- #
# Public API (context dicts are built by the plans router / plan_builder)
# --------------------------------------------------------------------------- #


async def generate(context: dict[str, Any], ai_model: str, effort: str) -> AgentPlan:
    system = f"{prompts.SYSTEM_PROMPT}\n\n{prompts.reasoning_line(effort)}"
    return await _generate(system, prompts.build_generate_prompt(context), ai_model, effort)


async def regenerate_with_changes(
    context: dict[str, Any], ai_model: str, effort: str
) -> AgentPlan:
    system = f"{prompts.SYSTEM_PROMPT}\n\n{prompts.reasoning_line(effort)}"
    return await _generate(system, prompts.build_chat_edit_prompt(context), ai_model, effort)


async def weekly_review(context: dict[str, Any], ai_model: str, effort: str) -> AgentPlan:
    system = f"{prompts.SYSTEM_PROMPT}\n\n{prompts.reasoning_line(effort)}"
    return await _generate(system, prompts.build_weekly_update_prompt(context), ai_model, effort)


async def manual_update(context: dict[str, Any], ai_model: str, effort: str) -> AgentPlan:
    system = f"{prompts.SYSTEM_PROMPT}\n\n{prompts.reasoning_line(effort)}"
    return await _generate(system, prompts.build_manual_update_prompt(context), ai_model, effort)


async def chat_reply(messages: list[dict[str, str]], context: dict[str, Any], ai_model: str) -> str:
    """Conversational reply while the user describes desired plan changes.

    Does not produce a full plan; it helps clarify the requested changes.
    """
    _ensure_api_key()
    from claude_agent_sdk import ClaudeAgentOptions, query  # lazy import

    system = (
        "You are a running coach helping the athlete describe changes they want to "
        "make to their current training plan. Acknowledge and, if useful, ask brief "
        "clarifying questions. Keep replies short. Do NOT output a full training plan; "
        "the plan will be regenerated once the athlete confirms their changes."
    )
    convo = [f"## Current plan context\n{json.dumps(context, default=str)[:6000]}", ""]
    for m in messages:
        convo.append(f"{m['role'].upper()}: {m['content']}")
    convo.append("ASSISTANT:")
    prompt = "\n".join(convo)

    option_kwargs: dict[str, Any] = {"system_prompt": system, "model": ai_model, "max_turns": 1}
    if "setting_sources" in _option_field_names(ClaudeAgentOptions):
        option_kwargs["setting_sources"] = []
    options = ClaudeAgentOptions(**option_kwargs)

    chunks: list[str] = []
    try:
        async for message in query(prompt=prompt, options=options):
            for block in getattr(message, "content", []) or []:
                txt = getattr(block, "text", None)
                if txt:
                    chunks.append(txt)
    except Exception as exc:  # noqa: BLE001
        raise AgentError(f"AI chat failed: {exc}") from exc
    return "\n".join(chunks).strip() or "Got it."
