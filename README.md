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
  The plan streams in live as Claude reasons.
- **Review & refine** — approve a plan, or open a chat to request changes in
  natural language and regenerate.
- **Tracking** — current-week table of planned vs. actually-completed workouts,
  matched from your synced activities.
- **Updates & versions** — weekly auto-review, free-text manual updates, and a
  side-by-side compare with the ability to restore any previous version.
- **My Board** — at-a-glance view of your latest Garmin health & performance
  metrics and recent activities.
- **Settings** — choose the Claude model and reasoning effort.

## Architecture

A single-page React app talks to a FastAPI backend over `/api`; everything runs
on your machine against a local SQLite database.

```
┌───────────────────────────┐   /api   ┌────────────────────────────────┐
│  React + Vite  (:5173)     │ ───────▶ │  FastAPI  (:8000)              │
│  React Query · Tailwind    │  proxy   │  routers → services            │
│  SSE reader for AI streams │ ◀─────── │  auth · garmin · plans · …     │
└───────────────────────────┘          │      │              │          │
                                        │      ▼              ▼          │
                                        │  SQLAlchemy     Claude Agent   │
                                        │   (SQLite)          SDK        │
                                        └──────┼──────────────┼──────────┘
                                               ▼              ▼
                                      coach.sqlite3 +   Anthropic API
                                      Garmin tokens     Garmin Connect
```

- **Request flow & auth** — the SPA calls `/api/*`; the Vite dev server proxies
  those to the backend, so only the frontend port is exposed. Auth is a JWT
  bearer token (HS256, PyJWT) issued on login and verified via an OAuth2 bearer
  scheme; passwords are hashed with bcrypt.
- **AI plan generation** — the Claude Agent SDK drives a locked-down agent: one
  custom in-process MCP tool, `submit_plan`, captures the structured plan, and
  **no filesystem or shell tools are granted**. Reasoning effort maps to a
  thinking-token budget. The SDK is imported lazily so the app and tests run
  without it (and without a key) installed.
- **Live streaming** — generation and updates stream over Server-Sent Events.
  The backend yields event dicts (`prompt`, `thinking`, `text`, `step`, `plan`,
  `done`); the frontend consumes them with `fetch` + `ReadableStream` rather than
  `EventSource`, so it can send the `Authorization` header.
- **Garmin sync** — the unofficial `garminconnect` library (over `curl_cffi`)
  handles login, MFA, and token storage. Every network call is defensive: a
  single failing endpoint never aborts a sync, and any metric it can't fetch
  stays hand-editable. Runs on demand or via an APScheduler daily cron.
- **Plans & versioning** — each plan holds an append-only chain of versions
  (`draft → proposed → active → superseded`, plus `restored`), with an
  `active_version` pointer marking the live one; generated, chat-edited,
  weekly-, manual-, and restored versions all coexist for compare/restore.
- **Tracking & matching** — after each sync a matching service pairs run
  activities to planned workouts on an Israeli-week calendar (Sunday-first) to
  compute completions and feed the weekly review.
- **Data model (SQLite)** — a `User` owns a `Profile`, `GarminConnection`, and
  `UserSettings`, plus synced `Activity`, `DailyHealth`, `HealthSnapshot`, and
  `MetricObservation` rows. A `TrainingPlan` fans out to `PlanVersion` →
  `PlannedWorkout`; `WorkoutCompletion` links matched activities and
  `PlanChangeRequest` records edit requests.

## Tech stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.10+, FastAPI, Uvicorn (ASGI) |
| Persistence | SQLAlchemy 2.0 ORM, SQLite |
| Config & validation | Pydantic v2, pydantic-settings |
| Auth | PyJWT (HS256), bcrypt, OAuth2 bearer |
| Scheduling | APScheduler (background cron) |
| AI | Claude Agent SDK + custom MCP tool → Anthropic API |
| Garmin | `garminconnect` + `curl_cffi` (unofficial API) |
| Frontend | React 18, TypeScript, Vite 5 |
| Routing & data | React Router 6, TanStack Query 5, axios |
| UI | Tailwind CSS 3, Radix UI, lucide-react |
| Tests | pytest · pytest-asyncio · httpx / Vitest · Testing Library · jsdom |

## Requirements

- **Python 3.10+** (tested on 3.13)
- **Node.js 18+** (tested on 24) — also required by the Claude Agent SDK
- An **Anthropic API key** — <https://console.anthropic.com>
- A **Garmin Connect** account

## First-time setup

You only do this once.

**1. Clone the repo**

```bash
git clone https://github.com/ofirbrand/AI-Running-Trainer.git
cd AI-Running-Trainer
```

**2. Create your `.env`**

```bash
cp .env.example .env
```

Then edit `.env` and set the two required values:

- `ANTHROPIC_API_KEY` — your key from the Anthropic console.
- `APP_SECRET_KEY` — a long random string used to sign login tokens. Generate one:

  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(48))"
  ```

Every other variable has a sensible default — see [Configuration](#configuration).

> `run.sh` will copy `.env.example` to `.env` automatically on first launch if you
> skip this step, but you still need to open `.env` and fill in your API key.

**3. Start the app**

```bash
./run.sh
```

The first run creates a Python virtualenv (`.venv`), installs backend and
frontend dependencies, and starts both servers. This takes a minute or two; later
runs are fast because everything is already installed.

When you see the frontend start, open <http://localhost:5173>.

**4. Onboard in the browser**

1. **Register** an account (email + password — stored locally).
2. Fill in your **runner profile** (PRs, height, weight, goals).
3. **Connect Garmin** — enter your Garmin Connect credentials (complete MFA if
   prompted). The app pulls your activities and health metrics.
4. **Create a plan** — the builder is pre-filled from your Garmin data; review it,
   then generate. Approve it or refine it via chat.

## Running day-to-day

Once setup is done, your daily loop is just:

```bash
cd AI-Running-Trainer
./run.sh
```

- Backend (FastAPI) runs on <http://localhost:8000>
- Frontend (Vite) runs on <http://localhost:5173> — **open this one**

Press **Ctrl-C** to stop both servers.

Typical things you'll do while it's running:

- **Sync** — hit "Sync now" on the dashboard to pull the latest runs, or let the
  automatic daily sync handle it (runs at `DAILY_SYNC_HOUR` while the app is up).
- **Track** — open the current week to see planned vs. completed workouts.
- **Refine / update** — chat with the coach to adjust the plan, or apply a
  free-text update; compare versions and restore an older one if needed.
- **My Board** — check your latest health and performance metrics.

### Manual start (alternative to `run.sh`)

Run the two servers yourself in separate terminals:

```bash
# Backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd backend && uvicorn app.main:app --reload --port 8000

# Frontend (in a second terminal)
cd frontend && npm install && npm run dev
```

### Accessing from your phone (iPhone / LAN / Tailscale)

The Vite dev server is configured with `host: true`, so it listens on your whole
network, not just `localhost`. To open the app on your phone:

- **Same Wi-Fi (LAN):** find your computer's local IP (e.g. `192.168.1.50`) and
  open `http://<that-ip>:5173` on your phone. Both devices must be on the same
  network.
- **Tailscale:** the config already allows `*.ts.net` hosts. With Tailscale
  running on both devices, open your machine's MagicDNS name (e.g.
  `http://your-machine.tailnet-name.ts.net:5173`) from anywhere.

The frontend proxies `/api` to the backend on port 8000, so you don't need to
expose the backend separately — reaching the frontend is enough.

## Configuration

All configuration lives in `.env` (see `.env.example`):

| Variable | Purpose |
| --- | --- |
| `ANTHROPIC_API_KEY` | **Required.** Used for AI plan generation. |
| `APP_SECRET_KEY` | **Required.** Signs login tokens. Use a long random string. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | How long a login stays valid (default 10080 = 7 days). |
| `DATABASE_URL` | SQLite location (default `sqlite:///./data/coach.sqlite3`). |
| `GARMIN_TOKENS_DIR` | Where per-user Garmin tokens are stored. |
| `DEFAULT_AI_MODEL` / `DEFAULT_REASONING_EFFORT` | Defaults for new users (changeable per-user in Settings). |
| `DAILY_SYNC_HOUR` | Hour (0-23, local time) for the automatic daily sync. |
| `SYNC_LOOKBACK_DAYS` | How many days back a routine sync pulls. |
| `AI_BACKEND` | `sdk` (Claude Agent SDK, local default) or `api` (direct Anthropic API, used on Vercel). |
| `GARMIN_TOKEN_STORE` | `file` (local default) or `db` (token blob in the database, used on Vercel). |
| `ENABLE_SCHEDULER` | In-process daily sync (default `true`; `false` on Vercel). |
| `ALLOW_REGISTRATION` | Allow new signups (default `true`; set `false` on a public deployment). |
| `CRON_SECRET` | Enables `GET /api/internal/daily-sync` for external schedulers (unset locally). |

## Deploying to Vercel

The app deploys as a single Vercel project: the Vite frontend is served
statically and the FastAPI backend runs as a Python serverless function
(`api/index.py`, routed via `vercel.json`). Local behavior is unchanged — every
serverless adaptation is opt-in via environment variables.

What differs in production:

- **Database**: hosted Postgres (e.g. Neon via the Vercel marketplace) through
  `DATABASE_URL`. `postgres://` URLs are normalized to the psycopg driver
  automatically.
- **AI**: `AI_BACKEND=api` swaps the Claude Agent SDK (which spawns a local
  Node CLI and can't run in a serverless function) for a direct Anthropic API
  implementation with identical streaming events and the same `submit_plan`
  tool (`backend/app/services/agent_api.py`).
- **Garmin tokens**: `GARMIN_TOKEN_STORE=db` stores the session-token blob in
  the `garmin_connections` row instead of files on disk.
- **Daily sync**: `ENABLE_SCHEDULER=false`; a Vercel Cron entry calls
  `GET /api/internal/daily-sync` authenticated with `CRON_SECRET`.
- **Registration**: set `ALLOW_REGISTRATION=false` once the owner account
  exists.

Setup outline:

1. Create the Vercel project from this repo (the included `vercel.json`
   supplies build command, rewrites, function config, and the cron schedule).
2. Add a Neon Postgres database and set the env vars: `ANTHROPIC_API_KEY`, a
   fresh `APP_SECRET_KEY`, `DATABASE_URL`, `AI_BACKEND=api`,
   `GARMIN_TOKEN_STORE=db`, `ENABLE_SCHEDULER=false`, `CRON_SECRET`,
   `DEFAULT_AI_MODEL`, `DEFAULT_REASONING_EFFORT`.
3. Migrate your local data (including Garmin tokens) from the repo root:
   `python scripts/migrate_sqlite_to_postgres.py --dest "$NEON_URL" --import-tokens`
4. Deploy, then smoke-test: `/api/health`, login, a plan generation stream,
   and a manual Garmin sync.

Notes: Vercel's Python function installs `api/requirements.txt` (a slim set
without the ~200MB Agent SDK). The Hobby plan caps requests at 300s — very long
high-effort plan generations can hit it; re-run or upgrade if that bites. If
Garmin MFA is required while connecting through the deployment and it fails,
connect locally and re-run the token import.

## Tests

```bash
source .venv/bin/activate
cd backend && pytest          # backend (Garmin + Claude are mocked)
cd frontend && npm test       # frontend component tests
```

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
  services/  garmin_service, agent_service, plan_builder, scheduler, matching, week
  agent/     prompts
backend/tests/   pytest suite (API flow, garmin sync, matching, plan, week)
frontend/src/
  pages/      Login, Register, OnboardingGarmin, Plans, MyBoard, Profile,
              CreatePlan, PlanOverview, Tracking, Settings
  components/ Layout, WeeklyTable, PlanDiff, ChatPopup, HealthMetrics, …
  api/ auth/ state/ lib/
```

## Project scope

The initial project construction includes:

- A FastAPI backend with local SQLite persistence, JWT-based auth, Garmin sync,
  training-plan generation, plan versioning, tracking, and settings APIs.
- A React + Vite frontend for onboarding, Garmin connection, plans dashboard,
  profile, plan creation, plan review/refinement, weekly tracking, and AI settings.
- Automated tests for backend API flows and core plan/tracking helpers, plus
  frontend unit/component tests for shared formatting and UI helpers.
- Local-first configuration via `.env.example`; real `.env`, Garmin token files,
  SQLite databases, virtualenvs, `node_modules`, and build artifacts are ignored.
