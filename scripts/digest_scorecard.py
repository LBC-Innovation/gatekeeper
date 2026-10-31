"""Score the weekly digest test: did the person decide, or did defaults decide for them?

Usage:
    bin/gk run digest_scorecard.py --since 2026-10-28 [--db <home>/data/gatekeeper.db]

Reads the database read-only. Counts queue items created on or after --since, and how
each one closed: by the person before its default date, by the person late, by default,
or still open. Pass bar: 60% decided by the person on time, and at least one first check funded.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import gk_home  # noqa: E402

PASS_RATE = 0.60


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", required=True, help="test start date, YYYY-MM-DD")
    ap.add_argument("--db", default=str(gk_home.home() / "data" / "gatekeeper.db"))
    a = ap.parse_args()

    con = sqlite3.connect(f"file:{Path(a.db).resolve()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    items = con.execute(
        "SELECT * FROM queue_items WHERE substr(created_at,1,10) >= ? ORDER BY created_at, id", (a.since,)).fetchall()
    # Queue items created before the test can still be decided during it; include those open at the start.
    carried = con.execute(
        "SELECT * FROM queue_items WHERE substr(created_at,1,10) < ? AND (status='open' OR substr(resolved_at,1,10) >= ?)",
        (a.since, a.since)).fetchall()
    items = list(carried) + list(items)

    rows, tally = [], {"on_time": 0, "late": 0, "default": 0, "superseded": 0, "open": 0}
    for q in items:
        d = con.execute(
            "SELECT action, actor, created_at FROM decisions WHERE idea_id=? AND created_at >= ? ORDER BY id LIMIT 1",
            (q["idea_id"], q["created_at"])).fetchone()
        if q["status"] == "open":
            outcome = "open"
        elif q["status"] == "superseded":
            outcome = "superseded"
        elif d and d["actor"] == "human":
            outcome = "on_time" if d["created_at"][:10] <= q["default_on"] else "late"
        else:
            outcome = "default"
        tally[outcome] += 1
        rows.append((q["idea_id"], q["recommended_action"], q["default_on"], outcome, d["action"] if d else ""))

    human = con.execute(
        "SELECT d.action, COUNT(*) n FROM decisions d JOIN ideas i ON i.id = d.idea_id "
        "WHERE d.actor='human' AND i.stage != 'exemplar' AND substr(d.created_at,1,10) >= ? GROUP BY d.action",
        (a.since,)).fetchall()
    by_action = {r["action"]: r["n"] for r in human}
    funded = by_action.get("promote", 0)
    answered = con.execute(
        "SELECT COUNT(*) FROM objections WHERE status != 'open'").fetchone()[0]
    open_obj = con.execute("SELECT COUNT(*) FROM objections WHERE status = 'open'").fetchone()[0]
    ranks = con.execute("SELECT COUNT(*) FROM my_rank WHERE substr(created_at,1,10) >= ?", (a.since,)).fetchone()[0]

    closed = tally["on_time"] + tally["late"] + tally["default"]
    rate = tally["on_time"] / closed if closed else None

    print(f"# Digest test scorecard, since {a.since}\n")
    print("| Idea | Recommended | Default on | Outcome | Action |")
    print("| --- | --- | --- | --- | --- |")
    for r in rows:
        print("| " + " | ".join(r) + " |")
    print()
    print(f"Closed items: {closed} (on time {tally['on_time']}, late {tally['late']}, by default {tally['default']}); "
          f"open {tally['open']}, superseded {tally['superseded']}")
    print(f"Decided by the person on time: {'n/a' if rate is None else f'{rate:.0%}'} (bar {PASS_RATE:.0%})")
    print(f"Human decisions by action: {by_action or 'none'}")
    print(f"First checks funded (promote): {funded} (bar 1)")
    print(f"Objections answered or accepted: {answered}; still open: {open_obj}")
    print(f"Own rankings given: {ranks}")
    if rate is not None:
        ok = rate >= PASS_RATE and funded >= 1
        print(f"\nSo far: {'PASS' if ok else 'NOT YET'}")


if __name__ == "__main__":
    main()
