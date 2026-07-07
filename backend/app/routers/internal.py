"""Internal endpoints for external schedulers (Vercel Cron).

Locally the in-process APScheduler handles the daily sync and CRON_SECRET is
unset, so this endpoint stays disabled (503).
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Header, HTTPException, status

from ..services import scheduler

router = APIRouter(prefix="/api/internal", tags=["internal"])


@router.get("/daily-sync")
def daily_sync(authorization: str | None = Header(None)) -> dict[str, str]:
    """Run the daily Garmin sync for all connected users.

    Vercel Cron invokes this with ``Authorization: Bearer $CRON_SECRET``.
    """
    secret = os.getenv("CRON_SECRET", "")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cron endpoint not configured.",
        )
    if authorization != f"Bearer {secret}":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized."
        )
    scheduler.sync_all_users()
    return {"status": "ok"}
