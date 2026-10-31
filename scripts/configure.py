"""Write .mcp.json for Code tab sessions and print (or merge) the Claude Desktop config entry.

Usage: python scripts/configure.py <gatekeeper home> [--desktop]
"""

import json
import shutil
import sys
import time
from pathlib import Path

root = Path(sys.argv[1]).resolve()
write_desktop = "--desktop" in sys.argv[2:]

entry = {
    "command": str(root / ".venv" / "bin" / "python"),
    "args": [str(root / "service" / "gatekeeper_server.py")],
    "env": {"GATEKEEPER_HOME": str(root)},
}

# 1. Project config, read by Code tab sessions and scheduled tasks opened on this folder.
(root / ".mcp.json").write_text(json.dumps({"mcpServers": {"gatekeeper": entry}}, indent=2) + "\n")
print(f"Wrote {root / '.mcp.json'}")

# 2. Claude Desktop config, read by chats and the board page.
desktop = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
snippet = json.dumps({"mcpServers": {"gatekeeper": entry}}, indent=2)

if write_desktop:
    desktop.parent.mkdir(parents=True, exist_ok=True)
    cfg = {}
    if desktop.exists():
        backup = desktop.with_name(f"claude_desktop_config.backup-{time.strftime('%Y%m%d-%H%M%S')}.json")
        shutil.copy2(desktop, backup)
        print(f"Backed up existing config to {backup}")
        cfg = json.loads(desktop.read_text() or "{}")
    cfg.setdefault("mcpServers", {})["gatekeeper"] = entry
    desktop.write_text(json.dumps(cfg, indent=2) + "\n")
    print(f"Added 'gatekeeper' to {desktop}")
    print("Quit Claude completely (Cmd+Q) and reopen it to load the connector.")
else:
    print("\nTo use Gatekeeper from ordinary Claude chats, add this under mcpServers in")
    print(f"  {desktop}")
    print("(Settings > Developer > Edit Config), or re-run with --desktop to do it for you:\n")
    print(snippet)
