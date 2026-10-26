#!/usr/bin/env bash
# Seed a scratch database with the mock graph, start the backend and the dev server, run the
# browser check, then stop everything. Needs uv, npm and network access for Playwright's browser.
#   scripts/e2e/run.sh [screenshot dir]
set -euo pipefail
cd "$(dirname "$0")/../.."

SHOTS="${1:-/tmp/ta_e2e_shots}"
DB="$(mktemp -u /tmp/ta_e2e_XXXXXX).db"
export TA_DATABASE_URL="sqlite:///$DB" TA_ADMIN_KEY=test-key
mkdir -p "$SHOTS"

(cd backend && uv run alembic upgrade head >/dev/null 2>&1)
uv run --project backend python -m backend.seed --mock >/dev/null

uv run --project backend uvicorn backend.main:app --port 8000 >/dev/null 2>&1 &
API=$!
npm run dev -- --port 5173 >/dev/null 2>&1 &
WEB=$!
trap 'kill $API $WEB 2>/dev/null || true; rm -f "$DB"' EXIT

for port in 8000 5173; do
  for _ in $(seq 1 60); do
    curl -s -o /dev/null "http://localhost:$port/" && break
    sleep 0.5
  done
done

uv run --with playwright python -m playwright install chromium >/dev/null 2>&1 || true
uv run --with playwright python scripts/e2e/review_flow.py "$SHOTS"
