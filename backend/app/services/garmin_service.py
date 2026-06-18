"""Garmin Connect integration: connect (with MFA), token storage, and sync.

The ``garminconnect`` library is imported lazily so the rest of the app (and the
test suite) can run without it installed. Garmin is an *unofficial* API, so every
network call is wrapped defensively: a single failing endpoint never aborts the
whole sync, and unavailable metrics simply stay editable by hand.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import (
    Activity,
    DailyHealth,
    GarminConnection,
    HealthSnapshot,
    MetricObservation,
    User,
)

logger = logging.getLogger("coach.garmin")
settings = get_settings()

# In-memory store of half-finished MFA logins, keyed by user id. This is fine for
# a local single-process app; it is intentionally not persisted.
_pending_mfa: dict[int, dict[str, Any]] = {}

RUN_TYPES = {"running", "treadmill_running", "trail_running", "track_running", "virtual_run"}


class GarminError(Exception):
    """Raised when a Garmin operation fails in a user-meaningful way."""


class GarminAuthError(GarminError):
    pass


class MfaRequiredError(GarminError):
    pass


# --------------------------------------------------------------------------- #
# Token storage
# --------------------------------------------------------------------------- #


def token_dir_for(user_id: int) -> Path:
    path = settings.resolved_tokens_dir / str(user_id)
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    return path


# --------------------------------------------------------------------------- #
# Connection / login (with MFA)
# --------------------------------------------------------------------------- #


def connect(user_id: int, garmin_email: str, password: str, mfa_code: str | None) -> str:
    """Attempt to connect a Garmin account.

    Returns "connected" on success or "mfa_required" if a code is needed. When
    "mfa_required" is returned, call ``connect`` again with the same user and the
    ``mfa_code`` filled in.
    """
    from garminconnect import Garmin  # lazy import

    token_dir = token_dir_for(user_id)

    # Resume a pending MFA login.
    if mfa_code and user_id in _pending_mfa:
        pending = _pending_mfa[user_id]
        client = pending["client"]
        try:
            client.resume_login(pending["state"], mfa_code.strip())
        except Exception as exc:  # noqa: BLE001
            raise GarminAuthError(f"MFA verification failed: {exc}") from exc
        _persist_tokens(client, token_dir)
        _pending_mfa.pop(user_id, None)
        return "connected"

    # Fresh login attempt.
    try:
        client = Garmin(email=garmin_email, password=password, return_on_mfa=True)
        result = client.login()
    except Exception as exc:  # noqa: BLE001
        raise GarminAuthError(f"Garmin login failed: {exc}") from exc

    if isinstance(result, tuple) and result and result[0] == "needs_mfa":
        _pending_mfa[user_id] = {"client": client, "state": result[1], "email": garmin_email}
        raise MfaRequiredError("Garmin requires a multi-factor authentication code.")

    _persist_tokens(client, token_dir)
    return "connected"


def _persist_tokens(client: Any, token_dir: Path) -> None:
    try:
        garth = getattr(client, "garth", None)
        if garth is not None and hasattr(garth, "dump"):
            garth.dump(str(token_dir))
        else:
            inner = getattr(client, "client", None)
            dump = getattr(inner, "dump", None)
            if dump is None:
                raise AttributeError("Garmin client exposes neither garth.dump nor client.dump")
            dump(str(token_dir))
    except Exception as exc:  # noqa: BLE001
        raise GarminError(f"Could not save Garmin session tokens: {exc}") from exc


def load_client(token_dir: Path) -> Any:
    """Restore an authenticated Garmin client from stored tokens."""
    from garminconnect import Garmin  # lazy import

    client = Garmin()
    try:
        client.login(str(token_dir))
    except Exception as exc:  # noqa: BLE001
        raise GarminAuthError(
            "Garmin session expired or invalid; please reconnect your account."
        ) from exc
    return client


# --------------------------------------------------------------------------- #
# Sync
# --------------------------------------------------------------------------- #


def _safe(client: Any, method: str, *args: Any) -> tuple[bool, Any]:
    """Call an optional Garmin client method, swallowing errors."""
    fn = getattr(client, method, None)
    if fn is None:
        return False, None
    try:
        time.sleep(0.15)  # be gentle with the unofficial API (avoid 429s)
        return True, fn(*args)
    except Exception as exc:  # noqa: BLE001
        logger.info("garmin %s failed: %s", method, exc)
        return False, None


# --------------------------------------------------------------------------- #
# Live health & performance metrics (read-only, not persisted)
# --------------------------------------------------------------------------- #

# The two metric groups exactly as the ``garminconnect`` library documents them.
# Each tuple is (response key, client method). The order here is the display
# order on "My Board". Every method takes a single calendar date unless handled
# specially in :func:`fetch_health_metrics` below.
DAILY_HEALTH_METHODS: list[tuple[str, str]] = [
    ("stats", "get_stats"),
    ("user_summary", "get_user_summary"),
    ("stats_and_body", "get_stats_and_body"),
    ("steps", "get_steps_data"),
    ("heart_rates", "get_heart_rates"),
    ("resting_heart_rate", "get_rhr_day"),
    ("sleep", "get_sleep_data"),
    ("all_day_stress", "get_all_day_stress"),
    ("lifestyle_logging", "get_lifestyle_logging_data"),
]

ADVANCED_HEALTH_METHODS: list[tuple[str, str]] = [
    ("training_readiness", "get_training_readiness"),
    ("morning_training_readiness", "get_morning_training_readiness"),
    ("training_status", "get_training_status"),
    ("respiration", "get_respiration_data"),
    ("spo2", "get_spo2_data"),
    ("max_metrics", "get_max_metrics"),
    ("hrv", "get_hrv_data"),
    ("fitness_age", "get_fitnessage_data"),
    ("stress", "get_stress_data"),
    ("lactate_threshold", "get_lactate_threshold"),
    ("intensity_minutes", "get_intensity_minutes_data"),
    ("running_tolerance", "get_running_tolerance"),
]


def _fetch_daily_payloads(client: Any, iso: str) -> dict[str, Any]:
    """Call the 9 daily-health methods for a single calendar date."""
    out: dict[str, Any] = {}
    for key, method in DAILY_HEALTH_METHODS:
        _, out[key] = _safe(client, method, iso)
    return out


def _fetch_advanced_payloads(client: Any, iso: str, week_start: str) -> dict[str, Any]:
    """Call the 12 advanced health & performance methods.

    Two of them don't take a single calendar date: ``get_lactate_threshold`` is
    keyword-only (latest) and ``get_running_tolerance`` needs a date range.
    """
    out: dict[str, Any] = {}
    for key, method in ADVANCED_HEALTH_METHODS:
        if method == "get_lactate_threshold":
            _, out[key] = _safe(client, method)
        elif method == "get_running_tolerance":
            _, out[key] = _safe(client, method, week_start, iso)
        else:
            _, out[key] = _safe(client, method, iso)
    return out


def fetch_health_metrics(db: Session, user: User, on_date: date) -> dict[str, Any]:
    """Live-fetch the full daily-health (9) and advanced-health (12) metric sets.

    Read-only: results are returned straight to the caller and never persisted.
    Every Garmin call goes through :func:`_safe`, so an unavailable metric simply
    comes back as ``None`` instead of failing the whole request.
    """
    conn = user.garmin
    if conn is None:
        raise GarminError("No Garmin account connected.")

    try:
        client = load_client(Path(conn.token_dir))
    except GarminAuthError as exc:
        conn.status = "expired"
        conn.last_sync_error = str(exc)
        db.commit()
        raise

    iso = on_date.isoformat()
    week_start = (on_date - timedelta(days=6)).isoformat()
    return {
        "date": iso,
        "daily": _fetch_daily_payloads(client, iso),
        "advanced": _fetch_advanced_payloads(client, iso, week_start),
    }


def sync_user(db: Session, user: User, lookback_days: int | None = None) -> dict[str, Any]:
    """Pull activities, daily health, and fitness metrics for a user."""
    conn = user.garmin
    if conn is None:
        raise GarminError("No Garmin account connected.")

    lookback = lookback_days or settings.sync_lookback_days
    errors: list[str] = []
    today = date.today()
    start = today - timedelta(days=lookback)

    try:
        client = load_client(Path(conn.token_dir))
    except GarminAuthError as exc:
        conn.status = "expired"
        conn.last_sync_error = str(exc)
        db.commit()
        raise

    activities_synced = _sync_activities(db, user, client, start, today, errors)
    days_synced, advanced_today = _sync_health(
        db, user, client, min(lookback, 10), today, errors
    )
    metrics_updated = _sync_metrics(db, user, today, errors, advanced_today)

    conn.last_sync_at = datetime.now(timezone.utc)
    conn.last_sync_error = "; ".join(errors) if errors else None
    conn.status = "connected"
    db.commit()

    return {
        "activities_synced": activities_synced,
        "days_health_synced": days_synced,
        "metrics_updated": metrics_updated,
        "errors": errors,
        "last_sync_at": conn.last_sync_at,
    }


def fetch_activities_window(db: Session, user: User, start: date, end: date) -> int:
    """Pull activities for a specific date window and upsert them.

    Unlike :func:`sync_user`, this stays strictly within the requested window
    (no recent-N fallback) and only touches the activities table. Returns the
    number of newly-inserted activities.
    """
    conn = user.garmin
    if conn is None:
        raise GarminError("No Garmin account connected.")

    try:
        client = load_client(Path(conn.token_dir))
    except GarminAuthError as exc:
        conn.status = "expired"
        conn.last_sync_error = str(exc)
        db.commit()
        raise

    ok, data = _safe(
        client, "get_activities_by_date", start.isoformat(), end.isoformat()
    )
    if not ok or not data:
        return 0

    count = 0
    for raw in data:
        try:
            count += _upsert_activity(db, user, raw)
        except Exception as exc:  # noqa: BLE001
            logger.info("activity parse failed: %s", exc)
    db.commit()
    return count


def fetch_activity_laps(user: User, activity: Activity) -> list[dict[str, Any]] | None:
    """Best-effort live fetch of a single activity's lap / interval splits.

    Laps are not part of the ``get_activities_by_date`` summary payload, so they
    are pulled on demand the first time an activity is opened. Like
    :func:`fetch_health_metrics` this reads straight from Garmin and persists
    nothing. Returns ``None`` when Garmin is unavailable (disconnected, expired
    session, or the splits endpoint failed) and an empty list when the activity
    genuinely has no laps — letting the caller tell "couldn't load" from "none".
    """
    conn = user.garmin
    if conn is None or conn.status != "connected" or not activity.garmin_activity_id:
        return None
    try:
        client = load_client(Path(conn.token_dir))
    except GarminError:
        return None
    ok, data = _safe(client, "get_activity_splits", activity.garmin_activity_id)
    if not ok or not isinstance(data, dict):
        return None
    laps = data.get("lapDTOs")
    return laps if isinstance(laps, list) else []


def _sync_activities(
    db: Session, user: User, client: Any, start: date, end: date, errors: list[str]
) -> int:
    ok, data = _safe(client, "get_activities_by_date", start.isoformat(), end.isoformat())
    if not ok or not data:
        # Fall back to the most recent N activities.
        ok, data = _safe(client, "get_activities", 0, 30)
    if not ok or not data:
        errors.append("Could not fetch activities.")
        return 0

    count = 0
    for raw in data:
        try:
            count += _upsert_activity(db, user, raw)
        except Exception as exc:  # noqa: BLE001
            logger.info("activity parse failed: %s", exc)
    db.commit()
    return count


def _upsert_activity(db: Session, user: User, raw: dict[str, Any]) -> int:
    gid = str(raw.get("activityId") or raw.get("activityUUID") or "").strip()
    if not gid:
        return 0

    start_str = raw.get("startTimeLocal") or raw.get("startTimeGMT")
    start_dt: datetime | None = None
    if start_str:
        try:
            start_dt = datetime.fromisoformat(str(start_str).replace("Z", ""))
        except ValueError:
            start_dt = None
    activity_date = (start_dt or datetime.now()).date()

    distance_m = raw.get("distance")
    duration_s = raw.get("duration") or raw.get("elapsedDuration")
    avg_speed = raw.get("averageSpeed")  # m/s
    avg_pace = None
    if avg_speed:
        avg_pace = 1000.0 / avg_speed if avg_speed else None
    elif distance_m and duration_s:
        avg_pace = duration_s / (distance_m / 1000.0)

    type_key = None
    atype = raw.get("activityType")
    if isinstance(atype, dict):
        type_key = atype.get("typeKey")
    type_key = type_key or raw.get("activityTypeDTO", {}).get("typeKey") if isinstance(
        raw.get("activityTypeDTO"), dict
    ) else type_key

    existing = db.scalar(
        select(Activity).where(
            Activity.user_id == user.id, Activity.garmin_activity_id == gid
        )
    )
    target = existing or Activity(user_id=user.id, garmin_activity_id=gid)
    target.start_time = start_dt
    target.activity_date = activity_date
    target.activity_type = type_key
    target.name = raw.get("activityName")
    target.distance_m = distance_m
    target.duration_s = duration_s
    target.avg_hr = raw.get("averageHR")
    target.max_hr = raw.get("maxHR")
    target.avg_pace_s_per_km = avg_pace
    target.calories = raw.get("calories")
    target.raw = raw
    if existing is None:
        db.add(target)
        return 1
    return 0


def _sync_health(
    db: Session, user: User, client: Any, days: int, end: date, errors: list[str]
) -> tuple[int, dict[str, Any]]:
    """Pull and persist the full health & performance data set for the window.

    For each day in the window the 9 daily-health methods are fetched and stored
    as a :class:`HealthSnapshot`, and the parsed :class:`DailyHealth` summary
    columns are derived from those same payloads. The 12 advanced performance
    metrics are captured once — for ``end`` (today) — as the current-fitness
    snapshot. Returns the number of days with daily data and today's advanced
    payloads (reused by :func:`_sync_metrics` to avoid duplicate API calls).
    """
    advanced_today: dict[str, Any] = {}
    count = 0
    for i in range(days):
        cdate = end - timedelta(days=i)
        iso = cdate.isoformat()
        daily = _fetch_daily_payloads(client, iso)

        advanced: dict[str, Any] = {}
        if i == 0:
            week_start = (cdate - timedelta(days=6)).isoformat()
            advanced = _fetch_advanced_payloads(client, iso, week_start)
            advanced_today = advanced

        has_daily = any(v is not None for v in daily.values())
        has_advanced = any(v is not None for v in advanced.values())
        if has_daily or has_advanced:
            _upsert_health_snapshot(db, user.id, cdate, daily, advanced)
        if _upsert_daily_health(db, user, cdate, daily):
            count += 1

    if count == 0:
        errors.append("Could not fetch daily health data.")
    db.commit()
    return count, advanced_today


def _upsert_health_snapshot(
    db: Session,
    user_id: int,
    cdate: date,
    daily: dict[str, Any],
    advanced: dict[str, Any],
) -> None:
    existing = db.scalar(
        select(HealthSnapshot).where(
            HealthSnapshot.user_id == user_id, HealthSnapshot.date == cdate
        )
    )
    target = existing or HealthSnapshot(user_id=user_id, date=cdate)
    target.daily = daily
    # ``advanced`` is only fetched for today; don't wipe a prior snapshot's
    # advanced metrics on days where we didn't refetch them.
    if advanced:
        target.advanced = advanced
    if existing is None:
        db.add(target)


def _upsert_daily_health(
    db: Session, user: User, cdate: date, daily: dict[str, Any]
) -> bool:
    """Derive the parsed DailyHealth summary columns from raw daily payloads."""
    summary = daily.get("user_summary") or daily.get("stats")
    sleep = daily.get("sleep")

    payload: dict[str, Any] = {}
    if isinstance(summary, dict):
        payload["steps"] = summary.get("totalSteps")
        payload["resting_hr"] = summary.get("restingHeartRate")
        payload["avg_stress"] = summary.get("averageStressLevel")
        payload["body_battery_high"] = summary.get("bodyBatteryHighestValue")
        payload["body_battery_low"] = summary.get("bodyBatteryLowestValue")
        payload["summary"] = summary
    if isinstance(sleep, dict):
        dto = sleep.get("dailySleepDTO") or {}
        payload["sleep_seconds"] = dto.get("sleepTimeSeconds")
        scores = dto.get("sleepScores") or {}
        overall = scores.get("overall") if isinstance(scores, dict) else None
        if isinstance(overall, dict):
            payload["sleep_score"] = overall.get("value")

    if not payload:
        return False

    existing = db.scalar(
        select(DailyHealth).where(
            DailyHealth.user_id == user.id, DailyHealth.date == cdate
        )
    )
    target = existing or DailyHealth(user_id=user.id, date=cdate)
    if "steps" in payload:
        target.steps = payload.get("steps")
    if payload.get("resting_hr"):
        target.resting_hr = payload.get("resting_hr")
    if payload.get("sleep_seconds"):
        target.sleep_seconds = payload.get("sleep_seconds")
    if payload.get("sleep_score"):
        target.sleep_score = payload.get("sleep_score")
    if payload.get("avg_stress"):
        target.avg_stress = payload.get("avg_stress")
    if payload.get("body_battery_high"):
        target.body_battery_high = payload.get("body_battery_high")
    if payload.get("body_battery_low"):
        target.body_battery_low = payload.get("body_battery_low")
    target.raw = payload.get("summary")
    if existing is None:
        db.add(target)
    return True


def _sync_metrics(
    db: Session, user: User, today: date, errors: list[str], advanced: dict[str, Any]
) -> int:
    updated = 0

    # VO2 max and training load are derived from today's advanced snapshot, which
    # _sync_health already fetched — so there are no extra Garmin calls here.
    vo2 = _extract_vo2max(advanced.get("max_metrics"))
    if vo2:
        _upsert_metric(db, user.id, "vo2max", vo2, "ml/kg/min", today)
        updated += 1

    ts = advanced.get("training_status")
    if isinstance(ts, dict):
        load = _extract_training_load(ts)
        if load is not None:
            _upsert_metric(db, user.id, "training_load", load, "score", today)
            updated += 1

    # Resting HR from the most recent daily health row.
    recent_rhr = db.scalar(
        select(DailyHealth.resting_hr)
        .where(DailyHealth.user_id == user.id, DailyHealth.resting_hr.is_not(None))
        .order_by(DailyHealth.date.desc())
    )
    if recent_rhr:
        _upsert_metric(db, user.id, "resting_hr", recent_rhr, "bpm", today)
        updated += 1

    # Computed metrics from synced activities.
    runs = list(
        db.scalars(
            select(Activity).where(
                Activity.user_id == user.id,
                Activity.activity_date >= today - timedelta(days=30),
            )
        )
    )
    run_only = [a for a in runs if (a.activity_type or "").lower() in RUN_TYPES]
    if run_only:
        longest = max((a.distance_m or 0) for a in run_only)
        if longest:
            _upsert_metric(db, user.id, "longest_run_30d_m", round(longest), "m", today)
            updated += 1
        last7 = [
            a for a in run_only if a.activity_date >= today - timedelta(days=7)
        ]
        weekly_km = round(sum((a.distance_m or 0) for a in last7) / 1000.0, 1)
        _upsert_metric(db, user.id, "weekly_volume_km", weekly_km, "km", today)
        updated += 1

    db.commit()
    return updated


def _extract_vo2max(data: Any) -> float | None:
    if isinstance(data, list) and data:
        data = data[0]
    if isinstance(data, dict):
        generic = data.get("generic") or {}
        if isinstance(generic, dict) and generic.get("vo2MaxValue"):
            return float(generic["vo2MaxValue"])
        if data.get("vo2MaxValue"):
            return float(data["vo2MaxValue"])
    return None


def _extract_training_load(ts: dict[str, Any]) -> float | None:
    bal = ts.get("mostRecentTrainingLoadBalance") or {}
    metrics = bal.get("metricsTrainingLoadBalanceDTOMap") or {}
    if isinstance(metrics, dict):
        for entry in metrics.values():
            if isinstance(entry, dict) and entry.get("monthlyLoad") is not None:
                return float(entry["monthlyLoad"])
    return None


def _upsert_metric(
    db: Session, user_id: int, key: str, value: Any, unit: str | None, measured_at: date
) -> None:
    existing = db.scalar(
        select(MetricObservation).where(
            MetricObservation.user_id == user_id, MetricObservation.key == key
        )
    )
    target = existing or MetricObservation(user_id=user_id, key=key)
    target.value = {"value": value, "unit": unit}
    target.source = "garmin"
    target.measured_at = measured_at
    if existing is None:
        db.add(target)
