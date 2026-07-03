#!/usr/bin/env bash
# ===========================================================================
# loadgen deploy script — macOS / Linux
#
#   ./deploy.sh            # create venv + install dependencies
#   ./deploy.sh --run      # ...then start the web app (foreground)
#   ./deploy.sh --detached # ...start in the background (nohup), frees the terminal
#   ./deploy.sh --stop     # stop a detached server started earlier
#   PORT=9000 ./deploy.sh --run
#   PYTHON=python3.13 ./deploy.sh
#
# Requires Python 3.10+ on PATH (as `python3`, or override with $PYTHON).
# ===========================================================================
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"
PIDFILE=".loadgen_server.pid"
RUN=0; DETACHED=0; STOP=0
for arg in "$@"; do
  case "$arg" in
    --run) RUN=1 ;;
    --detached|--detach) DETACHED=1 ;;
    --stop) STOP=1 ;;
  esac
done

# --- stop a previously-detached server -------------------------------------
if [ "$STOP" = "1" ]; then
  if [ -f "$PIDFILE" ]; then
    OLDPID="$(cat "$PIDFILE")"
    if kill "$OLDPID" 2>/dev/null; then echo "Stopped loadgen server (PID $OLDPID)."
    else echo "No running process with PID $OLDPID (already stopped?)."; fi
    rm -f "$PIDFILE"
  else
    echo "No PID file ($PIDFILE) - nothing to stop."
  fi
  exit 0
fi

if ! command -v "$PY" >/dev/null 2>&1; then
  echo "ERROR: '$PY' not found. Install Python 3.10+ or set PYTHON=/path/to/python." >&2
  exit 1
fi

VER="$("$PY" -c 'import sys;print(".".join(map(str,sys.version_info[:2])))')"
echo "==> Using Python $VER ($PY)"

echo "==> Creating virtual environment at ./venv"
"$PY" -m venv venv

echo "==> Upgrading pip + installing requirements"
./venv/bin/python -m pip install --upgrade pip >/dev/null
./venv/bin/python -m pip install -r requirements.txt

echo "==> Verifying pymongo imports"
./venv/bin/python -c "import pymongo, fastapi, uvicorn, apscheduler; print('   deps OK — pymongo', pymongo.version)"

# Find the first port uvicorn can actually bind, starting at $PORT (skips ports
# in use and, on Windows hosts, reserved ranges).
FREEPORT="$(./venv/bin/python freeport.py "$PORT")" || {
  echo "ERROR: no bindable port found at/above $PORT. Set PORT=... and retry." >&2
  exit 1
}
if [ "$FREEPORT" != "$PORT" ]; then
  echo "==> Port $PORT unavailable (in use or reserved); using $FREEPORT instead."
fi
URL="http://$HOST:$FREEPORT/"
# --no-access-log silences per-request log spam (the UI polls /api/logs ~every 1.5s);
# the app's own dual-TZ INFO lines still print.

echo ""
echo "Deploy complete. Start the app with:"
echo "    ./venv/bin/python -m uvicorn app:app --host $HOST --port $FREEPORT --no-access-log"
echo "Then open: $URL"

if [ "$DETACHED" = "1" ]; then
  nohup ./venv/bin/python -m uvicorn app:app --host "$HOST" --port "$FREEPORT" --no-access-log \
    > server.log 2>&1 &
  echo $! > "$PIDFILE"
  echo ""
  echo "==> Started loadgen DETACHED (PID $(cat "$PIDFILE")) - open $URL"
  echo "    Logs:  ./server.log     Stop:  ./deploy.sh --stop   (or kill $(cat "$PIDFILE"))"
  exit 0
fi

if [ "$RUN" = "1" ]; then
  echo ""
  echo "==> Starting loadgen — open $URL  (Ctrl+C to stop)"
  exec ./venv/bin/python -m uvicorn app:app --host "$HOST" --port "$FREEPORT" --no-access-log
fi
