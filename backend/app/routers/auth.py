"""Registration, login, and current-user endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from ..config import get_settings
from ..db import get_db
from ..models import Profile, User, UserSettings
from ..schemas import LoginIn, RegisterIn, Token, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, db: Session = Depends(get_db)) -> Token:
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(email=payload.email.lower(), password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()

    prof = payload.profile
    db.add(
        Profile(
            user_id=user.id,
            name=prof.name,
            height_cm=prof.height_cm,
            weight_kg=prof.weight_kg,
            gender=prof.gender,
            date_of_birth=prof.date_of_birth,
            personal_records=[pr.model_dump() for pr in prof.personal_records],
            notes=prof.notes,
        )
    )
    db.add(
        UserSettings(
            user_id=user.id,
            ai_model=settings.default_ai_model,
            reasoning_effort=settings.default_reasoning_effort,
        )
    )
    db.commit()
    return Token(access_token=create_access_token(user.id))


@router.post("/login", response_model=Token)
def login(payload: LoginIn, db: Session = Depends(get_db)) -> Token:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
