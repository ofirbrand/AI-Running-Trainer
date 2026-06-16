"""Pydantic schemas for API requests/responses and AI plan validation."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

# --------------------------------------------------------------------------- #
# Auth & profile
# --------------------------------------------------------------------------- #


class PersonalRecord(BaseModel):
    distance: str
    time: str | None = None
    date: str | None = None


class ProfileIn(BaseModel):
    name: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    gender: str | None = None
    date_of_birth: date | None = None
    personal_records: list[PersonalRecord] = Field(default_factory=list)
    notes: str | None = None


class ProfileOut(ProfileIn):
    model_config = ConfigDict(from_attributes=True)
    updated_at: datetime | None = None


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    profile: ProfileIn = Field(default_factory=ProfileIn)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    created_at: datetime


# --------------------------------------------------------------------------- #
# Garmin
# --------------------------------------------------------------------------- #


class GarminConnectIn(BaseModel):
    garmin_email: str
    password: str
    mfa_code: str | None = None


class GarminStatus(BaseModel):
    connected: bool
    garmin_email: str | None = None
    status: str | None = None
    last_sync_at: datetime | None = None
    last_sync_error: str | None = None


class MfaRequired(BaseModel):
    mfa_required: Literal[True] = True
    detail: str = "Multi-factor authentication code required."


class SyncResult(BaseModel):
    activities_synced: int = 0
    days_health_synced: int = 0
    metrics_updated: int = 0
    errors: list[str] = Field(default_factory=list)
    last_sync_at: datetime | None = None


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #


class MetricOut(BaseModel):
    key: str
    value: Any = None
    unit: str | None = None
    source: str
    measured_at: date | None = None
    updated_at: datetime | None = None


class MetricIn(BaseModel):
    key: str
    value: Any = None
    unit: str | None = None
    measured_at: date | None = None


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #


class SettingsIn(BaseModel):
    ai_model: str
    reasoning_effort: Literal["minimal", "low", "medium", "high"]


class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ai_model: str
    reasoning_effort: str


# --------------------------------------------------------------------------- #
# Plan creation inputs (the create-plan form)
# --------------------------------------------------------------------------- #


class PlanInputs(BaseModel):
    """Everything the user provides (or confirms) to generate a plan."""

    title: str | None = None
    distance_label: str  # e.g. "10K", "Half Marathon", "Marathon", "5K"
    distance_m: float | None = None
    target_date: date
    goal_type: Literal["time", "pace", "finish"] = "finish"
    goal_value: str | None = None
    is_race: bool = False

    current_weekly_volume: str | None = None  # "40 km" / "25 mi" / "5 hours"
    training_frequency_days: int | None = None
    experience_level: str | None = None  # beginner/intermediate/advanced or years
    days_available: list[str] = Field(default_factory=list)  # weekday names
    time_per_session: str | None = None
    time_per_session_by_day: dict[str, str] = Field(default_factory=dict)
    preferred_long_run_day: str | None = None
    strength_work: str | None = None  # willingness + gym access
    other_sports: str | None = None
    mobility_prehab: str | None = None

    # Garmin-derived (or manually entered) metrics
    longest_run_last_month_km: float | None = None
    vo2max: float | None = None
    resting_hr: int | None = None
    max_hr: int | None = None
    threshold_hr: int | None = None
    training_load: str | None = None

    # Optional Garmin activity history to factor into the plan.
    include_activity_history: bool = False
    activity_history_start: date | None = None
    activity_history_end: date | None = None

    extra_notes: str | None = None

    @field_validator("target_date")
    @classmethod
    def target_in_future(cls, v: date) -> date:
        if v <= date.today():
            raise ValueError("target_date must be in the future")
        return v

    @model_validator(mode="after")
    def check_activity_window(self) -> "PlanInputs":
        if self.include_activity_history:
            if self.activity_history_start is None or self.activity_history_end is None:
                raise ValueError(
                    "activity_history_start and activity_history_end are required "
                    "when include_activity_history is true"
                )
            if self.activity_history_start > self.activity_history_end:
                raise ValueError(
                    "activity_history_start must be on or before activity_history_end"
                )
        return self


# --------------------------------------------------------------------------- #
# AI-generated plan validation (strict)
# --------------------------------------------------------------------------- #


class AgentWorkout(BaseModel):
    weekday: int = Field(ge=0, le=6)  # 0=Sunday .. 6=Saturday
    workout_type: str
    goal: str
    how_to: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class AgentWeek(BaseModel):
    week_no: int = Field(ge=1)
    focus: str | None = None
    workouts: list[AgentWorkout] = Field(default_factory=list)


class AgentWorkoutType(BaseModel):
    name: str
    description: str


class AgentPlan(BaseModel):
    """Structured plan the AI must return via the ``submit_plan`` tool."""

    structure_explanation: str
    full_explanation: str
    change_summary: str | None = None
    workout_types: list[AgentWorkoutType] = Field(default_factory=list)
    weeks: list[AgentWeek]

    @field_validator("weeks")
    @classmethod
    def weeks_not_empty(cls, v: list[AgentWeek]) -> list[AgentWeek]:
        if not v:
            raise ValueError("plan must contain at least one week")
        return v


# --------------------------------------------------------------------------- #
# Plan output schemas
# --------------------------------------------------------------------------- #


class PlannedWorkoutOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    week_no: int
    weekday: int
    date: date
    workout_type: str
    goal: str | None = None
    how_to: str | None = None
    details: dict[str, Any] | None = None


class PlanVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    plan_id: int
    version_no: int
    status: str
    source: str
    structure_explanation: str | None = None
    full_explanation: str | None = None
    change_summary: str | None = None
    workout_types: list[dict[str, Any]] | None = None
    start_date: date | None = None
    num_weeks: int | None = None
    created_at: datetime
    planned_workouts: list[PlannedWorkoutOut] = Field(default_factory=list)


class PlanSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    distance_label: str | None = None
    target_date: date | None = None
    goal_type: str | None = None
    goal_value: str | None = None
    is_race: bool
    status: str
    active_version_id: int | None = None
    created_at: datetime


class PlanDetail(PlanSummary):
    active_version: PlanVersionOut | None = None
    versions: list[PlanVersionOut] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Tracking
# --------------------------------------------------------------------------- #


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    activity_date: date
    activity_type: str | None = None
    name: str | None = None
    distance_m: float | None = None
    duration_s: float | None = None
    avg_hr: float | None = None
    avg_pace_s_per_km: float | None = None


class ActivityFetchIn(BaseModel):
    start: date
    end: date

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v: date, info) -> date:
        start = info.data.get("start")
        if start is not None and v < start:
            raise ValueError("end must be on or after start")
        return v


class ActivityFetchResult(BaseModel):
    fetched: int = 0
    activities: list[ActivityOut] = Field(default_factory=list)


class ActivityDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    garmin_activity_id: str | None = None
    start_time: datetime | None = None
    activity_date: date
    activity_type: str | None = None
    name: str | None = None
    distance_m: float | None = None
    duration_s: float | None = None
    avg_hr: float | None = None
    max_hr: float | None = None
    avg_pace_s_per_km: float | None = None
    calories: float | None = None
    raw: dict[str, Any] | None = None
    created_at: datetime | None = None


class TrackingDay(BaseModel):
    date: date
    weekday: int
    weekday_name: str
    planned: list[PlannedWorkoutOut] = Field(default_factory=list)
    actual: list[ActivityOut] = Field(default_factory=list)
    status: Literal["completed", "missed", "rest", "upcoming", "extra"] = "upcoming"


class TrackingWeek(BaseModel):
    plan_id: int
    version_id: int
    week_no: int
    num_weeks: int
    current_week: int
    week_start: date
    week_end: date
    days: list[TrackingDay]


# --------------------------------------------------------------------------- #
# Change requests / updates
# --------------------------------------------------------------------------- #


class ChatMessageIn(BaseModel):
    message: str


class ChatMessageOut(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ConfirmChangesIn(BaseModel):
    requests: list[str] = Field(default_factory=list)


class ManualUpdateIn(BaseModel):
    request_text: str


class WeeklyUpdateResult(BaseModel):
    update_recommended: bool
    proposed_version_id: int | None = None
    change_summary: str | None = None
    message: str | None = None
