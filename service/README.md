# Gatekeeper service (v2)

One local process hosts the web app, the web API and the MCP connector over one ledger. This is the engine the plugin runs; the older connector in `server/` is kept only for the legacy scripts and tests.

```
service/
  gatekeeper/        the domain and adapters
    core.py          the ledger and every rule (forked from server/, with the five defect fixes)
    deliberation.py  pure rules: resolve, queue reconciliation
    types.py         typed tool inputs (claims, gaps, readiness) so agents see real field names
    registry.py      one declaration per command; MCP and REST both read it
    mcp_adapter.py   registers the commands as MCP tools, on two surfaces
    views.py         read models for the web app
    api.py           FastAPI app: REST, live stream, MCP mounts, static web app
    auth.py          local sign-in: launch link, session cookie, bearer token
  serve.py           run it
  gatekeeper_server.py  direct stdio MCP entry (Claude Desktop, tests)
  web/               React 19 + Vite + Tailwind v4 app
  tools/backfill_titles.py
  gatekeeper/team.py   the eleven agents: bios, schedule, and their instruction files from claude-config/agents/
  tests/             pytest (76) and web unit tests (7)
```

## Run it (development, on a copy of the ledger)

The short way, in your own terminal:

```bash
service/dev.sh        # builds the web app and starts the service on http://127.0.0.1:8787; Ctrl-C stops it, run it again to restart
```

The long way, step by step:

```bash
# once: a read-only snapshot of the live ledger to play with
python - <<'PY'
import sqlite3
src = sqlite3.connect("file:data/gatekeeper.db?mode=ro", uri=True); dst = sqlite3.connect("service/dev-data/gatekeeper.db"); src.backup(dst)
PY

GATEKEEPER_DB=service/dev-data/gatekeeper.db GATEKEEPER_HOME=service/dev-data python service/serve.py
python service/serve.py open        # prints a one-time sign-in link (same env vars)
```

The service listens on `127.0.0.1:8787` only. Open the link it prints once; the browser then stays signed in for 30 days.

Web app development, with hot reload against the running service:

```bash
cd service/web && pnpm install && pnpm dev      # http://127.0.0.1:5173, proxies /api to :8787
pnpm build                                      # writes service/web/dist, which the service serves
```

## Two MCP surfaces

| Endpoint | For | Has `decide`? |
|---|---|---|
| `/mcp/person/` | you and your Claude | yes (58 tools) |
| `/mcp/pipeline/` | scheduled agents | **no** (47 tools) |

`python service/serve.py mcp-config` prints the `.mcp.json` entries, with the bearer token.

## Tests

```bash
.venv/bin/python -m pytest service/tests -q     # rules, defects, properties, API
cd service/web && pnpm test && pnpm typecheck
.venv/bin/python service/tests/smoke_mcp.py                       # stdio
.venv/bin/python service/tests/smoke_http.py http://127.0.0.1:8787 "$(python service/serve.py token)"   # HTTP, both surfaces
```
