"""Training-plan tracking: planned vs. actual by week."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..models import TrainingPlan, User
from ..schemas import TrackingWeek
from ..services import matching

router = APIRouter(prefix="/api/plans", tags=["tracking"])


@router.get("/{plan_id}/tracking", response_model=TrackingWeek)
def get_tracking(
    plan_id: int,
    week_no: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TrackingWeek:
    plan = db.get(TrainingPlan, plan_id)
    if plan is None or plan.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found.")

    version = plan.active_version
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approve a plan version before tracking it.",
        )

    num_weeks = version.num_weeks or 1
    current = matching.current_week_no(version)
    selected = week_no or current
    selected = max(1, min(selected, num_weeks))

    data = matching.week_tracking(db, user, version, selected)
    data["num_weeks"] = num_weeks
    data["current_week"] = current
    return TrackingWeek(**data)
