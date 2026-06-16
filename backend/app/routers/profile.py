"""Profile read/update."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..models import Profile, User
from ..schemas import ProfileIn, ProfileOut

router = APIRouter(prefix="/api/profile", tags=["profile"])


def _get_or_create(db: Session, user: User) -> Profile:
    if user.profile is None:
        prof = Profile(user_id=user.id, personal_records=[])
        db.add(prof)
        db.commit()
        db.refresh(prof)
        return prof
    return user.profile


@router.get("", response_model=ProfileOut)
def get_profile(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Profile:
    return _get_or_create(db, user)


@router.put("", response_model=ProfileOut)
def update_profile(
    payload: ProfileIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Profile:
    prof = _get_or_create(db, user)
    prof.name = payload.name
    prof.height_cm = payload.height_cm
    prof.weight_kg = payload.weight_kg
    prof.gender = payload.gender
    prof.date_of_birth = payload.date_of_birth
    prof.personal_records = [pr.model_dump() for pr in payload.personal_records]
    prof.notes = payload.notes
    db.commit()
    db.refresh(prof)
    return prof
