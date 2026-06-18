"""SQLAlchemy ORM models.

Relationship overview:

    User 1─1 Profile
    User 1─1 GarminConnection
    User 1─1 UserSettings
    User 1─* MetricObservation        (current value per metric key)
    User 1─* Activity                 (synced workouts)
    User 1─* DailyHealth              (steps / sleep / hr per day)
    User 1─* TrainingPlan
        TrainingPlan 1─* PlanVersion          (draft / proposed / active / superseded)
            PlanVersion 1─* PlannedWorkout
        TrainingPlan 1─* WorkoutCompletion    (activity matched to a plan)
        TrainingPlan 1─* PlanChangeRequest    (user-requested overrides)
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    profile: Mapped["Profile"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    garmin: Mapped["GarminConnection"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    settings: Mapped["UserSettings"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    plans: Mapped[list["TrainingPlan"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)

    name: Mapped[str | None] = mapped_column(String(255))
    height_cm: Mapped[float | None] = mapped_column(Float)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    gender: Mapped[str | None] = mapped_column(String(32))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    # List of {"distance": "5K", "time": "20:30", "date": "2025-04-01"}
    personal_records: Mapped[list | None] = mapped_column(JSON, default=list)
    notes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    user: Mapped[User] = relationship(back_populates="profile")


class GarminConnection(Base):
    __tablename__ = "garmin_connections"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)

    garmin_email: Mapped[str] = mapped_column(String(255))
    token_dir: Mapped[str] = mapped_column(String(1024))
    status: Mapped[str] = mapped_column(String(32), default="connected")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_sync_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user: Mapped[User] = relationship(back_populates="garmin")


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    ai_model: Mapped[str] = mapped_column(String(128), default="claude-sonnet-4-5")
    reasoning_effort: Mapped[str] = mapped_column(String(32), default="medium")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    user: Mapped[User] = relationship(back_populates="settings")


class MetricObservation(Base):
    """Current value of a single fitness/health metric for a user.

    One row per (user, key). ``source`` records whether the value came from a
    Garmin sync or was entered/edited manually; ``measured_at`` is the date the
    value applies to and powers the "last updated on X" confirmation UX.
    """

    __tablename__ = "metric_observations"
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_metric_user_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    value: Mapped[dict | None] = mapped_column(JSON)  # {"value": ..., "unit": ...}
    source: Mapped[str] = mapped_column(String(16), default="manual")  # garmin|manual
    measured_at: Mapped[date | None] = mapped_column(Date)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    garmin_activity_id: Mapped[str] = mapped_column(String(64), index=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime)
    activity_date: Mapped[date] = mapped_column(Date, index=True)
    activity_type: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str | None] = mapped_column(String(255))
    distance_m: Mapped[float | None] = mapped_column(Float)
    duration_s: Mapped[float | None] = mapped_column(Float)
    avg_hr: Mapped[float | None] = mapped_column(Float)
    max_hr: Mapped[float | None] = mapped_column(Float)
    avg_pace_s_per_km: Mapped[float | None] = mapped_column(Float)
    calories: Mapped[float | None] = mapped_column(Float)
    raw: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "garmin_activity_id", name="uq_activity_user_gid"),
    )


class DailyHealth(Base):
    __tablename__ = "daily_health"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_health_user_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    steps: Mapped[int | None] = mapped_column(Integer)
    resting_hr: Mapped[int | None] = mapped_column(Integer)
    sleep_seconds: Mapped[int | None] = mapped_column(Integer)
    sleep_score: Mapped[int | None] = mapped_column(Integer)
    avg_stress: Mapped[int | None] = mapped_column(Integer)
    body_battery_high: Mapped[int | None] = mapped_column(Integer)
    body_battery_low: Mapped[int | None] = mapped_column(Integer)
    raw: Mapped[dict | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )


class HealthSnapshot(Base):
    """Complete raw Garmin health & performance payloads for a single date.

    Stores everything a sync pulls beyond activities: the 9 daily-health methods
    (``daily``) and the 12 advanced health & performance methods (``advanced``),
    each a ``{method_key: raw_payload}`` map. The parsed ``DailyHealth`` columns
    are derived from ``daily``; this table keeps the full fidelity for the AI
    coach and the board. One row per (user, date)."""

    __tablename__ = "health_snapshots"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_health_snapshot_user_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    daily: Mapped[dict | None] = mapped_column(JSON)  # {method_key: raw_payload}
    advanced: Mapped[dict | None] = mapped_column(JSON)  # {method_key: raw_payload}
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )


class TrainingPlan(Base):
    __tablename__ = "training_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    distance_label: Mapped[str | None] = mapped_column(String(64))
    distance_m: Mapped[float | None] = mapped_column(Float)
    target_date: Mapped[date | None] = mapped_column(Date)
    goal_type: Mapped[str | None] = mapped_column(String(16))  # time|pace|finish
    goal_value: Mapped[str | None] = mapped_column(String(64))
    is_race: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft|active|archived
    active_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("plan_versions.id", use_alter=True, name="fk_plan_active_version")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    user: Mapped[User] = relationship(back_populates="plans")
    versions: Mapped[list["PlanVersion"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        foreign_keys="PlanVersion.plan_id",
        order_by="PlanVersion.version_no",
    )
    active_version: Mapped["PlanVersion | None"] = relationship(
        foreign_keys=[active_version_id], post_update=True
    )


class PlanVersion(Base):
    __tablename__ = "plan_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("training_plans.id"), index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    # draft | proposed | active | superseded | archived
    status: Mapped[str] = mapped_column(String(16), default="draft")
    # generated | chat_edit | weekly_update | manual_update | restored
    source: Mapped[str] = mapped_column(String(24), default="generated")
    structure_explanation: Mapped[str | None] = mapped_column(Text)
    full_explanation: Mapped[str | None] = mapped_column(Text)
    change_summary: Mapped[str | None] = mapped_column(Text)
    workout_types: Mapped[list | None] = mapped_column(JSON)  # [{name, description}]
    inputs_snapshot: Mapped[dict | None] = mapped_column(JSON)
    start_date: Mapped[date | None] = mapped_column(Date)
    num_weeks: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    plan: Mapped[TrainingPlan] = relationship(
        back_populates="versions", foreign_keys=[plan_id]
    )
    planned_workouts: Mapped[list["PlannedWorkout"]] = relationship(
        back_populates="version",
        cascade="all, delete-orphan",
        order_by="PlannedWorkout.date",
    )


class PlannedWorkout(Base):
    __tablename__ = "planned_workouts"

    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("plan_versions.id"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("training_plans.id"), index=True)
    week_no: Mapped[int] = mapped_column(Integer)  # 1-based
    weekday: Mapped[int] = mapped_column(Integer)  # 0=Sunday .. 6=Saturday
    date: Mapped[date] = mapped_column(Date, index=True)
    workout_type: Mapped[str] = mapped_column(String(64))
    goal: Mapped[str | None] = mapped_column(Text)
    how_to: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JSON)  # distance/pace/hr/duration
    order_in_day: Mapped[int] = mapped_column(Integer, default=0)

    version: Mapped[PlanVersion] = relationship(back_populates="planned_workouts")


class WorkoutCompletion(Base):
    """An actual activity matched to a training plan (and optionally a planned
    workout). Recomputed by the matching service after each sync."""

    __tablename__ = "workout_completions"
    __table_args__ = (
        UniqueConstraint("plan_id", "activity_id", name="uq_completion_plan_activity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("training_plans.id"), index=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"))
    planned_workout_id: Mapped[int | None] = mapped_column(
        ForeignKey("planned_workouts.id")
    )
    performed_date: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    activity: Mapped[Activity] = relationship()


class PlanChangeRequest(Base):
    __tablename__ = "plan_change_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("training_plans.id"), index=True)
    from_version_id: Mapped[int | None] = mapped_column(ForeignKey("plan_versions.id"))
    kind: Mapped[str] = mapped_column(String(24))  # chat_edit|manual_update
    request_text: Mapped[str] = mapped_column(Text)
    applied_version_id: Mapped[int | None] = mapped_column(ForeignKey("plan_versions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
