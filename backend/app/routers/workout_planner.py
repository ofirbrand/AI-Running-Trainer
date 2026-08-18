"""Ad-hoc workout / training-week planner.

Generates a single workout or one week of training as a TRANSIENT result: the
generate endpoint performs no database writes — no TrainingPlan/PlanVersion/
PlannedWorkout rows, no metric observations. The only persistence in this router
is the normal Garmin activity sync performed by the data-loading endpoint.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..models import Activity, DailyHealth, User
from ..schemas import (
    AgentPlan,
    WorkoutGarminDataIn,
    WorkoutGarminDataOut,
    WorkoutPlanRequest,
)
from ..services import agent_service, ai_settings, garmin_service, plan_builder
from ..services.week import israeli_weekday, week_start
from .plans import _require_agent, _sse

router = APIRouter(prefix="/api/workout-planner", tags=["workout-planner"])


# --------------------------------------------------------------------------- #
# Garmin data loading (the survey's "loading" step)
# --------------------------------------------------------------------------- #


@router.post("/garmin-data", response_model=WorkoutGarminDataOut)
def load_garmin_data(
    payload: WorkoutGarminDataIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkoutGarminDataOut:
    """Fresh-sync activities for the range, then report what data is available."""
    if user.garmin is None or user.garmin.status == "disconnected":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Garmin account connected.",
        )
    try:
        garmin_service.fetch_activities_window(db, user, payload.start, payload.end)
    except garmin_service.GarminAuthError as exc:
        # 409, not 401: the frontend's axios interceptor logs the user out on
        # any 401, and an expired Garmin session must not end the app session.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except garmin_service.GarminError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    activities_count = (
        db.scalar(
            select(func.count())
            .select_from(Activity)
            .where(
                Activity.user_id == user.id,
                Activity.activity_date >= payload.start,
                Activity.activity_date <= payload.end,
            )
        )
        or 0
    )
    health_days = (
        db.scalar(
            select(func.count())
            .select_from(DailyHealth)
            .where(
                DailyHealth.user_id == user.id,
                DailyHealth.date >= payload.start,
                DailyHealth.date <= payload.end,
            )
        )
        or 0
    )
    return WorkoutGarminDataOut(
        activities_count=activities_count,
        health_days=health_days,
        start=payload.start,
        end=payload.end,
    )


# --------------------------------------------------------------------------- #
# Date math (mirrors plan_builder.materialize_version, but nothing is stored)
# --------------------------------------------------------------------------- #


def _anchor_today(client_today: date | None) -> date:
    """Trust the client's local date within ±2 days of the server's (timezones)."""
    server_today = date.today()
    if client_today is None or abs((client_today - server_today).days) > 2:
        return server_today
    return client_today


def _compute_start_date(payload: WorkoutPlanRequest, today: date) -> date:
    if payload.mode == "week" and payload.week_choice == "next_week":
        return week_start(today) + timedelta(days=7)
    if payload.mode == "single" and payload.day_preference == "tomorrow":
        # Saturday -> Sunday rolls into a new (Israeli) week.
        return week_start(today + timedelta(days=1))
    return week_start(today)


def _calendar_note(payload: WorkoutPlanRequest, today: date, start_date: date) -> str:
    if payload.mode == "week":
        if payload.week_choice == "next_week":
            return (
                f"Plan NEXT week: week_no 1 begins on {start_date.isoformat()} (Sunday)."
            )
        return (
            "Plan the CURRENT week: week_no 1 begins on "
            f"{start_date.isoformat()} (Sunday). Today is weekday index "
            f"{israeli_weekday(today)}; schedule only on weekday indices >= that."
        )
    if payload.day_preference == "ai_pick":
        return (
            f"Pick the best single day between today ({today.isoformat()}) and "
            f"{(today + timedelta(days=6)).isoformat()}. Days in the current week use "
            "week_no 1; days after this Saturday use week_no 2."
        )
    intended = today if payload.day_preference == "today" else today + timedelta(days=1)
    return (
        f"The workout must be on {intended.isoformat()}: week_no 1, weekday index "
        f"{israeli_weekday(intended)}."
    )


def build_transient_version(agent_plan: AgentPlan, start_date: date) -> dict[str, Any]:
    """Shape a validated AgentPlan like the frontend's PlanVersion type, with
    computed dates and synthetic ids, without touching the database."""
    base = week_start(start_date)
    workouts: list[dict[str, Any]] = []
    for week in agent_plan.weeks:
        for wo in week.workouts:
            workout_date = base + timedelta(days=(week.week_no - 1) * 7 + wo.weekday)
            workouts.append(
                {
                    "id": len(workouts) + 1,
                    "week_no": week.week_no,
                    "weekday": wo.weekday,
                    "date": workout_date.isoformat(),
                    "workout_type": wo.workout_type,
                    "goal": wo.goal,
                    "how_to": wo.how_to,
                    "details": wo.details or {},
                }
            )
    workouts.sort(key=lambda w: w["date"])
    return {
        "id": 0,
        "plan_id": 0,
        "version_no": 1,
        "status": "transient",
        "source": "workout_planner",
        "structure_explanation": agent_plan.structure_explanation,
        "full_explanation": agent_plan.full_explanation,
        "change_summary": agent_plan.change_summary,
        "workout_types": [wt.model_dump() for wt in agent_plan.workout_types],
        "start_date": base.isoformat(),
        "num_weeks": max(w.week_no for w in agent_plan.weeks),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "planned_workouts": workouts,
    }


def _workout_context(
    db: Session,
    user: User,
    payload: WorkoutPlanRequest,
    today: date,
    start_date: date,
) -> dict[str, Any]:
    """Read-only context for the workout prompt (no writes, unlike the plans flow)."""
    context: dict[str, Any] = {
        "profile": plan_builder.gather_profile(user),
        "metrics": plan_builder.gather_metrics(db, user),
        "request": payload.model_dump(
            mode="json",
            exclude={"ai_model", "reasoning_effort", "client_today", "description"},
        ),
        "description": payload.description,
        "calendar": {
            "today": today.isoformat(),
            "today_weekday": israeli_weekday(today),
            "start_date_sunday": start_date.isoformat(),
            "note": _calendar_note(payload, today, start_date),
        },
    }
    if payload.use_garmin and payload.garmin_start and payload.garmin_end:
        context["activities"] = plan_builder.gather_activities_in_range(
            db, user, payload.garmin_start, payload.garmin_end
        )
        context["daily_health"] = plan_builder.gather_daily_health_in_range(
            db, user, payload.garmin_start, payload.garmin_end
        )
    return context


# --------------------------------------------------------------------------- #
# Generation (SSE; the done event carries the transient plan)
# --------------------------------------------------------------------------- #


@router.post("/generate")
async def generate_workout_stream(
    payload: WorkoutPlanRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Generate a transient workout/week, streaming agent events as SSE. The
    terminal ``done`` event carries ``workout_plan.version`` (never persisted —
    deliberately no ``plan_id``, so the client stores nothing)."""
    _require_agent()
    try:
        ai_model, effort = ai_settings.resolve(
            user, payload.ai_model, payload.reasoning_effort
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    today = _anchor_today(payload.client_today)
    start_date = _compute_start_date(payload, today)
    context = _workout_context(db, user, payload, today, start_date)

    async def gen() -> AsyncIterator[str]:
        try:
            async for event in agent_service.plan_workout_stream(context, ai_model, effort):
                if event.get("type") == "plan":
                    version = build_transient_version(event["plan"], start_date)
                    yield _sse({"type": "done", "workout_plan": {"version": version}})
                else:
                    yield _sse(event)
        except Exception as exc:  # noqa: BLE001
            yield _sse({"type": "error", "message": str(exc)})

    return StreamingResponse(gen(), media_type="text/event-stream")
