#!/usr/bin/env bash
# Start the AI Running Coach locally: FastAPI backend + Vite frontend.
# Stops both when you press Ctrl-C.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# --- Python backend ---------------------------------------------------------
if [ ! -d ".venv" ]; then
  echo "==> Creating Python virtualenv (.venv)"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
echo "==> Installing backend dependencies"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

if [ ! -f ".env" ]; then
  echo "==> No .env found; copying .env.example (edit it to add your API key)"
  cp .env.example .env
fi

echo "==> Starting backend on http://localhost:8000"
(cd backend && uvicorn app.main:app --reload --port 8000) &
BACKEND_PID=$!

# --- Frontend ---------------------------------------------------------------
if [ ! -d "frontend/node_modules" ]; then
  echo "==> Installing frontend dependencies"
  (cd frontend && npm install)
fi

echo "==> Starting frontend on http://localhost:5173"
(cd frontend && npm run dev) &
FRONTEND_PID=$!

cleanup() {
  echo ""
  echo "==> Shutting down"
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait
