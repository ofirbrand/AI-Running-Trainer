"""In-process daily Garmin sync via APScheduler.

Runs while the app is running. For always-on syncing, keep the app running or
trigger the manual sync endpoint from an external scheduler (cron/launchd).
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from ..config import get_settings
from ..db import SessionLocal
from ..models import GarminConnection, User
from . import garmin_service

logger = logging.getLogger("coach.scheduler")
settings = get_settings()

_scheduler: BackgroundScheduler | None = None


def sync_all_users() -> None:
    """Sync every user that has a connected Garmin account."""
    db = SessionLocal()
    try:
        conns = db.scalars(
            select(GarminConnection).where(GarminConnection.status != "disconnected")
        ).all()
        for conn in conns:
            user = db.get(User, conn.user_id)
            if user is None:
                continue
            try:
                result = garmin_service.sync_user(db, user)
                logger.info("daily sync user=%s result=%s", user.id, result)
            except Exception as exc:  # noqa: BLE001
                logger.warning("daily sync failed user=%s: %s", user.id, exc)
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        sync_all_users,
        CronTrigger(hour=settings.daily_sync_hour, minute=0),
        id="daily_garmin_sync",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info("Daily Garmin sync scheduled for %02d:00 local", settings.daily_sync_hour)
    _scheduler = scheduler
    return scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
