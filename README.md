# AI Running Trainer

A local, web-based AI running coach. It connects to your Garmin account, pulls
your activities and health data, and uses Claude (via the Claude Agent SDK) to
build, track, and continuously update a personalized running training plan.

> Runs entirely on your own machine. Your Garmin tokens and data live in a local
> SQLite database and local token files — nothing is sent anywhere except to
> Garmin Connect (to read your data) and to the Anthropic API (to generate plans).

## Features

- **Profile & onboarding** — register, capture your runner profile (PRs, height,
  weight, etc.), and connect a single Garmin account (with MFA support).
- **Garmin sync** — pull activities, daily health (steps, sleep, heart rate) and
  fitness metrics (VO2 max, resting/threshold HR, training load…). Manual "Sync
  now" plus an automatic daily sync.
- **AI plan builder** — a multi-step form pre-filled from your Garmin metrics
  (with "last updated on…" dates) generates a full periodized plan: weekly
  workout table (Israeli weeks, Sunday-first), workout goals, and how-to notes.
- **Review & refine** — approve a plan, or open a chat to request changes in
  natural language and regenerate.
- **Tracking** — current-week table of planned vs. actually-completed workouts,
  matched from your synced activities.
- **Updates & versions** — weekly auto-review, free-text manual updates, and a
  side-by-side compare with the ability to restore any previous version.
- **Settings** — choose the Claude model and reasoning effort.

## Requirements

- **Python 3.10+** (tested on 3.13)
- **Node.js 18+** (tested on 24) — also required by the Claude Agent SDK
- An **Anthropic API key**
- A **Garmin Connect** account

## Quick start

```bash
git clone git@github.com:ofirbrand/AI-Running-Trainer.git
cd AI-Running-Trainer
cp .env.example .env          # then edit .env and set ANTHROPIC_API_KEY + APP_SECRET_KEY
./run.sh
```

`run.sh` creates a virtualenv, installs backend + frontend dependencies, and
starts both servers. Then open <http://localhost:5173>.

Generate a secret key for `APP_SECRET_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Manual start (alternative)

```bash
# Backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd backend && uvicorn app.main:app --reload --port 8000

# Frontend (in a second terminal)
cd frontend && npm install && npm run dev
```

## Configuration

All configuration lives in `.env` (see `.env.example`):

| Variable | Purpose |
| --- | --- |
| `ANTHROPIC_API_KEY` | Required for AI plan generation. |
| `APP_SECRET_KEY` | Signs login tokens. Use a long random string. |
| `DATABASE_URL` | SQLite location (default `./data/coach.sqlite3`). |
| `GARMIN_TOKENS_DIR` | Where per-user Garmin tokens are stored. |
| `DEFAULT_AI_MODEL` / `DEFAULT_REASONING_EFFORT` | Defaults for new users. |
| `DAILY_SYNC_HOUR` | Hour (0-23) for the automatic daily sync. |
| `SYNC_LOOKBACK_DAYS` | How many days back a routine sync pulls. |

## Notes & limitations

- **Garmin is an unofficial API.** Logins can occasionally require MFA, hit rate
  limits, or change shape. The app handles these gracefully and keeps any metric
  you can edit manually.
- **Daily auto-sync** runs in-process while the app is running. For always-on
  sync, keep the app running or schedule a periodic launch (e.g. macOS `launchd`
  / `cron` calling the manual sync endpoint).
- **Pull-only**: the app reads from Garmin; it does not push workouts back to your
  watch.

## Project layout

```
backend/app/
  config.py db.py models.py schemas.py auth.py main.py
  routers/   auth, profile, garmin, plans, tracking, settings
  services/  garmin_service, agent_service, scheduler, matching, week
  agent/     tools, prompts
frontend/src/
  pages/ components/ api/ hooks/
```

## Initial Project Scope

This initial project construction includes:

- A FastAPI backend with local SQLite persistence, JWT-based auth, Garmin sync,
  training-plan generation, plan versioning, tracking, and settings APIs.
- A React + Vite frontend for onboarding, Garmin connection, dashboard, profile,
  plan creation, plan review/refinement, weekly tracking, and AI settings.
- Automated tests for backend API flows and core plan/tracking helpers, plus
  frontend unit/component tests for shared formatting and UI helpers.
- Local-first configuration via `.env.example`; real `.env`, Garmin token files,
  SQLite databases, virtualenvs, `node_modules`, and build artifacts are ignored.

## Tests

```bash
source .venv/bin/activate
cd backend && pytest          # backend (Garmin + Claude are mocked)
cd frontend && npm test       # frontend component tests
```
