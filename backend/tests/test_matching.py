"""Tests for activity<->plan matching and weekly tracking."""
from datetime import date, datetime, timedelta

from app.models import (
    Activity,
    PlannedWorkout,
    PlanVersion,
    TrainingPlan,
    User,
    WorkoutCompletion,
)
from app.services import matching
from app.services.week import week_start


def _seed(db):
    user = User(email="m@example.com", password_hash="x")
    db.add(user)
    db.flush()

    start = week_start(date.today()) - timedelta(days=7)  # last week's Sunday
    plan = TrainingPlan(user_id=user.id, title="Test", status="active")
    db.add(plan)
    db.flush()

    version = PlanVersion(
        plan_id=plan.id, version_no=1, status="active", start_date=start, num_weeks=2
    )
    db.add(version)
    db.flush()
    plan.active_version_id = version.id

    db.add_all(
        [
            PlannedWorkout(
                version_id=version.id,
                plan_id=plan.id,
                week_no=1,
                weekday=0,
                date=start,
                workout_type="Long Run",
                goal="10 km",
            ),
            PlannedWorkout(
                version_id=version.id,
                plan_id=plan.id,
                week_no=1,
                weekday=2,
                date=start + timedelta(days=2),
                workout_type="Tempo",
                goal="5 km",
            ),
        ]
    )
    # A run completed on the long-run day.
    db.add(
        Activity(
            user_id=user.id,
            garmin_activity_id="a1",
            activity_date=start,
            activity_type="running",
            distance_m=10000,
            duration_s=3000,
            start_time=datetime.combine(start, datetime.min.time()),
        )
    )
    db.commit()
    db.refresh(plan)
    db.refresh(version)
    return user, plan, version


def test_recompute_completions_links_same_day(db_session_factory):
    db = db_session_factory()
    user, plan, version = _seed(db)

    count = matching.recompute_completions(db, user, plan, version)
    assert count == 1

    completions = db.query(WorkoutCompletion).all()
    assert len(completions) == 1
    long_run = next(p for p in version.planned_workouts if p.workout_type == "Long Run")
    assert completions[0].planned_workout_id == long_run.id
    db.close()


def test_week_tracking_statuses(db_session_factory):
    db = db_session_factory()
    user, plan, version = _seed(db)

    week1 = matching.week_tracking(db, user, version, 1)
    by_weekday = {d["weekday"]: d for d in week1["days"]}

    assert by_weekday[0]["status"] == "completed"  # planned + actual
    assert by_weekday[2]["status"] == "missed"  # planned, in the past, no actual
    assert by_weekday[1]["status"] == "rest"  # nothing planned or done
    assert len(by_weekday[0]["actual"]) == 1
    db.close()
