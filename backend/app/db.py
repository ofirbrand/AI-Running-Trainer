"""Database engine, session management, and base model."""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

settings = get_settings()


def _engine_kwargs(url: str) -> dict[str, Any]:
    if url.startswith("sqlite"):
        # check_same_thread=False is required because the APScheduler background
        # job and request handlers may touch the SQLite connection from
        # different threads.
        return {"connect_args": {"check_same_thread": False}}
    # Hosted Postgres (Neon): pre_ping survives autosuspend/resume, recycle
    # avoids stale idle connections, and a small pool suits a single warm
    # serverless instance.
    return {
        "pool_pre_ping": True,
        "pool_size": 2,
        "max_overflow": 3,
        "pool_recycle": 300,
    }


engine = create_engine(
    settings.resolved_database_url,
    future=True,
    **_engine_kwargs(settings.resolved_database_url),
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Import models so they register on the metadata."""
    from . import models  # noqa: F401  (ensures models are imported)

    Base.metadata.create_all(bind=engine)
    _apply_additive_migrations()


def _apply_additive_migrations() -> None:
    """Add columns that create_all won't add to pre-existing tables."""
    inspector = inspect(engine)
    columns = {c["name"] for c in inspector.get_columns("garmin_connections")}
    if "token_data" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE garmin_connections ADD COLUMN token_data TEXT"))
