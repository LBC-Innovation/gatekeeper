#!/usr/bin/env bash
# Gatekeeper installer for a CHECKOUT used in place (development, or a standalone copy). Safe to re-run.
# To use Gatekeeper normally, install the plugin instead:  /plugin marketplace add <owner>/<repo>  (see README).
#
#   scripts/install.sh            set up .venv, run tests, write .mcp.json, print the desktop config entry
#   scripts/install.sh --desktop  same, and also add the entry to Claude Desktop's config (backup kept)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
echo "Gatekeeper home: $ROOT"

if command -v uv >/dev/null 2>&1; then
  echo "Using uv"
  uv venv --allow-existing --python 3.12 .venv
  uv pip install --python .venv/bin/python --quiet -r requirements.txt
else
  PY3="$(command -v python3 || true)"
  if [ -z "$PY3" ]; then
    echo "Need Python 3.10 or newer, or uv (brew install uv)." >&2
    exit 1
  fi
  if ! "$PY3" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo "$PY3 is older than 3.10. Install uv (brew install uv) and re-run." >&2
    exit 1
  fi
  echo "Using $PY3"
  "$PY3" -m venv .venv
  .venv/bin/python -m pip install --quiet --upgrade pip
  .venv/bin/python -m pip install --quiet -r requirements.txt
fi

PY="$ROOT/.venv/bin/python"

echo
echo "Installing agents, skills and settings into .claude/"
mkdir -p .claude/agents .claude/skills
cp claude-config/agents/*.md .claude/agents/
cp -R claude-config/skills/. .claude/skills/
# The sources are written for the plugin (connector tools are mcp__plugin_gatekeeper_gatekeeper__*, scripts run through
# ${CLAUDE_PLUGIN_ROOT}). In a checkout the connector is plain "gatekeeper" and the code is this folder.
"$ROOT/.venv/bin/python" - "$ROOT" <<'PY'
import sys
from pathlib import Path
root = sys.argv[1]
for p in list(Path(".claude/agents").glob("gatekeeper-*.md")) + list(Path(".claude/skills").rglob("*.md")):
    s = p.read_text()
    t = s.replace("mcp__plugin_gatekeeper_gatekeeper__", "mcp__gatekeeper__").replace("${CLAUDE_PLUGIN_ROOT}", root)
    if t != s:
        p.write_text(t)
PY
mkdir -p data context briefs inbox   # a data/ folder here makes this checkout its own Gatekeeper home (scripts/gk_home.py)
if [ -f .claude/settings.json ] && ! cmp -s claude-config/settings.json .claude/settings.json; then
  cp .claude/settings.json ".claude/settings.backup-$(date +%Y%m%d-%H%M%S).json"
  echo "Backed up your existing .claude/settings.json"
fi
cp claude-config/settings.json .claude/settings.json

echo
echo "Running tests"
"$PY" -m unittest discover -s tests
"$PY" tests/smoke_mcp.py
echo
"$PY" scripts/configure.py "$ROOT" "$@"
