"""Vercel serverless entrypoint.

Exposes the FastAPI backend as a Python function. vercel.json rewrites
``/api/(.*)`` here, and the app's routes are absolute (``/api/...``), so the
original request paths match unchanged.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.config import get_settings  # noqa: E402
from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402, F401  (Vercel serves the ASGI `app`)

# Belt and braces: Vercel's Python runtime may not fire the ASGI lifespan, so
# run the (idempotent) startup work at import time. The scheduler is disabled
# via ENABLE_SCHEDULER=false in the Vercel environment.
_settings = get_settings()
if _settings.anthropic_api_key:
    os.environ.setdefault("ANTHROPIC_API_KEY", _settings.anthropic_api_key)
init_db()
