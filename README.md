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
