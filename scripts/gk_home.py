"""Where Gatekeeper's code is and where one person's Gatekeeper data lives. The only place that decides.

The code folder is wherever this repo was put: a git checkout, or the plugin cache Claude Code installs into. It is
replaced on every update, so nothing a person owns may be stored in it. Their data lives in the home folder:

    $GATEKEEPER_HOME                          if set
    the code folder itself                    if it already has a data/ folder (a checkout used in place, as before)
    ~/Gatekeeper                              otherwise (every plugin install)

The home folder holds data/ (the ledger and its backups), context/, briefs/ and inbox/. Sign-in tokens, the Python
environment and the dashboard's pid and log are machine state, kept in ~/.gatekeeper (GATEKEEPER_STATE).
"""

from __future__ import annotations

import os
from pathlib import Path

CODE = Path(__file__).resolve().parents[1]
INBOX_NOTE = '# inbox\n\nDrop exports here for the internal sensors: support tickets, returns, lost-deal notes,\ndowntime logs, an Azure DevOps work-item export. Any text format (CSV, markdown, plain text).\n\nScouts for `unexpected_occurrences`, `incongruities` and `process_needs` read only this folder\nand cite files as `file:///<absolute path to the file>`. Nothing here is ever sent to a web search.\n'


def home() -> Path:
    env = os.environ.get("GATEKEEPER_HOME")
    if env:
        return Path(env).expanduser().resolve()
    if (CODE / "data").is_dir():
        return CODE
    return Path.home() / "Gatekeeper"


def state() -> Path:
    return Path(os.environ.get("GATEKEEPER_STATE", Path.home() / ".gatekeeper")).expanduser()


def ensure_home() -> Path:
    h = home()
    for sub in ("data", "context", "briefs", "inbox"):
        (h / sub).mkdir(parents=True, exist_ok=True)
    note = h / "inbox" / "README.md"
    if not note.exists():
        note.write_text(INBOX_NOTE)
    return h


if __name__ == "__main__":
    print(ensure_home())
