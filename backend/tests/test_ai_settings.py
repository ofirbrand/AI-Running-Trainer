"""Model/effort option catalog and resolution (services.ai_settings + settings API)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.config import get_settings
from app.services import ai_settings

from tests.conftest import auth_headers


# --------------------------------------------------------------------------- #
# resolve() precedence
# --------------------------------------------------------------------------- #


def test_resolve_falls_back_to_config_defaults():
    user = SimpleNamespace(settings=None)
    model, effort = ai_settings.resolve(user)
    assert model == get_settings().default_ai_model
    assert effort == get_settings().default_reasoning_effort


def test_resolve_uses_stored_settings():
    user = SimpleNamespace(
        settings=SimpleNamespace(ai_model="claude-sonnet-4-5", reasoning_effort="minimal")
    )
    # Legacy stored values pass through unvalidated.
    assert ai_settings.resolve(user) == ("claude-sonnet-4-5", "minimal")


def test_resolve_override_wins():
    user = SimpleNamespace(
        settings=SimpleNamespace(ai_model="claude-sonnet-4-6", reasoning_effort="medium")
    )
    model, effort = ai_settings.resolve(
        user, ai_model="claude-opus-4-8", reasoning_effort="max"
    )
    assert (model, effort) == ("claude-opus-4-8", "max")
    # Partial override keeps the other stored value.
    assert ai_settings.resolve(user, reasoning_effort="high") == ("claude-sonnet-4-6", "high")


def test_resolve_rejects_unknown_overrides():
    user = SimpleNamespace(settings=None)
    with pytest.raises(ValueError):
        ai_settings.resolve(user, ai_model="gpt-4o")
    with pytest.raises(ValueError):
        ai_settings.resolve(user, reasoning_effort="ultra")


# --------------------------------------------------------------------------- #
# Settings API — every offered option must round-trip (regression: "max" 422'd)
# --------------------------------------------------------------------------- #


def test_options_endpoint_lists_catalog(client):
    headers = auth_headers(client)
    resp = client.get("/api/settings/options", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["models"] == ai_settings.AVAILABLE_MODELS
    assert body["reasoning_efforts"] == ai_settings.REASONING_EFFORTS


def test_every_offered_option_saves(client):
    headers = auth_headers(client)
    for model in ai_settings.AVAILABLE_MODELS:
        for effort in ai_settings.REASONING_EFFORTS:
            resp = client.put(
                "/api/settings",
                headers=headers,
                json={"ai_model": model, "reasoning_effort": effort},
            )
            assert resp.status_code == 200, f"{model}/{effort}: {resp.text}"
            body = resp.json()
            assert body["ai_model"] == model
            assert body["reasoning_effort"] == effort


def test_unknown_settings_values_rejected(client):
    headers = auth_headers(client)
    resp = client.put(
        "/api/settings",
        headers=headers,
        json={"ai_model": "claude-sonnet-4-6", "reasoning_effort": "ultra"},
    )
    assert resp.status_code == 422
    resp = client.put(
        "/api/settings",
        headers=headers,
        json={"ai_model": "not-a-model", "reasoning_effort": "medium"},
    )
    assert resp.status_code == 422


def test_default_settings_come_from_config(client):
    headers = auth_headers(client)
    resp = client.get("/api/settings", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ai_model"] == get_settings().default_ai_model
    assert body["reasoning_effort"] == get_settings().default_reasoning_effort
