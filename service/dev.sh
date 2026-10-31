#!/usr/bin/env bash
# Run the Gatekeeper service for development, in THIS terminal. Ctrl-C stops it; run it again to restart.
#
#   service/dev.sh            build the web app, then start the service on http://127.0.0.1:8787
#   PORT=9000 service/dev.sh  use another port
#   service/dev.sh open       print a fresh sign-in link for the service that is already running
#
# It reads your live ledger (data/gatekeeper.db). LEDGER=dev service/dev.sh uses a throwaway copy instead.
# Web changes: rerun this script (or `cd service/web && pnpm build`) and reload the browser.
# Python changes: rerun this script.
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${PORT:-8787}"

if [ "${1:-}" = "open" ]; then exec .venv/bin/python service/serve.py open --port "$PORT"; fi

# Stop whatever already holds the port: an earlier run of this script, or a background one.
pid="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN || true)"
if [ -n "$pid" ]; then
  echo "Stopping the service already on :$PORT (pid $pid)"; kill "$pid"
  for _ in 1 2 3 4 5 6 7 8 9 10; do lsof -tiTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1 || break; sleep 0.5; done   # wait until it has really let go
fi

# The web app reads your real ledger (data/) by default. LEDGER=dev uses a throwaway copy (service/dev-data) for trying things out.
if [ "${LEDGER:-live}" = "dev" ] && [ ! -f service/dev-data/gatekeeper.db ]; then
  mkdir -p service/dev-data
  .venv/bin/python - <<'PY'
import sqlite3
src = sqlite3.connect("file:data/gatekeeper.db?mode=ro", uri=True)
dst = sqlite3.connect("service/dev-data/gatekeeper.db"); src.backup(dst)
print("Made service/dev-data/gatekeeper.db from a read-only snapshot of data/gatekeeper.db")
PY
fi

echo "Building the web app..."
(cd service/web && pnpm install --silent && pnpm build >/dev/null)

if [ "${LEDGER:-live}" = "dev" ]; then
  export GATEKEEPER_DB="$PWD/service/dev-data/gatekeeper.db" GATEKEEPER_HOME="$PWD/service/dev-data"; echo "Using the DEV COPY of the ledger"
else
  export GATEKEEPER_DB="$PWD/data/gatekeeper.db" GATEKEEPER_HOME="$PWD"; echo "Using your LIVE ledger: decisions you click are real"
fi
exec .venv/bin/python service/serve.py --port "$PORT"
