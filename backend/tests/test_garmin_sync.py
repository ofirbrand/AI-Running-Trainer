"""Comprehensive Garmin sync: a fake client, verifying ALL data points persist.

Covers the full sync path (activities + 9 daily-health methods + 12 advanced
performance methods) which the rest of the suite does not exercise. The Garmin
client and its rate-limit sleep are stubbed so the test is fast and offline.
"""
from __future__ import annotations

from datetime import date

from app.models import (
    Activity,
    DailyHealth,
    GarminConnection,
    HealthSnapshot,
    MetricObservation,
    User,
)
from app.services import garmin_service


class FakeGarmin:
    """Minimal stand-in for garminconnect.Garmin with representative payloads."""

    def get_activities_by_date(self, start, end):
        # Date the activity to the sync window so the 30-day metrics always apply.
        return [
            {
                "activityId": "a1",
                "startTimeLocal": f"{end} 06:00:00",
                "distance": 10000.0,
                "duration": 3000.0,
                "averageSpeed": 3.33,
                "activityType": {"typeKey": "running"},
                "activityName": "Morning Run",
                "averageHR": 150,
                "maxHR": 170,
                "calories": 600,
            }
        ]

    # --- daily health (9) -------------------------------------------------- #
    def get_stats(self, *a):
        return {"totalSteps": 12000}

    def get_user_summary(self, *a):
        return {
            "totalSteps": 12000,
            "restingHeartRate": 48,
            "averageStressLevel": 30,
            "bodyBatteryHighestValue": 90,
            "bodyBatteryLowestValue": 20,
        }

    def get_stats_and_body(self, *a):
        return {"weight": 70000, "bmi": 22.0}

    def get_steps_data(self, *a):
        return [{"steps": 100}, {"steps": 200}]

    def get_heart_rates(self, *a):
        return {"restingHeartRate": 48, "maxHeartRate": 180}

    def get_rhr_day(self, *a):
        return {
            "allMetrics": {"metricsMap": {"WELLNESS_RESTING_HEART_RATE": [{"value": 48}]}}
        }

    def get_sleep_data(self, *a):
        return {
            "dailySleepDTO": {
                "sleepTimeSeconds": 27000,
                "sleepScores": {"overall": {"value": 85}},
            }
        }

    def get_all_day_stress(self, *a):
        return {"avgStressLevel": 30, "maxStressLevel": 80}

    def get_lifestyle_logging_data(self, *a):
        return {"entries": []}

    # --- advanced health & performance (12) -------------------------------- #
    def get_training_readiness(self, *a):
        return [{"score": 75, "level": "READY"}]

    def get_morning_training_readiness(self, *a):
        return {"score": 70, "level": "READY"}

    def get_training_status(self, *a):
        return {
            "mostRecentTrainingLoadBalance": {
                "metricsTrainingLoadBalanceDTOMap": {"dev1": {"monthlyLoad": 800}}
            }
        }

    def get_respiration_data(self, *a):
        return {"avgWakingRespirationValue": 14}

    def get_spo2_data(self, *a):
        return {"averageSpO2": 96}

    def get_max_metrics(self, *a):
        return [{"generic": {"vo2MaxValue": 52.0, "fitnessAge": 30}}]

    def get_hrv_data(self, *a):
        return {"hrvSummary": {"lastNightAvg": 60, "status": "BALANCED"}}

    def get_fitnessage_data(self, *a):
        return {"fitnessAge": 30, "chronologicalAge": 35}

    def get_stress_data(self, *a):
        return {"avgStressLevel": 28, "maxStressLevel": 75}

    def get_lactate_threshold(self, *a, **k):
        return {"speed_and_heart_rate": {"heartRate": 165, "speed": 3.5}, "power": {}}

    def get_intensity_minutes_data(self, *a):
        return {"moderateMinutes": 30, "vigorousMinutes": 10}

    def get_running_tolerance(self, *a):
        return [{"calendarDate": "2026-06-17"}]

    # --- per-activity laps / interval splits ------------------------------- #
    def get_activity_splits(self, activity_id):
        return {
            "activityId": activity_id,
            "lapDTOs": [
                {"lapIndex": 1, "distance": 1000.0, "duration": 300.0, "averageHR": 150},
                {"lapIndex": 2, "distance": 1000.0, "duration": 290.0, "averageHR": 158},
            ],
        }


def _make_user(db):
    user = User(email="g@example.com", password_hash="x")
    db.add(user)
    db.flush()
    db.add(
        GarminConnection(
            user_id=user.id,
            garmin_email="g@example.com",
            token_dir="/tmp/none",
            status="connected",
        )
    )
    db.commit()
    db.refresh(user)
    return user


def test_sync_persists_all_data_points(db_session_factory, monkeypatch):
    monkeypatch.setattr(garmin_service.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(garmin_service, "load_client", lambda token_dir: FakeGarmin())

    db = db_session_factory()
    user = _make_user(db)

    result = garmin_service.sync_user(db, user, lookback_days=1)

    assert result["activities_synced"] == 1
    assert result["days_health_synced"] >= 1
    assert result["metrics_updated"] >= 1

    # Full raw snapshot: all 9 daily + 12 advanced methods captured for today.
    snap = db.query(HealthSnapshot).filter_by(user_id=user.id).one()
    assert len(snap.daily) == 9
    assert len(snap.advanced) == 12
    assert snap.daily["user_summary"]["totalSteps"] == 12000
    assert snap.advanced["max_metrics"][0]["generic"]["vo2MaxValue"] == 52.0
    assert snap.advanced["lactate_threshold"]["speed_and_heart_rate"]["heartRate"] == 165

    # Parsed daily-health summary derived from the same payloads.
    dh = db.query(DailyHealth).filter_by(user_id=user.id).one()
    assert dh.steps == 12000
    assert dh.resting_hr == 48
    assert dh.sleep_seconds == 27000
    assert dh.sleep_score == 85

    # Coach-facing metrics derived from the snapshot + activities (no extra calls).
    metrics = {
        m.key: m.value["value"]
        for m in db.query(MetricObservation).filter_by(user_id=user.id)
    }
    assert metrics["vo2max"] == 52.0
    assert metrics["training_load"] == 800
    assert "weekly_volume_km" in metrics
    db.close()


def test_fetch_activity_laps(db_session_factory, monkeypatch):
    monkeypatch.setattr(garmin_service.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(garmin_service, "load_client", lambda token_dir: FakeGarmin())

    db = db_session_factory()
    user = _make_user(db)
    activity = Activity(
        user_id=user.id, garmin_activity_id="a1", activity_date=date(2026, 6, 17)
    )
    db.add(activity)
    db.commit()

    laps = garmin_service.fetch_activity_laps(user, activity)
    assert laps is not None
    assert len(laps) == 2
    assert laps[0]["lapIndex"] == 1
    assert laps[1]["averageHR"] == 158

    # Disconnected accounts yield None (couldn't load) rather than an empty list.
    user.garmin.status = "disconnected"
    db.commit()
    assert garmin_service.fetch_activity_laps(user, activity) is None
    db.close()
