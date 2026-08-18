"""Single source of truth for AI model/effort options and their resolution.

The offered lists feed both the Settings UI (via ``GET /api/settings/options``)
and request validation. ``resolve`` is the one place that turns a user (plus an
optional per-request override) into the ``(model, effort)`` pair every AI
endpoint uses.
"""
from __future__ import annotations

from typing import Any

from ..config import get_settings

# Models offered in the UI. The user can also rely on whatever the API key allows.
AVAILABLE_MODELS = [
    "claude-opus-5",
    "claude-sonnet-5",
    "claude-fable-5",
]
REASONING_EFFORTS = ["low", "medium", "high", "max"]


def resolve(
    user: Any, ai_model: str | None = None, reasoning_effort: str | None = None
) -> tuple[str, str]:
    """Return ``(model, effort)``: override > user settings > config defaults.

    Explicit overrides are validated against the offered lists (``ValueError``
    on unknown values); stored settings pass through unvalidated so legacy
    values in existing rows keep working.
    """
    if ai_model is not None and ai_model not in AVAILABLE_MODELS:
        raise ValueError(f"Unknown AI model: {ai_model}")
    if reasoning_effort is not None and reasoning_effort not in REASONING_EFFORTS:
        raise ValueError(f"Unknown reasoning effort: {reasoning_effort}")
    app = get_settings()
    settings = getattr(user, "settings", None)
    stored_model = settings.ai_model if settings is not None else app.default_ai_model
    stored_effort = (
        settings.reasoning_effort if settings is not None else app.default_reasoning_effort
    )
    return ai_model or stored_model, reasoning_effort or stored_effort
