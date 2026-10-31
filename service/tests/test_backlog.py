"""The backlog index: loading an ADO snapshot, searching it for one idea, and filing a check."""

import sqlite3
import unittest
from pathlib import Path

from gatekeeper.core import Rejected
from test_pipeline import Base

ROWS = [
    # id, title, type, state, parent, tags, started_at
    (1, "Widget Enforcement (WGT) Enhancements - 2026", "Epic", "Active", None, "", "2026-01-05"),
    (2, "Widget Event Ingestion", "Feature", "Closed", 1, "", "2025-03-01"),
    (3, "Warning Periods", "Feature", "Closed", None, "", "2025-05-01"),
    (4, "Operations and Repairs", "Feature", "New", None, "", None),
    (5, "Toolbox Phase 2: idempotent recovery", "Feature", "Closed", None, "toolbox:in-flight", "2026-08-01"),
    (6, "Admin cleanup", "Feature", "Closed", None, "", None),            # closed without ever starting
    (10, "Parse widget events", "User Story", "Closed", 2, "", "2025-03-02"),
    (11, "Widget notice template", "User Story", "Active", 1, "", "2026-09-01"),
    (12, "Widget reporting", "Task", "New", 1, "", None),
]


def make_snapshot(path: Path, with_orphans=False):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE work_items (id INTEGER PRIMARY KEY, title TEXT, work_item_type TEXT, state TEXT, parent_id INTEGER, "
              "tags TEXT, area_path TEXT, changed_date TEXT, closed_date TEXT, started_at TEXT)")
    for i, t, ty, st, p, tags, s in ROWS:
        c.execute("INSERT INTO work_items VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (i, t, ty, st, p, tags, "Platform\\X", "2026-10-01T00:00:00Z", None, s))
    c.commit()
    c.close()


class BacklogTests(Base):
    def setUp(self):
        super().setUp()
        self.snap = Path(self.tmp.name) / "ado.db"
        make_snapshot(self.snap)
        (Path(self.tmp.name) / "backlog_vocabulary.json").write_text(
            '{"aliases": {"wgt": ["widget", "enforcement"]}, "specific": ["warning"], "exclude": ["toolbox"]}')
        self.configure()
        self.run_id = self.gk.start_run()["run_id"]

    def idea(self, text):
        self.n = getattr(self, "n", 0) + 1
        return self.candidate(self.run_id, self.n, text=text)

    def test_sync_loads_top_level_only_and_buckets_them(self):
        r = self.gk.sync_backlog(str(self.snap))
        self.assertEqual(r["loaded"], 5)  # the Toolbox feature is left out
        rows = {x["id"]: x for x in self.gk.q("SELECT * FROM backlog_items")}
        self.assertNotIn(5, rows, "the person's own tooling is excluded")
        self.assertEqual(rows[1]["bucket"], "in_flight")
        self.assertEqual(rows[2]["bucket"], "done")
        self.assertEqual(rows[4]["bucket"], "not_started")
        self.assertEqual((rows[1]["child_total"], rows[1]["child_active"], rows[1]["child_open"]), (3, 1, 1))  # a Feature under an Epic counts as its child

    def test_closed_without_a_start_is_not_counted_as_done(self):
        self.gk.sync_backlog(str(self.snap))
        row = self.gk.q1("SELECT bucket FROM backlog_items WHERE id=6")
        self.assertEqual(row["bucket"], "closed_unstarted")

    def test_search_finds_the_area_and_returns_nothing_for_unrelated_ideas(self):
        self.gk.sync_backlog(str(self.snap))
        hit = self.gk.find_backlog_matches(self.idea("Run a widget enforcement warning period at one intersection for agencies"))
        ids = [m["id"] for m in hit["matches"]]
        self.assertIn(1, ids)
        miss = self.gk.find_backlog_matches(self.idea("Publish a reliability scorecard with quarterly service credits"))
        self.assertEqual(miss["matches"], [])

    def test_hyphenated_words_are_split_and_company_vocabulary_expands(self):
        self.gk.sync_backlog(str(self.snap))
        hit = self.gk.find_backlog_matches(self.idea("Run WGT in warning-only mode at a reference intersection for agencies"))
        ids = [m["id"] for m in hit["matches"]]
        self.assertIn(3, ids, "warning-only must reach 'Warning Periods'")
        self.assertIn(1, ids, "WGT must reach 'Widget'")

    def test_search_before_load_says_so(self):
        out = self.gk.find_backlog_matches(self.idea("Offer widget enforcement to agencies"))
        self.assertFalse(out["synced"])

    def test_check_records_verdicts_and_sourced_claims(self):
        self.gk.sync_backlog(str(self.snap))
        iid = self.idea("Run a widget enforcement warning period at one intersection for agencies")
        out = self.gk.submit_backlog_check(iid, "Widget work is in flight under one Epic.", [
            {"item_id": 1, "verdict": "in_flight", "reason": "The 2026 WGT epic is active with open stories."},
            {"item_id": 4, "verdict": "unrelated", "reason": "Operations backlog, different problem."}], ["widget"], run_id=self.run_id)
        self.assertEqual(len(out["claim_ids"]), 1, "unrelated verdicts leave no claim")
        ev = [c for c in self.gk.get_evidence(iid) if c["field"] == "backlog"]
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["kind"], "source")
        got = self.gk.get_backlog_check(iid)
        self.assertTrue(got["current"])
        self.assertEqual(got["verdicts"][0]["title"], "Widget Enforcement (WGT) Enhancements - 2026")
        again = self.gk.find_backlog_matches(iid)
        self.assertEqual(again["existing_check"], out["check_id"])

    def test_an_empty_check_is_allowed_and_an_unknown_item_is_not(self):
        self.gk.sync_backlog(str(self.snap))
        iid = self.idea("Publish a reliability scorecard with quarterly service credits")
        self.assertTrue(self.gk.submit_backlog_check(iid, "Nothing in the backlog overlaps this idea.", [])["check_id"])
        with self.assertRaises(Rejected):
            self.gk.submit_backlog_check(iid, "Bad item id should be rejected.", [
                {"item_id": 999, "verdict": "related", "reason": "There is no such item."}])

    def test_reload_marks_old_checks_not_current(self):
        self.gk.sync_backlog(str(self.snap))
        iid = self.idea("Run a widget enforcement warning period at one intersection for agencies")
        self.gk.submit_backlog_check(iid, "Widget work is in flight under one Epic.", [])
        self.gk.conn.execute("UPDATE backlog_meta SET value='2020-01-01T00:00:00+00:00' WHERE key='synced_at'")
        self.assertFalse(self.gk.get_backlog_check(iid)["current"])

    def test_agents_cannot_reload_the_backlog(self):
        from gatekeeper.registry import build_registry
        reg = build_registry(self.gk)
        self.assertFalse(reg["sync_backlog"].on("pipeline"))
        self.assertTrue(reg["find_backlog_matches"].on("pipeline"))
        self.assertTrue(reg["submit_backlog_check"].on("pipeline"))


if __name__ == "__main__":
    unittest.main()
