"""AI model + reasoning effort settings."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import get_settings
from ..db import get_db
from ..models import User, UserSettings
from ..schemas import SettingsIn, SettingsOut

router = APIRouter(prefix="/api/settings", tags=["settings"])
app_settings = get_settings()

# Models offered in the UI. The user can also rely on whatever the API key allows.
AVAILABLE_MODELS = [
    "claude-opus-4-8",
    "claude-sonnet-4-6"
]
REASONING_EFFORTS = ["low", "medium", "high", "max"]


def _get_or_create(db: Session, user: User) -> UserSettings:
    if user.settings is None:
        s = UserSettings(
            user_id=user.id,
            ai_model=app_settings.default_ai_model,
            reasoning_effort=app_settings.default_reasoning_effort,
        )
        db.add(s)
        db.commit()
        db.refresh(s)
        return s
    return user.settings


@router.get("", response_model=SettingsOut)
def get_user_settings(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> UserSettings:
    return _get_or_create(db, user)


@router.put("", response_model=SettingsOut)
def update_user_settings(
    payload: SettingsIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserSettings:
    s = _get_or_create(db, user)
    s.ai_model = payload.ai_model
    s.reasoning_effort = payload.reasoning_effort
    db.commit()
    db.refresh(s)
    return s


@router.get("/options")
def options() -> dict[str, list[str]]:
    return {"models": AVAILABLE_MODELS, "reasoning_efforts": REASONING_EFFORTS}
