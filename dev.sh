#!/usr/bin/env bash
# Start the FastAPI backend and the Vite frontend together for local development.
# Ctrl+C stops both.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

# Use the backend virtualenv if it exists; otherwise rely on whatever is on PATH.
if [[ -f "$ROOT/backend/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/backend/.venv/bin/activate"
fi

# The frontend needs Node >= 22.12 (see frontend/.nvmrc). Switch to it if nvm is installed.
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [[ -s "$NVM_DIR/nvm.sh" ]]; then
  # shellcheck disable=SC1091
  source "$NVM_DIR/nvm.sh"
  nvm use --silent "$(cat "$ROOT/frontend/.nvmrc")" >/dev/null 2>&1 \
    || echo "warning: nvm could not switch to Node $(cat "$ROOT/frontend/.nvmrc")" >&2
fi

command -v fastapi >/dev/null || { echo "fastapi not found: set up the backend first (see README)" >&2; exit 1; }
[[ -d "$ROOT/frontend/node_modules" ]] || (cd "$ROOT/frontend" && npm install)

cleanup() {
  trap - INT TERM EXIT
  kill 0 2>/dev/null || true
}
trap cleanup INT TERM EXIT

# Output goes to the terminal (prefixed) and to logs/*.log (overwritten on each run).
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

# Run a command in a directory, tee its output to a log file, and prefix each terminal line with a label.
run() {
  local label=$1 dir=$2 log=$3
  shift 3
  (cd "$dir" && "$@" 2>&1) | tee "$log" | sed -u "s/^/[$label] /"
}

run backend "$ROOT/backend" "$LOG_DIR/backend.log" fastapi dev app/main.py &
BACKEND=$!
run frontend "$ROOT/frontend" "$LOG_DIR/frontend.log" npm run dev &
FRONTEND=$!

echo "Backend:  http://localhost:8000 (docs at /docs)  log: logs/backend.log"
echo "Frontend: http://localhost:5173                   log: logs/frontend.log"

# If either server exits (e.g. crashes on startup), stop the other one too.
while kill -0 "$BACKEND" 2>/dev/null && kill -0 "$FRONTEND" 2>/dev/null; do
  sleep 1
done
echo "A server exited; shutting down." >&2
