#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
APP_API_URL="${NEXT_PUBLIC_API_URL:-http://127.0.0.1:${BACKEND_PORT}}"

ensure_port_is_free() {
  local port="$1"
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $port is already in use. Stop the existing local service before starting the app." >&2
    return 1
  fi
}

if [[ ! -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
  echo "Missing Python environment: $PROJECT_ROOT/.venv/bin/python" >&2
  echo "Create it with: uv venv --python 3.12 .venv && uv pip install -r requirements.txt" >&2
  exit 1
fi

if [[ ! -x "$PROJECT_ROOT/frontend/node_modules/.bin/next" ]]; then
  echo "Missing frontend dependencies. Run: cd frontend && npm install" >&2
  exit 1
fi

ensure_port_is_free "$BACKEND_PORT" || exit 1
ensure_port_is_free "$FRONTEND_PORT" || exit 1

echo "Building the frontend..."
(cd "$PROJECT_ROOT/frontend" && NEXT_PUBLIC_API_URL="$APP_API_URL" npm run build)

# Standalone output does not copy these assets automatically.
mkdir -p "$PROJECT_ROOT/frontend/.next/standalone/.next/static"
cp -R "$PROJECT_ROOT/frontend/.next/static/." "$PROJECT_ROOT/frontend/.next/standalone/.next/static/"
if [[ -d "$PROJECT_ROOT/frontend/public" ]]; then
  mkdir -p "$PROJECT_ROOT/frontend/.next/standalone/public"
  cp -R "$PROJECT_ROOT/frontend/public/." "$PROJECT_ROOT/frontend/.next/standalone/public/"
fi

cleanup() {
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

"$PROJECT_ROOT/.venv/bin/python" -m uvicorn backend.main:app \
  --host 127.0.0.1 --port "$BACKEND_PORT" &
BACKEND_PID=$!

(
  cd "$PROJECT_ROOT/frontend"
  HOSTNAME=127.0.0.1 PORT="$FRONTEND_PORT" node .next/standalone/server.js
) &
FRONTEND_PID=$!

echo "Backend:  http://127.0.0.1:${BACKEND_PORT}"
echo "Frontend: http://127.0.0.1:${FRONTEND_PORT}"
echo "Press Ctrl-C to stop both services."

wait "$BACKEND_PID" "$FRONTEND_PID"
