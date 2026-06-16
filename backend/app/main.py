"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import init_db
from .routers import auth, garmin, plans, profile, settings as settings_router, tracking
from .services import scheduler

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Make the API key visible to the Claude Agent SDK (which reads os.environ).
    if settings.anthropic_api_key:
        os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)
    init_db()
    scheduler.start_scheduler()
    try:
        yield
    finally:
        scheduler.shutdown_scheduler()


app = FastAPI(title="AI Running Coach", version="0.1.0", lifespan=lifespan)

# The Vite dev server proxies /api, so CORS is mostly a convenience for direct use.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(garmin.router)
app.include_router(plans.router)
app.include_router(tracking.router)
app.include_router(settings_router.router)


@app.get("/api/health")
def health() -> dict[str, object]:
    from .services import agent_service

    return {"status": "ok", "ai_available": agent_service.is_available()}
