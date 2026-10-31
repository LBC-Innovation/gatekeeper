"""Run the Gatekeeper service on this machine: the web app, the web API and both MCP surfaces, over one ledger.

    python service/serve.py                 start the service (default http://127.0.0.1:8787)
    python service/serve.py open            print a fresh one-time sign-in link for a running service
    python service/serve.py mcp-config      print the .mcp.json entries (with the bearer token) for Claude Code
    python service/serve.py token --rotate  replace the API token and sign every browser out

Env: GATEKEEPER_HOME (folder holding data/, context/, briefs/; default ~/Gatekeeper, see scripts/gk_home.py), GATEKEEPER_DB (database path),
     GATEKEEPER_AUTH_DIR (the folder that holds .gatekeeper/ with sign-in tokens; default your
     home folder, so one sign-in store is shared by every ledger).
It binds to loopback only. For development, point it at a copy: GATEKEEPER_DB=service/dev-data/gatekeeper.db
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "scripts"))

from gatekeeper.auth import Auth  # noqa: E402
from gatekeeper.core import Gatekeeper  # noqa: E402
import gk_home  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", nargs="?", default="serve", choices=["serve", "open", "mcp-config", "token"])
    ap.add_argument("--port", type=int, default=int(os.environ.get("GATEKEEPER_PORT", 8787)))
    ap.add_argument("--rotate", action="store_true")
    a = ap.parse_args()

    home = gk_home.ensure_home()
    db = Path(os.environ.get("GATEKEEPER_DB", home / "data" / "gatekeeper.db")).expanduser()
    # Sign-in is per person, not per ledger: one store, so `open` works whichever ledger the running service uses.
    auth = Auth(Path(os.environ.get("GATEKEEPER_AUTH_DIR", Path.home())).expanduser())
    base = f"http://127.0.0.1:{a.port}"

    if a.command == "token":
        print(auth.rotate_token() if a.rotate else auth.api_token)
        return
    if a.command == "mcp-config":
        import json
        hdr = {"Authorization": f"Bearer {auth.api_token}"}
        print(json.dumps({"mcpServers": {"gatekeeper": {"type": "http", "url": f"{base}/mcp/person/", "headers": hdr},
                                         "gatekeeper-pipeline": {"type": "http", "url": f"{base}/mcp/pipeline/", "headers": hdr}}}, indent=2))
        return
    if a.command == "open":
        print(f"{base}/auth/launch?t={auth.new_launch_token()}")
        return

    import socket

    import uvicorn
    from gatekeeper.api import create_app

    # Claim the port before printing anything, so a sign-in link is never shown for a service that did not start.
    probe = socket.socket()
    probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)   # connections still closing from a server that just stopped do not count
    try:
        probe.bind(("127.0.0.1", a.port))
    except OSError:
        sys.exit(f"Port {a.port} is already in use, probably by a Gatekeeper service that is already running.\n"
                 f"  To get a sign-in link for it:   service/dev.sh open\n  To replace it with a fresh start: service/dev.sh")
    finally:
        probe.close()

    gk = Gatekeeper(db, home)
    app = create_app(gk, auth, port=a.port, static_dir=HERE / "web" / "dist")
    print(f"\nGatekeeper service\n  ledger  {db}\n  web     {base}\n  sign in {base}/auth/launch?t={auth.new_launch_token()}   (one use, 15 minutes)\n", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
