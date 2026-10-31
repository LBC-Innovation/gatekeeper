"""List the ledger backups in data/backups/ and restore one.

Usage:
    .venv/bin/python scripts/restore_backup.py --list [--json]
    .venv/bin/python scripts/restore_backup.py --restore NAME --yes

--restore replaces the current ledger with the backup. The current ledger is first saved to data/backups/ as
gatekeeper-<time>-before-restore.db, so a restore can itself be undone. It refuses while a run is in progress.
NAME is a file name inside data/backups/, as --list prints it. Nothing outside that folder can be restored.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "service"))
sys.path.insert(0, str(ROOT / "scripts"))

import gk_home  # noqa: E402

COUNTS = (("ideas", "ideas"), ("runs", "runs"), ("decisions", "decisions"))
RUN_GUARD = timedelta(minutes=30)


def _ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def _one(con: sqlite3.Connection, sql: str):
    try:
        row = con.execute(sql).fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        return None


def describe(path: Path) -> dict:
    """What a backup holds, read without changing it. A missing table reads as zero."""
    out = {"name": path.name, "size_kb": round(path.stat().st_size / 1024),
           "saved": datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
           "label": None, "company": None, "ok": True}
    stem = path.stem.removeprefix("gatekeeper-")
    parts = stem.split("-", 2)
    if len(parts) == 3 and parts[1].isdigit() and len(parts[1]) == 6:
        out["label"] = parts[2]
    elif len(parts) >= 2 and not parts[1].isdigit():
        out["label"] = "-".join(parts[1:])
    try:
        con = _ro(path)
    except sqlite3.Error:
        return {**out, "ok": False}
    try:
        if _one(con, "PRAGMA integrity_check") != "ok":
            return {**out, "ok": False}
        for key, table in COUNTS:
            out[key] = _one(con, f"SELECT COUNT(*) FROM {table}") or 0
        body = _one(con, "SELECT body FROM config_versions WHERE section='profile' ORDER BY id DESC LIMIT 1")
        if body:
            try:
                out["company"] = json.loads(body).get("company")
            except (ValueError, AttributeError):
                pass
        out["last_run"] = _one(con, "SELECT started_at FROM runs ORDER BY id DESC LIMIT 1")
        out["last_brief"] = _one(con, "SELECT created_at FROM briefs ORDER BY id DESC LIMIT 1")
    finally:
        con.close()
    return out


def list_backups(home: Path) -> list[dict]:
    folder = home / "data" / "backups"
    files = sorted(folder.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True) if folder.is_dir() else []
    return [describe(p) for p in files]


def restore(home: Path, name: str, echo=print) -> dict:
    folder = (home / "data" / "backups").resolve()
    src = (folder / name).resolve()
    if src.parent != folder or src.suffix != ".db" or not src.is_file():
        raise SystemExit(f"{name!r} is not a backup in data/backups/. Run --list to see the names.")
    info = describe(src)
    if not info["ok"]:
        raise SystemExit(f"{name} did not pass the integrity check, so it was not restored.")
    db = home / "data" / "gatekeeper.db"

    now = datetime.now(timezone.utc)
    cur = sqlite3.connect(db, timeout=8)
    try:
        live = cur.execute("SELECT id, started_at FROM runs WHERE status='running' ORDER BY id DESC LIMIT 1").fetchone()
        if live and now - datetime.fromisoformat(live[1]) < RUN_GUARD:
            raise SystemExit(f"Run {live[0]} is in progress (started {live[1]}). Wait for it to finish, then restore.")
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        saved = folder / f"gatekeeper-{stamp}-before-restore.db"
        n = 1
        while saved.exists():            # never overwrite a backup, even one made a second ago
            n += 1
            saved = folder / f"gatekeeper-{stamp}-before-restore-{n}.db"
        target = sqlite3.connect(saved)
        try:
            cur.backup(target)
        finally:
            target.close()
        echo(f"Saved the current ledger to {saved.name}")
        # The backup API overwrites the pages in place, so the web service and the connector, which hold the
        # file open, see the restored ledger without a restart.
        source = _ro(src)
        try:
            source.backup(cur)
        finally:
            source.close()
        cur.commit()
    finally:
        cur.close()

    # Bring an older backup up to the current schema (additive only), and rewrite context/ from the ledger.
    from gatekeeper.core import Gatekeeper
    gk = Gatekeeper(db, home)
    try:
        gk.export_context()
    finally:
        gk.close()
    echo(f"Restored {name}.")
    return {"restored": name, "saved_current_as": saved.name, **info}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--restore", metavar="NAME")
    ap.add_argument("--yes", action="store_true", help="the person confirmed the restore in chat")
    ap.add_argument("--home", type=Path, default=None)
    a = ap.parse_args()
    if a.home is None:
        a.home = gk_home.ensure_home()
    if a.restore:
        if not a.yes:
            raise SystemExit("Restoring replaces the current ledger. Re-run with --yes once the person has said yes.")
        res = restore(a.home, a.restore)
        if a.json:
            print(json.dumps(res))
        return
    rows = list_backups(a.home)
    if a.json:
        print(json.dumps(rows, indent=1))
        return
    if not rows:
        print("No backups in data/backups/.")
    for n, r in enumerate(rows, 1):
        what = "unreadable" if not r["ok"] else (
            f"{r.get('company') or 'no profile'}: {r['ideas']} ideas, {r['runs']} runs, {r['decisions']} decisions")
        print(f"{n}. {r['name']}  {r['saved']}  {r['size_kb']} KB  {('[' + r['label'] + '] ') if r['label'] else ''}{what}")


if __name__ == "__main__":
    main()
