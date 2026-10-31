"""Cost guards found in the 2026-10-29 run: a second run must not replace one in progress, and 'claim 185' is a reference, not a figure."""

import unittest

from gatekeeper.core import Rejected, claim_refs, unbacked_numbers
from test_pipeline import Base


class RunGuard(Base):
    def test_a_second_run_is_refused_while_one_is_in_progress(self):
        first = self.gk.start_run("scheduled")["run_id"]
        with self.assertRaises(Rejected) as cm:
            self.gk.start_run("scheduled")
        self.assertIn(f"Run {first}", str(cm.exception))
        self.assertEqual(self.gk.q1("SELECT status FROM runs WHERE id=?", (first,))["status"], "running")

    def test_a_finished_run_does_not_block_the_next(self):
        self.gk.finish_run(self.gk.start_run("scheduled")["run_id"])
        self.assertTrue(self.gk.start_run("scheduled")["run_id"])

    def test_a_stuck_run_is_replaced(self):
        first = self.gk.start_run("scheduled")["run_id"]
        with self.gk.tx() as c:
            c.execute("UPDATE runs SET started_at='2020-01-01T00:00:00+00:00' WHERE id=?", (first,))
        second = self.gk.start_run("scheduled")
        self.assertEqual(second["abandoned_previous_runs"], 1)


class ClaimReferences(unittest.TestCase):
    def test_claim_numbers_are_references_not_figures(self):
        self.assertEqual(unbacked_numbers("Held, see claim 185 and claims 197, 198.", []), [])
        self.assertEqual(claim_refs("claims 197, 198 and claim #185"), {185, 197, 198})

    def test_a_real_figure_still_needs_a_claim(self):
        self.assertEqual(unbacked_numbers("Costs 4200 per site (claim 185).", []), ["4200"])


if __name__ == "__main__":
    unittest.main()
