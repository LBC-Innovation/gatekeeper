"""Gatekeeper connector over stdio, straight on the SQLite ledger. For Claude Desktop and for tests.

Run with:  python service/gatekeeper_server.py
Env:       GATEKEEPER_HOME     folder holding data/, context/, briefs/ (default: see scripts/gk_home.py, ~/Gatekeeper)
           GATEKEEPER_DB       database path (default: $GATEKEEPER_HOME/data/gatekeeper.db)
           GATEKEEPER_SURFACE  person (default, everything) or pipeline (what agents may call)

The normal way to run Gatekeeper is `python service/serve.py`, which hosts the web app, the web API and both MCP
surfaces in one process. This direct entry point shares every rule with it: the tools come from the same registry.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "scripts"))

from gatekeeper.core import Gatekeeper  # noqa: E402
from gatekeeper.mcp_adapter import build_mcp  # noqa: E402
import gk_home  # noqa: E402

HOME = gk_home.ensure_home()
DB = Path(os.environ.get("GATEKEEPER_DB", HOME / "data" / "gatekeeper.db")).expanduser()

gk = Gatekeeper(DB, HOME)
server = build_mcp(gk, os.environ.get("GATEKEEPER_SURFACE", "person"))

if __name__ == "__main__":
    server.run()
