"""Match synced activities to planned workouts for tracking and weekly review."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    Activity,
    PlannedWorkout,
    PlanVersion,
    TrainingPlan,
    User,
    WorkoutCompletion,
)
from .garmin_service import RUN_TYPES
from .week import WEEKDAY_NAMES, israeli_weekday, week_number_for, week_start


def plan_date_range(version: PlanVersion) -> tuple[date, date]:
    start = version.start_date or date.today()
    weeks = version.num_weeks or 1
    return start, start + timedelta(days=weeks * 7 - 1)


def _is_run(activity: Activity) -> bool:
    return (activity.activity_type or "").lower() in RUN_TYPES


def recompute_completions(
    db: Session, user: User, plan: TrainingPlan, version: PlanVersion
) -> int:
    """Rebuild WorkoutCompletion rows linking activities to planned workouts."""
    db.query(WorkoutCompletion).filter(WorkoutCompletion.plan_id == plan.id).delete()

    start, end = plan_date_range(version)
    activities = list(
        db.scalars(
            select(Activity)
            .where(
                Activity.user_id == user.id,
                Activity.activity_date >= start,
                Activity.activity_date <= end,
            )
            .order_by(Activity.activity_date)
        )
    )
    planned = list(version.planned_workouts)
    matched_ids: set[int] = set()
    count = 0

    for act in activities:
        if not _is_run(act):
            continue
        match = _find_planned_match(act, planned, matched_ids)
        if match is not None:
            matched_ids.add(match.id)
        db.add(
            WorkoutCompletion(
                user_id=user.id,
                plan_id=plan.id,
                activity_id=act.id,
                planned_workout_id=match.id if match else None,
                performed_date=act.activity_date,
            )
        )
        count += 1

    db.commit()
    return count


def _find_planned_match(
    act: Activity, planned: list[PlannedWorkout], matched_ids: set[int]
) -> PlannedWorkout | None:
    # 1) Same exact day.
    for pw in planned:
        if pw.id not in matched_ids and pw.date == act.activity_date:
            return pw
    # 2) Same Israeli week, nearest unmatched planned run-type workout.
    act_week = week_start(act.activity_date)
    candidates = [
        pw
        for pw in planned
        if pw.id not in matched_ids and week_start(pw.date) == act_week
    ]
    if candidates:
        candidates.sort(key=lambda pw: abs((pw.date - act.activity_date).days))
        return candidates[0]
    return None


def current_week_no(version: PlanVersion, today: date | None = None) -> int:
    today = today or date.today()
    start = version.start_date or today
    if today < start:
        return 1
    wn = week_number_for(start, today)
    return max(1, min(wn, version.num_weeks or wn))


def week_tracking(
    db: Session,
    user: User,
    version: PlanVersion,
    week_no: int,
    today: date | None = None,
) -> dict[str, Any]:
    """Build a planned-vs-actual view for a single week."""
    today = today or date.today()
    start = version.start_date or today
    wk_start = week_start(start) + timedelta(days=(week_no - 1) * 7)
    wk_end = wk_start + timedelta(days=6)

    planned_by_date: dict[date, list[PlannedWorkout]] = {}
    for pw in version.planned_workouts:
        if wk_start <= pw.date <= wk_end:
            planned_by_date.setdefault(pw.date, []).append(pw)

    activities = list(
        db.scalars(
            select(Activity)
            .where(
                Activity.user_id == user.id,
                Activity.activity_date >= wk_start,
                Activity.activity_date <= wk_end,
            )
            .order_by(Activity.activity_date)
        )
    )
    actual_by_date: dict[date, list[Activity]] = {}
    for act in activities:
        if _is_run(act):
            actual_by_date.setdefault(act.activity_date, []).append(act)

    days = []
    for i in range(7):
        d = wk_start + timedelta(days=i)
        planned = planned_by_date.get(d, [])
        actual = actual_by_date.get(d, [])
        status = _day_status(planned, actual, d, today)
        days.append(
            {
                "date": d,
                "weekday": israeli_weekday(d),
                "weekday_name": WEEKDAY_NAMES[israeli_weekday(d)],
                "planned": planned,
                "actual": actual,
                "status": status,
            }
        )

    return {
        "plan_id": version.plan_id,
        "version_id": version.id,
        "week_no": week_no,
        "week_start": wk_start,
        "week_end": wk_end,
        "days": days,
    }


def _day_status(
    planned: list[PlannedWorkout],
    actual: list[Activity],
    d: date,
    today: date,
) -> str:
    has_planned = len(planned) > 0
    has_actual = len(actual) > 0
    if has_planned and has_actual:
        return "completed"
    if has_planned and not has_actual:
        return "missed" if d < today else "upcoming"
    if not has_planned and has_actual:
        return "extra"
    return "rest"


def progress_summary(
    db: Session, user: User, version: PlanVersion, up_to: date | None = None
) -> dict[str, Any]:
    """Summarize planned vs completed so far, for the AI weekly review."""
    up_to = up_to or date.today()
    start, _ = plan_date_range(version)

    completed = 0
    missed = 0
    rows: list[dict[str, Any]] = []
    activities = list(
        db.scalars(
            select(Activity).where(
                Activity.user_id == user.id,
                Activity.activity_date >= start,
                Activity.activity_date <= up_to,
            )
        )
    )
    runs = [a for a in activities if _is_run(a)]
    by_date: dict[date, list[Activity]] = {}
    for a in runs:
        by_date.setdefault(a.activity_date, []).append(a)

    for pw in version.planned_workouts:
        if pw.date > up_to:
            continue
        done = bool(by_date.get(pw.date))
        if done:
            completed += 1
        else:
            missed += 1
        rows.append(
            {
                "date": pw.date.isoformat(),
                "type": pw.workout_type,
                "goal": pw.goal,
                "completed": done,
            }
        )

    actual_rows = [
        {
            "date": a.activity_date.isoformat(),
            "type": a.activity_type,
            "distance_km": round((a.distance_m or 0) / 1000.0, 2),
            "duration_min": round((a.duration_s or 0) / 60.0, 1),
            "avg_hr": a.avg_hr,
        }
        for a in runs
    ]

    return {
        "planned_completed": completed,
        "planned_missed": missed,
        "planned_rows": rows,
        "actual_activities": actual_rows,
    }
