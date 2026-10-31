"""SessionStart hook: if this person's Gatekeeper is not set up, tell Claude to offer the setup interview.

Prints nothing once setup is complete, so a configured install adds no noise. Never fails the session.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "service"))
sys.path.insert(0, str(ROOT / "scripts"))

import gk_home  # noqa: E402

try:
    from gatekeeper.core import Gatekeeper

    home = gk_home.ensure_home()
    gk = Gatekeeper(home / "data" / "gatekeeper.db", home)
    status = gk.get_setup_status()
except Exception as e:  # the hook must never break a session
    print(f"Gatekeeper is installed but its ledger could not be opened ({e}). Tell the person, and do not guess.")
    sys.exit(0)

if not status["complete"]:
    done = sum(1 for s in status["steps"] if s["done"])
    print("Gatekeeper is installed but not set up yet "
          f"({done} of {len(status['steps'])} setup steps done; next: {status['next_step']}). "
          "Tell the person in one line, and offer to run the `gatekeeper-setup` skill now: "
          "a conversation of about forty-five minutes that can stop and resume at any step. "
          "Do not start it without their yes. If they decline, move on and do not raise it again this session. "
          "Also mention once that the Gatekeeper tools will ask for approval each time unless they allow the connector: "
          "offer to add `mcp__plugin_gatekeeper_gatekeeper` to their allowed permissions.")
