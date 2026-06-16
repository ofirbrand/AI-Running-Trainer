"""Garmin connection, sync, and metric endpoints."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import get_db
from ..models import Activity, GarminConnection, MetricObservation, User
from ..schemas import (
    ActivityDetail,
    ActivityFetchIn,
    ActivityFetchResult,
    ActivityOut,
    GarminConnectIn,
    GarminStatus,
    MetricIn,
    MetricOut,
    SyncResult,
)
from ..services import garmin_service

router = APIRouter(prefix="/api/garmin", tags=["garmin"])


@router.get("/status", response_model=GarminStatus)
def get_status(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> GarminStatus:
    conn = user.garmin
    if conn is None:
        return GarminStatus(connected=False)
    return GarminStatus(
        connected=conn.status == "connected",
        garmin_email=conn.garmin_email,
        status=conn.status,
        last_sync_at=conn.last_sync_at,
        last_sync_error=conn.last_sync_error,
    )


@router.post("/connect")
def connect(
    payload: GarminConnectIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        result = garmin_service.connect(
            user.id, payload.garmin_email, payload.password, payload.mfa_code
        )
    except garmin_service.MfaRequiredError:
        return {"mfa_required": True, "detail": "Enter the code from your authenticator."}
    except garmin_service.GarminAuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except garmin_service.GarminError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    if result != "connected":
        return {"mfa_required": True}

    token_dir = str(garmin_service.token_dir_for(user.id))
    conn = user.garmin
    if conn is None:
        conn = GarminConnection(user_id=user.id)
        db.add(conn)
    conn.garmin_email = payload.garmin_email
    conn.token_dir = token_dir
    conn.status = "connected"
    conn.last_sync_error = None
    db.commit()

    # Best-effort initial sync so the create-plan form has data immediately.
    result_payload: dict[str, Any] = {"connected": True}
    try:
        sync = garmin_service.sync_user(db, user)
        result_payload["sync"] = SyncResult(**sync).model_dump()
    except Exception as exc:  # noqa: BLE001
        result_payload["sync_error"] = str(exc)
    return result_payload


@router.post("/disconnect", response_model=GarminStatus)
def disconnect(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> GarminStatus:
    conn = user.garmin
    if conn is not None:
        conn.status = "disconnected"
        db.commit()
    return GarminStatus(connected=False)


@router.post("/sync", response_model=SyncResult)
def sync_now(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> SyncResult:
    if user.garmin is None or user.garmin.status == "disconnected":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Garmin account connected.",
        )
    try:
        result = garmin_service.sync_user(db, user)
    except garmin_service.GarminAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    except garmin_service.GarminError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return SyncResult(**result)


def _query_activities(
    db: Session,
    user: User,
    start: date | None = None,
    end: date | None = None,
    limit: int | None = None,
) -> list[Activity]:
    stmt = select(Activity).where(Activity.user_id == user.id)
    if start is not None:
        stmt = stmt.where(Activity.activity_date >= start)
    if end is not None:
        stmt = stmt.where(Activity.activity_date <= end)
    stmt = stmt.order_by(
        Activity.activity_date.desc(),
        Activity.start_time.desc(),
        Activity.id.desc(),
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt))


@router.get("/activities", response_model=list[ActivityOut])
def list_activities(
    start: date | None = None,
    end: date | None = None,
    limit: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ActivityOut]:
    """Return previously-synced activities from the local DB, newest-first.

    Reads only from storage, so it works even when Garmin is disconnected.
    """
    rows = _query_activities(db, user, start=start, end=end, limit=limit)
    return [ActivityOut.model_validate(a) for a in rows]


@router.post("/activities/fetch", response_model=ActivityFetchResult)
def fetch_activities(
    payload: ActivityFetchIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ActivityFetchResult:
    """Pull activities for a date window from Garmin, then return that window."""
    if user.garmin is None or user.garmin.status == "disconnected":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Garmin account connected.",
        )
    try:
        fetched = garmin_service.fetch_activities_window(
            db, user, payload.start, payload.end
        )
    except garmin_service.GarminAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    except garmin_service.GarminError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    rows = _query_activities(db, user, start=payload.start, end=payload.end)
    return ActivityFetchResult(
        fetched=fetched,
        activities=[ActivityOut.model_validate(a) for a in rows],
    )


@router.get("/activities/{activity_id}", response_model=ActivityDetail)
def get_activity(
    activity_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ActivityDetail:
    """Return the full stored data for a single activity (including raw payload)."""
    act = db.get(Activity, activity_id)
    if act is None or act.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found."
        )
    return ActivityDetail.model_validate(act)


@router.get("/metrics", response_model=list[MetricOut])
def list_metrics(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[MetricOut]:
    rows = db.scalars(
        select(MetricObservation).where(MetricObservation.user_id == user.id)
    )
    out = []
    for m in rows:
        value = m.value.get("value") if isinstance(m.value, dict) else m.value
        unit = m.value.get("unit") if isinstance(m.value, dict) else None
        out.append(
            MetricOut(
                key=m.key,
                value=value,
                unit=unit,
                source=m.source,
                measured_at=m.measured_at,
                updated_at=m.updated_at,
            )
        )
    return out


@router.put("/metrics", response_model=MetricOut)
def upsert_metric(
    payload: MetricIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MetricOut:
    existing = db.scalar(
        select(MetricObservation).where(
            MetricObservation.user_id == user.id, MetricObservation.key == payload.key
        )
    )
    target = existing or MetricObservation(user_id=user.id, key=payload.key)
    target.value = {"value": payload.value, "unit": payload.unit}
    target.source = "manual"
    target.measured_at = payload.measured_at or date.today()
    target.confirmed_at = datetime.now(timezone.utc)
    if existing is None:
        db.add(target)
    db.commit()
    db.refresh(target)
    return MetricOut(
        key=target.key,
        value=payload.value,
        unit=payload.unit,
        source=target.source,
        measured_at=target.measured_at,
        updated_at=target.updated_at,
    )
