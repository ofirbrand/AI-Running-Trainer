"""Application configuration loaded from the environment / .env file."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ directory (parent of the app package). All relative paths in the
# settings resolve against this so the app behaves the same regardless of the
# current working directory it is launched from.
BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Claude / Anthropic
    anthropic_api_key: str = ""

    # Auth
    app_secret_key: str = "dev-insecure-secret-change-me"
    access_token_expire_minutes: int = 60 * 24 * 7  # one week
    jwt_algorithm: str = "HS256"

    # Storage
    database_url: str = "sqlite:///./data/coach.sqlite3"
    garmin_tokens_dir: str = "./data/garmin_tokens"

    # AI defaults
    default_ai_model: str = "claude-sonnet-4-5"
    default_reasoning_effort: str = "medium"

    # Sync
    daily_sync_hour: int = 5
    sync_lookback_days: int = 14

    @property
    def resolved_database_url(self) -> str:
        """Return an absolute sqlite URL so the DB file location is stable."""
        url = self.database_url
        prefix = "sqlite:///"
        if url.startswith(prefix):
            raw_path = url[len(prefix):]
            path = Path(raw_path)
            if not path.is_absolute():
                path = (BACKEND_DIR / raw_path).resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            return f"{prefix}{path}"
        return url

    @property
    def resolved_tokens_dir(self) -> Path:
        path = Path(self.garmin_tokens_dir)
        if not path.is_absolute():
            path = (BACKEND_DIR / path).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
