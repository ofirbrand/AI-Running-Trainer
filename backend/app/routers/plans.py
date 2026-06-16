"""Training plan creation, review, approval, chat edits, and updates."""
from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..models import (
    PlanChangeRequest,
    PlannedWorkout,
    PlanVersion,
    Profile,
    TrainingPlan,
    User,
)
from ..schemas import (
    ChatMessageOut,
    ConfirmChangesIn,
    ManualUpdateIn,
    MetricOut,
    PlanDetail,
    PlanInputs,
    PlanSummary,
    PlanVersionOut,
    ProfileOut,
    WeeklyUpdateResult,
)
from ..services import agent_service, garmin_service, matching, plan_builder

router = APIRouter(prefix="/api/plans", tags=["plans"])

NO_CHANGE = "NO_CHANGE_NEEDED"

# Maps plan-form fields to the metric keys used for prefill.
PREFILL_FIELDS = {
    "vo2max": "vo2max",
    "resting_hr": "resting_hr",
    "max_hr": "max_hr",
    "threshold_hr": "threshold_hr",
    "training_load": "training_load",
    "current_weekly_volume": "weekly_volume",
    "training_frequency_days": "training_frequency_days",
    "experience_level": "experience_level",
}


class ChatHistoryIn(BaseModel):
    messages: list[ChatMessageOut]


class PrefillOut(BaseModel):
    profile: ProfileOut
    metrics: list[MetricOut]
    prefill: dict[str, Any]
    has_previous_plan: bool


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _get_plan(db: Session, user: User, plan_id: int) -> TrainingPlan:
    plan = db.get(TrainingPlan, plan_id)
    if plan is None or plan.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found.")
    return plan


def _get_version(db: Session, plan: TrainingPlan, version_id: int) -> PlanVersion:
    version = db.get(PlanVersion, version_id)
    if version is None or version.plan_id != plan.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found.")
    return version


def _settings(user: User) -> tuple[str, str]:
    if user.settings is not None:
        return user.settings.ai_model, user.settings.reasoning_effort
    return "claude-sonnet-4-5", "medium"


def _require_agent() -> None:
    if not agent_service.is_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI is not configured. Set ANTHROPIC_API_KEY in your .env.",
        )


def _latest_reviewable_version(plan: TrainingPlan) -> PlanVersion | None:
    if plan.active_version is not None:
        return plan.active_version
    if plan.versions:
        return plan.versions[-1]
    return None


def _calendar_for(version: PlanVersion) -> tuple[date, int]:
    return (version.start_date or date.today(), version.num_weeks or 1)


# --------------------------------------------------------------------------- #
# Listing & prefill
# --------------------------------------------------------------------------- #


@router.get("", response_model=list[PlanSummary])
def list_plans(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[TrainingPlan]:
    return list(
        db.scalars(
            select(TrainingPlan)
            .where(TrainingPlan.user_id == user.id)
            .order_by(TrainingPlan.created_at.desc())
        )
    )


@router.get("/prefill", response_model=PrefillOut)
def prefill(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> PrefillOut:
    profile = user.profile or Profile(user_id=user.id, personal_records=[])
    metrics = plan_builder.gather_metrics(db, user)

    prefill_map: dict[str, Any] = {}
    for field, key in PREFILL_FIELDS.items():
        if key in metrics:
            prefill_map[field] = metrics[key]
    # longest run: stored in metres, the form wants km.
    if "longest_run_30d_m" in metrics:
        m = dict(metrics["longest_run_30d_m"])
        if isinstance(m.get("value"), (int, float)):
            m["value"] = round(m["value"] / 1000.0, 2)
        prefill_map["longest_run_last_month_km"] = m

    metric_list = [
        MetricOut(
            key=k,
            value=v.get("value"),
            unit=v.get("unit"),
            source=v.get("source"),
            measured_at=v.get("measured_at"),
        )
        for k, v in metrics.items()
    ]
    has_prev = (
        db.scalar(select(TrainingPlan.id).where(TrainingPlan.user_id == user.id)) is not None
    )
    return PrefillOut(
        profile=ProfileOut.model_validate(profile),
        metrics=metric_list,
        prefill=prefill_map,
        has_previous_plan=has_prev,
    )


# --------------------------------------------------------------------------- #
# Create / generate
# --------------------------------------------------------------------------- #


@router.post("", response_model=PlanDetail, status_code=status.HTTP_201_CREATED)
async def create_plan(
    inputs: PlanInputs,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TrainingPlan:
    _require_agent()
    plan_builder.save_input_metrics(db, user, inputs)

    plan = TrainingPlan(
        user_id=user.id,
        title=inputs.title or f"{inputs.distance_label} plan",
        distance_label=inputs.distance_label,
        distance_m=inputs.distance_m,
        target_date=inputs.target_date,
        goal_type=inputs.goal_type,
        goal_value=inputs.goal_value,
        is_race=inputs.is_race,
        status="draft",
    )
    db.add(plan)
    db.flush()

    start_date, num_weeks = plan_builder.compute_calendar(inputs.target_date)
    context = plan_builder.build_base_context(db, user)

    # Activity history is opt-in: only inject activities the user asked for.
    activities: list[dict[str, Any]] = []
    if (
        inputs.include_activity_history
        and inputs.activity_history_start
        and inputs.activity_history_end
    ):
        conn = user.garmin
        if conn is not None and conn.status != "disconnected":
            try:
                await run_in_threadpool(
                    garmin_service.fetch_activities_window,
                    db,
                    user,
                    inputs.activity_history_start,
                    inputs.activity_history_end,
                )
            except (garmin_service.GarminError, garmin_service.GarminAuthError):
                pass  # best-effort; fall back to whatever is already stored
        activities = plan_builder.gather_activities_in_range(
            db, user, inputs.activity_history_start, inputs.activity_history_end
        )
    context["activities"] = activities

    context.update(
        {
            "inputs": inputs.model_dump(mode="json"),
            "start_date": start_date.isoformat(),
            "num_weeks": num_weeks,
            "target_date": inputs.target_date.isoformat(),
        }
    )
    ai_model, effort = _settings(user)
    agent_plan = await agent_service.generate(context, ai_model, effort)

    plan_builder.materialize_version(
        db,
        plan,
        agent_plan,
        start_date=start_date,
        num_weeks=num_weeks,
        source="generated",
        status="draft",
        inputs_snapshot=inputs.model_dump(mode="json"),
    )
    db.commit()
    db.refresh(plan)
    return plan


# --------------------------------------------------------------------------- #
# Read
# --------------------------------------------------------------------------- #


@router.get("/{plan_id}", response_model=PlanDetail)
def get_plan(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TrainingPlan:
    return _get_plan(db, user, plan_id)


@router.get("/{plan_id}/versions/{version_id}", response_model=PlanVersionOut)
def get_version(
    plan_id: int,
    version_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlanVersion:
    plan = _get_plan(db, user, plan_id)
    return _get_version(db, plan, version_id)


# --------------------------------------------------------------------------- #
# Approve / activate
# --------------------------------------------------------------------------- #


@router.post("/{plan_id}/versions/{version_id}/approve", response_model=PlanDetail)
def approve_version(
    plan_id: int,
    version_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TrainingPlan:
    plan = _get_plan(db, user, plan_id)
    version = _get_version(db, plan, version_id)
    _activate(db, plan, version)
    db.commit()
    matching.recompute_completions(db, user, plan, version)
    db.refresh(plan)
    return plan


def _activate(db: Session, plan: TrainingPlan, version: PlanVersion) -> None:
    for v in plan.versions:
        if v.id != version.id and v.status == "active":
            v.status = "superseded"
    version.status = "active"
    plan.active_version_id = version.id
    plan.status = "active"


# --------------------------------------------------------------------------- #
# Chat edit (request changes in natural language)
# --------------------------------------------------------------------------- #


@router.post("/{plan_id}/chat", response_model=ChatMessageOut)
async def chat(
    plan_id: int,
    payload: ChatHistoryIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatMessageOut:
    _require_agent()
    plan = _get_plan(db, user, plan_id)
    version = _latest_reviewable_version(plan)
    context = {
        "current_plan": plan_builder.current_plan_to_dict(version) if version else {},
        "inputs": version.inputs_snapshot if version else {},
    }
    ai_model, _ = _settings(user)
    reply = await agent_service.chat_reply(
        [m.model_dump() for m in payload.messages], context, ai_model
    )
    return ChatMessageOut(role="assistant", content=reply)


@router.post("/{plan_id}/confirm-changes", response_model=WeeklyUpdateResult)
async def confirm_changes(
    plan_id: int,
    payload: ConfirmChangesIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WeeklyUpdateResult:
    _require_agent()
    plan = _get_plan(db, user, plan_id)
    base = _latest_reviewable_version(plan)
    if base is None:
        raise HTTPException(status_code=400, detail="No plan version to revise.")

    for text in payload.requests:
        db.add(
            PlanChangeRequest(
                plan_id=plan.id, from_version_id=base.id, kind="chat_edit", request_text=text
            )
        )

    start_date, num_weeks = _calendar_for(base)
    context = plan_builder.build_base_context(db, user)
    context.update(
        {
            "inputs": base.inputs_snapshot or {},
            "current_plan": plan_builder.current_plan_to_dict(base),
            "change_requests": payload.requests,
            "start_date": start_date.isoformat(),
            "num_weeks": num_weeks,
            "target_date": plan.target_date.isoformat() if plan.target_date else None,
        }
    )
    ai_model, effort = _settings(user)
    agent_plan = await agent_service.regenerate_with_changes(context, ai_model, effort)
    new_version = plan_builder.materialize_version(
        db,
        plan,
        agent_plan,
        start_date=start_date,
        num_weeks=num_weeks,
        source="chat_edit",
        status="proposed",
        inputs_snapshot=base.inputs_snapshot,
    )
    db.commit()
    return WeeklyUpdateResult(
        update_recommended=True,
        proposed_version_id=new_version.id,
        change_summary=agent_plan.change_summary,
        message="Revised plan ready for review.",
    )


# --------------------------------------------------------------------------- #
# Updates: weekly review + manual change
# --------------------------------------------------------------------------- #


@router.post("/{plan_id}/weekly-update", response_model=WeeklyUpdateResult)
async def weekly_update(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WeeklyUpdateResult:
    _require_agent()
    plan = _get_plan(db, user, plan_id)
    base = plan.active_version or _latest_reviewable_version(plan)
    if base is None:
        raise HTTPException(status_code=400, detail="No active plan to review.")

    start_date, num_weeks = _calendar_for(base)
    progress = matching.progress_summary(db, user, base)
    context = plan_builder.build_base_context(db, user)
    context.update(
        {
            "inputs": base.inputs_snapshot or {},
            "current_plan": plan_builder.current_plan_to_dict(base),
            "progress": progress,
            "start_date": start_date.isoformat(),
            "num_weeks": num_weeks,
            "target_date": plan.target_date.isoformat() if plan.target_date else None,
            "current_week": matching.current_week_no(base),
        }
    )
    ai_model, effort = _settings(user)
    agent_plan = await agent_service.weekly_review(context, ai_model, effort)

    summary = (agent_plan.change_summary or "").strip()
    if summary == NO_CHANGE or not summary:
        return WeeklyUpdateResult(
            update_recommended=False,
            change_summary=None,
            message="Your plan is on track — no changes recommended this week.",
        )

    new_version = plan_builder.materialize_version(
        db,
        plan,
        agent_plan,
        start_date=start_date,
        num_weeks=num_weeks,
        source="weekly_update",
        status="proposed",
        inputs_snapshot=base.inputs_snapshot,
    )
    db.commit()
    return WeeklyUpdateResult(
        update_recommended=True,
        proposed_version_id=new_version.id,
        change_summary=summary,
        message="A plan update is recommended.",
    )


@router.post("/{plan_id}/manual-update", response_model=WeeklyUpdateResult)
async def manual_update(
    plan_id: int,
    payload: ManualUpdateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WeeklyUpdateResult:
    _require_agent()
    plan = _get_plan(db, user, plan_id)
    base = plan.active_version or _latest_reviewable_version(plan)
    if base is None:
        raise HTTPException(status_code=400, detail="No plan to update.")

    db.add(
        PlanChangeRequest(
            plan_id=plan.id,
            from_version_id=base.id,
            kind="manual_update",
            request_text=payload.request_text,
        )
    )
    start_date, num_weeks = _calendar_for(base)
    context = plan_builder.build_base_context(db, user)
    context.update(
        {
            "inputs": base.inputs_snapshot or {},
            "current_plan": plan_builder.current_plan_to_dict(base),
            "request_text": payload.request_text,
            "start_date": start_date.isoformat(),
            "num_weeks": num_weeks,
            "target_date": plan.target_date.isoformat() if plan.target_date else None,
            "current_week": matching.current_week_no(base),
        }
    )
    ai_model, effort = _settings(user)
    agent_plan = await agent_service.manual_update(context, ai_model, effort)
    new_version = plan_builder.materialize_version(
        db,
        plan,
        agent_plan,
        start_date=start_date,
        num_weeks=num_weeks,
        source="manual_update",
        status="proposed",
        inputs_snapshot=base.inputs_snapshot,
    )
    db.commit()
    return WeeklyUpdateResult(
        update_recommended=True,
        proposed_version_id=new_version.id,
        change_summary=agent_plan.change_summary,
        message="Updated plan ready for review.",
    )


# --------------------------------------------------------------------------- #
# Restore a previous version
# --------------------------------------------------------------------------- #


@router.post("/{plan_id}/versions/{version_id}/restore", response_model=PlanDetail)
def restore_version(
    plan_id: int,
    version_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TrainingPlan:
    plan = _get_plan(db, user, plan_id)
    source_version = _get_version(db, plan, version_id)

    clone = PlanVersion(
        plan_id=plan.id,
        version_no=plan_builder.next_version_no(plan),
        status="draft",
        source="restored",
        structure_explanation=source_version.structure_explanation,
        full_explanation=source_version.full_explanation,
        change_summary=f"Restored from version {source_version.version_no}.",
        workout_types=source_version.workout_types,
        inputs_snapshot=source_version.inputs_snapshot,
        start_date=source_version.start_date,
        num_weeks=source_version.num_weeks,
    )
    db.add(clone)
    db.flush()
    for pw in source_version.planned_workouts:
        db.add(
            PlannedWorkout(
                version_id=clone.id,
                plan_id=plan.id,
                week_no=pw.week_no,
                weekday=pw.weekday,
                date=pw.date,
                workout_type=pw.workout_type,
                goal=pw.goal,
                how_to=pw.how_to,
                details=pw.details,
            )
        )
    _activate(db, plan, clone)
    db.commit()
    matching.recompute_completions(db, user, plan, clone)
    db.refresh(plan)
    return plan
