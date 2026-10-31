#!/usr/bin/env bash
# Start, stop or check the Gatekeeper dashboard (the web app service) in the background.
# Used by the gatekeeper-dashboard skill; also fine to run by hand.
#
#   scripts/dashboard.sh [start]   build the web app if needed, start the service detached, print a sign-in link
#   scripts/dashboard.sh stop      stop it
#   scripts/dashboard.sh status    say whether it is running
#   scripts/dashboard.sh open      print a fresh sign-in link for the running service
#
# PORT=9000 changes the port. LEDGER=dev uses the throwaway copy in service/dev-data (see service/dev.sh).
# Process id and log: ~/.gatekeeper/dashboard.pid and dashboard.log (GATEKEEPER_STATE moves them).
# Runs from any folder: the code is where this script lives, the ledger is the person's Gatekeeper home (scripts/gk_home.py).
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"
PORT="${PORT:-8787}"
STATE="${GATEKEEPER_STATE:-$HOME/.gatekeeper}"
PIDFILE="$STATE/dashboard.pid"
LOG="$STATE/dashboard.log"
GK="$ROOT/bin/gk"
URL="http://127.0.0.1:$PORT"
mkdir -p "$STATE"

# The pid of OUR service on the port, or nothing. Never returns an unrelated process.
service_pid() {
  local pid
  for pid in $(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null); do
    if ps -o command= -p "$pid" | grep -q "service/serve.py"; then echo "$pid"; return; fi
  done
}

signin() { "$GK" serve open --port "$PORT"; }
# The link is good for 15 minutes from when it is made; say when, in local time.
expires() { date -v+15M "+%-I:%M %p" 2>/dev/null || date -d "+15 minutes" "+%-I:%M %p"; }

cmd="${1:-start}"
case "$cmd" in
  status)
    pid="$(service_pid)"
    if [ -n "$pid" ]; then echo "running  pid $pid  $URL  log $LOG"; else
      if lsof -tiTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then echo "port $PORT is held by something that is not the Gatekeeper service"; exit 2; fi
      echo "stopped"; fi
    ;;
  open)
    [ -n "$(service_pid)" ] || { echo "The dashboard is not running." >&2; exit 1; }
    echo "Sign in: $(signin)"
    echo "Expires: $(expires)"
    ;;
  stop)
    pid="$(service_pid)"
    if [ -z "$pid" ]; then
      if lsof -tiTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then echo "Port $PORT is held by something that is not the Gatekeeper service. Left alone." >&2; exit 2; fi
      rm -f "$PIDFILE"; echo "The dashboard was not running."; exit 0
    fi
    kill "$pid"
    for _ in $(seq 1 20); do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done
    if kill -0 "$pid" 2>/dev/null; then kill -9 "$pid"; fi
    rm -f "$PIDFILE"; echo "Stopped the dashboard (pid $pid)."
    ;;
  start)
    "$GK" bootstrap >/dev/null || { echo "Could not build the Python environment (see above)." >&2; exit 1; }
    pid="$(service_pid)"
    if [ -n "$pid" ]; then echo "Already running (pid $pid) at $URL"; echo "Sign in: $(signin)"; echo "Expires: $(expires)"; exit 0; fi
    if lsof -tiTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then echo "Port $PORT is in use by something else. Try PORT=<other> gk dashboard" >&2; exit 2; fi

    # The built web app ships in the repo. Rebuild only when the source is newer (a developer with pnpm).
    if [ ! -f service/web/dist/index.html ] || [ -n "$(find service/web/src service/web/index.html service/web/package.json -newer service/web/dist/index.html -print -quit 2>/dev/null)" ]; then
      if command -v pnpm >/dev/null 2>&1; then
        echo "Building the web app..."
        if ! (cd service/web && pnpm install --silent && pnpm build >/dev/null); then
          [ -f service/web/dist/index.html ] || { echo "Web build failed." >&2; exit 1; }
          echo "Web rebuild failed; using the build that ships with Gatekeeper." >&2
        fi
      elif [ ! -f service/web/dist/index.html ]; then
        echo "The web app is not built and pnpm is not installed." >&2; exit 1
      fi
    fi

    if [ "${LEDGER:-live}" = "dev" ]; then
      [ -f service/dev-data/gatekeeper.db ] || { echo "No service/dev-data/gatekeeper.db. Run LEDGER=dev service/dev.sh once to create it." >&2; exit 1; }
      export GATEKEEPER_DB="$PWD/service/dev-data/gatekeeper.db" GATEKEEPER_HOME="$PWD/service/dev-data"; ledger="DEV COPY of the ledger"
    else
      GATEKEEPER_HOME="$("$GK" python "$ROOT/scripts/gk_home.py")"; export GATEKEEPER_HOME
      export GATEKEEPER_DB="$GATEKEEPER_HOME/data/gatekeeper.db"; ledger="LIVE ledger"
    fi

    nohup "$GK" serve --port "$PORT" >"$LOG" 2>&1 </dev/null &
    echo $! >"$PIDFILE"
    disown 2>/dev/null || true
    for _ in $(seq 1 40); do
      [ -n "$(service_pid)" ] && break
      kill -0 "$(cat "$PIDFILE")" 2>/dev/null || { echo "The service exited on start. Log:" >&2; tail -20 "$LOG" >&2; rm -f "$PIDFILE"; exit 1; }
      sleep 0.5
    done
    [ -n "$(service_pid)" ] || { echo "The service did not come up in 20 seconds. Log: $LOG" >&2; exit 1; }
    echo "Started the dashboard on the $ledger (pid $(service_pid))"
    echo "Open: $URL"
    echo "Sign in: $(signin)"
    echo "Expires: $(expires)"
    ;;
  *)
    echo "usage: gk dashboard [start|stop|status|open]" >&2; exit 64 ;;
esac
