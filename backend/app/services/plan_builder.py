"""DB-aware helpers: build agent context and materialize plan versions."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    Activity,
    MetricObservation,
    PlannedWorkout,
    PlanVersion,
    Profile,
    TrainingPlan,
    User,
)
from ..schemas import AgentPlan, PlanInputs
from .week import week_start, weeks_between

# Plan-input fields that should be persisted as metric observations.
INPUT_METRIC_KEYS = {
    "vo2max": ("vo2max", "ml/kg/min"),
    "resting_hr": ("resting_hr", "bpm"),
    "max_hr": ("max_hr", "bpm"),
    "threshold_hr": ("threshold_hr", "bpm"),
    "longest_run_last_month_km": ("longest_run_30d_m", "m"),
    "current_weekly_volume": ("weekly_volume", None),
    "training_frequency_days": ("training_frequency_days", "days"),
    "training_load": ("training_load", None),
    "experience_level": ("experience_level", None),
}


def gather_profile(user: User) -> dict[str, Any]:
    p: Profile | None = user.profile
    if p is None:
        return {}
    return {
        "name": p.name,
        "height_cm": p.height_cm,
        "weight_kg": p.weight_kg,
        "gender": p.gender,
        "date_of_birth": p.date_of_birth.isoformat() if p.date_of_birth else None,
        "personal_records": p.personal_records or [],
        "notes": p.notes,
    }


def gather_metrics(db: Session, user: User) -> dict[str, Any]:
    rows = db.scalars(
        select(MetricObservation).where(MetricObservation.user_id == user.id)
    )
    out: dict[str, Any] = {}
    for m in rows:
        value = (m.value or {}).get("value") if isinstance(m.value, dict) else m.value
        unit = (m.value or {}).get("unit") if isinstance(m.value, dict) else None
        out[m.key] = {
            "value": value,
            "unit": unit,
            "source": m.source,
            "measured_at": m.measured_at.isoformat() if m.measured_at else None,
        }
    return out


def _activity_to_dict(a: Activity) -> dict[str, Any]:
    return {
        "date": a.activity_date.isoformat(),
        "type": a.activity_type,
        "distance_km": round((a.distance_m or 0) / 1000.0, 2),
        "duration_min": round((a.duration_s or 0) / 60.0, 1),
        "avg_hr": a.avg_hr,
        "avg_pace_s_per_km": round(a.avg_pace_s_per_km) if a.avg_pace_s_per_km else None,
    }


def gather_recent_activities(db: Session, user: User, limit: int = 20) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(Activity)
        .where(Activity.user_id == user.id)
        .order_by(Activity.activity_date.desc())
        .limit(limit)
    )
    return [_activity_to_dict(a) for a in rows]


def gather_activities_in_range(
    db: Session, user: User, start: date, end: date, limit: int = 100
) -> list[dict[str, Any]]:
    """Activities within [start, end] (inclusive), newest-first, capped for prompt size."""
    rows = db.scalars(
        select(Activity)
        .where(
            Activity.user_id == user.id,
            Activity.activity_date >= start,
            Activity.activity_date <= end,
        )
        .order_by(Activity.activity_date.desc())
        .limit(limit)
    )
    return [_activity_to_dict(a) for a in rows]


def compute_calendar(target_date: date, today: date | None = None) -> tuple[date, int]:
    """Return (start_date_sunday, num_weeks) for a plan ending on target_date."""
    today = today or date.today()
    start = week_start(today)
    num_weeks = weeks_between(today, target_date)
    return start, num_weeks


def current_plan_to_dict(version: PlanVersion) -> dict[str, Any]:
    weeks: dict[int, dict[str, Any]] = {}
    for pw in version.planned_workouts:
        wk = weeks.setdefault(pw.week_no, {"week_no": pw.week_no, "workouts": []})
        wk["workouts"].append(
            {
                "weekday": pw.weekday,
                "date": pw.date.isoformat(),
                "workout_type": pw.workout_type,
                "goal": pw.goal,
                "how_to": pw.how_to,
                "details": pw.details,
            }
        )
    return {
        "structure_explanation": version.structure_explanation,
        "full_explanation": version.full_explanation,
        "workout_types": version.workout_types,
        "start_date": version.start_date.isoformat() if version.start_date else None,
        "num_weeks": version.num_weeks,
        "weeks": [weeks[k] for k in sorted(weeks)],
    }


def build_base_context(db: Session, user: User) -> dict[str, Any]:
    return {
        "profile": gather_profile(user),
        "metrics": gather_metrics(db, user),
        "activities": gather_recent_activities(db, user),
    }


def save_input_metrics(db: Session, user: User, inputs: PlanInputs) -> None:
    """Persist metrics the user entered/confirmed on the create-plan form."""
    today = date.today()
    now = datetime.now(timezone.utc)
    data = inputs.model_dump()
    for field, (key, unit) in INPUT_METRIC_KEYS.items():
        value = data.get(field)
        if value in (None, "", []):
            continue
        if field == "longest_run_last_month_km":
            value = round(float(value) * 1000)  # km -> m
        existing = db.scalar(
            select(MetricObservation).where(
                MetricObservation.user_id == user.id, MetricObservation.key == key
            )
        )
        new_val = {"value": value, "unit": unit}
        if existing is None:
            db.add(
                MetricObservation(
                    user_id=user.id,
                    key=key,
                    value=new_val,
                    source="manual",
                    measured_at=today,
                    confirmed_at=now,
                )
            )
        else:
            stored = existing.value.get("value") if isinstance(existing.value, dict) else None
            if stored != value:
                existing.value = new_val
                existing.source = "manual"
                existing.measured_at = today
            existing.confirmed_at = now
    db.commit()


def next_version_no(plan: TrainingPlan) -> int:
    if not plan.versions:
        return 1
    return max(v.version_no for v in plan.versions) + 1


def materialize_version(
    db: Session,
    plan: TrainingPlan,
    agent_plan: AgentPlan,
    *,
    start_date: date,
    num_weeks: int,
    source: str,
    status: str,
    inputs_snapshot: dict[str, Any] | None = None,
) -> PlanVersion:
    """Create a PlanVersion (+ PlannedWorkouts) from a validated AgentPlan."""
    max_week = max((w.week_no for w in agent_plan.weeks), default=num_weeks)
    version = PlanVersion(
        plan_id=plan.id,
        version_no=next_version_no(plan),
        status=status,
        source=source,
        structure_explanation=agent_plan.structure_explanation,
        full_explanation=agent_plan.full_explanation,
        change_summary=agent_plan.change_summary,
        workout_types=[wt.model_dump() for wt in agent_plan.workout_types],
        inputs_snapshot=inputs_snapshot,
        start_date=start_date,
        num_weeks=max(max_week, num_weeks),
    )
    db.add(version)
    db.flush()  # assign version.id

    base_sunday = week_start(start_date)
    for week in agent_plan.weeks:
        for wo in week.workouts:
            workout_date = base_sunday + timedelta(
                days=(week.week_no - 1) * 7 + wo.weekday
            )
            db.add(
                PlannedWorkout(
                    version_id=version.id,
                    plan_id=plan.id,
                    week_no=week.week_no,
                    weekday=wo.weekday,
                    date=workout_date,
                    workout_type=wo.workout_type,
                    goal=wo.goal,
                    how_to=wo.how_to,
                    details=wo.details or {},
                )
            )
    db.flush()
    return version
