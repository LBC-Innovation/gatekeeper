"""One named regression test per defect found in the run-4 review (docs/web-app-review/06, section 2).

Each is built from the shape of the real run: seven ideas for a panel capped at five, round-2 scores that fall,
claim ids above 100, and a decision queue that is already full when a serious objection arrives.
They failed against the v1 server and pin the fixes.
"""

import copy
import json
import unittest

from gatekeeper import core
from gatekeeper.core import Rejected
from test_pipeline import SRC, Base

ANALYST_OK = "Fits the recurring revenue directive and uses camera hardware we ship today."


class Defect1PanelCap(Base):
    def _seven_cleared(self, run):
        """Seven candidates from two problems (a run keeps 3 signals and a problem takes 6 candidates), all clearing the gate."""
        g = self.gk
        ids = []
        for p in range(2):
            sid = self.signal(run, 100 + p)
            g.curate_signal(sid, True, "Fresh angle not seen in the ledger", novelty=0.7, four_p="product")
            pid = g.frame_problem(sid, f"Agencies cannot do thing {p} without manual work today", "municipal agencies",
                                  "New capability makes it feasible now")["id"]
            for k in range(4 if p == 0 else 3):
                n = p * 10 + k
                ids.append(g.submit_candidate(pid, f"Offer automated thing {n} to municipal agencies in region {n}",
                                              f"A description of candidate {n} with mechanism delta{n} and epsilon{n} zeta{n} for agencies.",
                                              "forced_relationship", "adjacent", "product",
                                              {"smallest_commitment": "Two week bench test with one camera",
                                               "uncertainty_retired": "Whether detection works at night",
                                               "what_must_be_true": "Detection holds up in low light"})["id"])
        # Descending gate scores so the order is unambiguous: 0.9, 0.85, ... 0.6
        for k, iid in enumerate(ids):
            s = round(0.9 - 0.05 * k, 2)
            g.submit_analyst_review(iid, run, s, "SD-01", s, [], {"ours_to_build": True}, ANALYST_OK, "medium")
        return ids

    def test_cap_is_an_admission_count_not_a_sliding_window(self):
        self.configure()
        g = self.gk
        run = g.start_run("scheduled")["run_id"]
        ids = self._seven_cleared(run)
        cap = g.rules()["panel_per_run"]

        work = g.list_panel_work(run)
        admitted = [w["idea_id"] for w in work["full_panel"]]
        self.assertEqual(admitted, ids[:cap])
        self.assertEqual(work["held_for_next_run"], len(ids) - cap)

        # Full panel on the admitted five, each with a serious objection so round 2 is due.
        for iid in admitted:
            self.full_panel(iid, run, a=(0.8, 0.8), steward=0.7, objection=0.8)
        # Round-2 analyst revisions drop every score. In v1 this pushed finished ideas out of the window
        # and let the two held ideas slide in (7 ideas through a cap of 5).
        for iid in admitted:
            g.submit_analyst_review(iid, run, 0.3, "SD-01", 0.3, [], {"ours_to_build": True}, ANALYST_OK, "medium",
                                    round=2, revision_reason="The objection lowered my fit and my capability view")
        work = g.list_panel_work(run)
        self.assertEqual([w for w in work["full_panel"] if w["idea_id"] not in admitted], [])
        self.assertEqual(work["held_for_next_run"], len(ids) - cap)
        self.assertEqual(len(g.q("SELECT 1 FROM panel_admissions WHERE run_id=?", (run,))), cap)

    def test_a_held_idea_cannot_be_reviewed_by_the_full_panel(self):
        self.configure()
        g = self.gk
        run = g.start_run("scheduled")["run_id"]
        ids = self._seven_cleared(run)
        g.list_panel_work(run)
        held = ids[-1]
        with self.assertRaisesRegex(Rejected, "held for the next run"):
            g.submit_steward_review(held, run, 0.6, 0.1, [], "Moves the mix toward the adjacent target with little overlap.", "medium")
        with self.assertRaisesRegex(Rejected, "held for the next run"):
            g.raise_objection(held, run, "Agencies may not have budget authority to buy this outside a contract cycle.", 0.3,
                              "A signed letter of intent from one agency")

    def test_direct_writes_cannot_exceed_the_cap_either(self):
        """A caller that never asks for the worklist still hits the cap: admission happens on first write."""
        self.configure()
        g = self.gk
        run = g.start_run("scheduled")["run_id"]
        ids = self._seven_cleared(run)
        cap = g.rules()["panel_per_run"]
        for iid in ids[:cap]:
            g.submit_steward_review(iid, run, 0.6, 0.1, [], "Moves the mix toward the adjacent target with little overlap.", "medium")
        with self.assertRaisesRegex(Rejected, "held for the next run"):
            g.submit_steward_review(ids[cap], run, 0.6, 0.1, [], "Moves the mix toward the adjacent target with little overlap.", "medium")

    def test_held_ideas_are_admitted_in_the_next_run(self):
        self.configure()
        g = self.gk
        run = g.start_run("scheduled")["run_id"]
        ids = self._seven_cleared(run)
        cap = g.rules()["panel_per_run"]
        for iid in g.list_panel_work(run)["full_panel"]:
            self.full_panel(iid["idea_id"], run, a=(0.8, 0.8), steward=0.7, objection=0.1)
        g.compute_board(run)
        g.finish_run(run)
        run2 = g.start_run("scheduled")["run_id"]
        work = g.list_panel_work(run2)
        self.assertEqual([w["idea_id"] for w in work["full_panel"]], ids[cap:])
        self.assertEqual(work["held_for_next_run"], 0)


class Defect2CapabilityConstraint(Base):
    def _idea(self):
        self.configure()
        run = self.gk.start_run("manual")["run_id"]
        return run, self.candidate(run, 1)

    def test_a_no_path_gap_always_leaves_a_record_even_when_it_did_not_bind(self):
        run, iid = self._idea()
        r = self.gk.submit_analyst_review(iid, run, 0.6, "SD-01", 0.3, [{"capability": "Legal authority", "acquisition_path": "none"}],
                                          {}, ANALYST_OK, "medium")
        self.assertFalse(r["capability_capped"])
        c = {x["rule"]: x for x in r["constraints"]}["no_path_gap"]
        self.assertTrue(c["applies"])
        self.assertFalse(c["binding"])
        self.assertEqual(c["ceiling"], 0.5)
        stored = self.gk.get_reviews(iid)["reviews"][0]["sub"]
        self.assertEqual({x["rule"] for x in stored["constraints"]}, {"no_path_gap"})

    def test_a_binding_cap_is_marked_binding(self):
        run, iid = self._idea()
        r = self.gk.submit_analyst_review(iid, run, 0.6, "SD-01", 0.9, [{"capability": "Legal authority", "acquisition_path": "none"}],
                                          {}, ANALYST_OK, "medium")
        self.assertTrue(r["capability_capped"])
        self.assertTrue({x["rule"]: x for x in r["constraints"]}["no_path_gap"]["binding"])

    def test_no_gap_means_the_constraint_does_not_apply(self):
        run, iid = self._idea()
        r = self.gk.submit_analyst_review(iid, run, 0.6, "SD-01", 0.9, [{"capability": "Cameras", "acquisition_path": "build"}],
                                          {}, ANALYST_OK, "medium")
        self.assertFalse({x["rule"]: x for x in r["constraints"]}["no_path_gap"]["applies"])

    def test_acquisition_path_is_a_strict_enum(self):
        run, iid = self._idea()
        with self.assertRaisesRegex(Rejected, "acquisition_path"):
            self.gk.submit_analyst_review(iid, run, 0.6, "SD-01", 0.6, [{"capability": "Cameras", "acquisition_path": "magic"}],
                                          {}, ANALYST_OK, "medium")


class Defect3ClaimReferences(Base):
    def _idea_with_many_claims(self):
        """Push claim ids past 100, which is when the v1 check started rejecting claim references."""
        self.configure()
        run = self.gk.start_run("manual")["run_id"]
        iid = self.candidate(run, 1)
        self.gk.submit_analyst_review(iid, run, 0.7, "SD-01", 0.7, [], {}, ANALYST_OK, "medium")
        ids = []
        for n in range(105):
            ids += self.gk.add_evidence(iid, [dict(SRC, field="business_case", statement=f"Fact number {n} from a source")])["claim_ids"]
        return run, iid, ids

    def test_claim_references_are_references_not_figures(self):
        for text in ("Claim 136 shows the rule", "claims 79/80 agree", "claim ids 112, 114 and 141", "see claims 109 to 115",
                     "(claim 107)", "claim #108 says so", "claims 112 and 114"):
            self.assertEqual(core.unbacked_numbers(text, []), [], text)
        # A figure next to a reference is still a figure.
        self.assertEqual(core.unbacked_numbers("Claim 136 says costs rise 40%", []), ["40%"])

    def test_a_reference_to_a_real_claim_is_accepted_in_a_rationale(self):
        run, iid, ids = self._idea_with_many_claims()
        hi = max(ids)
        r = self.gk.raise_objection(iid, run, f"The weak point is the timeline, which claim {hi} dates to July and claim {ids[-2]} confirms.",
                                    0.4, "A confirmed date from the agency")
        self.assertIn("objection_id", r)

    def test_a_reference_to_a_claim_that_does_not_exist_is_rejected(self):
        run, iid, ids = self._idea_with_many_claims()
        with self.assertRaisesRegex(Rejected, "claim 9999"):
            self.gk.raise_objection(iid, run, "The weak point is the timeline, which claim 9999 dates to July.",
                                    0.4, "A confirmed date from the agency")

    def test_rejections_are_attributed_to_the_running_run(self):
        self.configure()
        run = self.gk.start_run("manual")["run_id"]
        self.gk.log_rejection("add_evidence", "malformed claim", {"idea_id": "IDEA-2026-0001"})
        row = self.gk.q1("SELECT run_id FROM rejections ORDER BY id DESC LIMIT 1")
        self.assertEqual(row["run_id"], run)


class Defect4Round2Packet(Base):
    def _split(self):
        self.configure()
        g = self.gk
        run = g.start_run("manual")["run_id"]
        iid = self.candidate(run, 1)
        self.full_panel(iid, run, a=(0.9, 0.9), steward=0.2, objection=0.1)  # spread triggers round 2
        return run, iid

    def test_packet_carries_the_full_round_one_review(self):
        run, iid = self._split()
        for role in ("analyst", "registrar", "steward"):
            pkt = self.gk.get_round2_packet(iid, role)
            r1 = pkt["your_round1"]
            self.assertIn("sub", r1)
            self.assertIn("confidence", r1)
            self.assertIn("resubmit_template", pkt)
            self.assertEqual(pkt["resubmit_template"]["tool"], f"submit_{role}_review")

    def test_a_hold_round_two_reproduces_round_one_exactly(self):
        run, iid = self._split()
        g = self.gk
        before = {r["role"]: r["sub"] for r in g.get_reviews(iid)["reviews"]}
        g.submit_analyst_review(iid, run, None, None, None, None, None, "Holding my view after reading the others.",
                                "medium", round=2, revision_reason="Nothing in the other rationales changed my mind")
        g.submit_registrar_review(iid, run, None, "Holding my view after reading the others.", "medium",
                                  round=2, revision_reason="Nothing in the other rationales changed my mind")
        g.submit_steward_review(iid, run, None, None, None, "Holding my view after reading the others.", "medium",
                                round=2, revision_reason="Nothing in the other rationales changed my mind")
        after = {}
        for r in g.get_reviews(iid)["reviews"]:
            if r["round"] == 2:
                after[r["role"]] = r["sub"]
        for role in ("analyst", "registrar", "steward"):
            b, a = copy.deepcopy(before[role]), copy.deepcopy(after[role])
            self.assertEqual(b, a, role)

    def test_a_delta_changes_only_what_was_sent(self):
        run, iid = self._split()
        g = self.gk
        g.submit_steward_review(iid, run, 0.5, None, None, "Revising on the overlap argument alone.", "medium",
                                round=2, revision_reason="Analyst showed the overlap is smaller than I assumed")
        r1 = [r for r in g.get_reviews(iid)["reviews"] if r["role"] == "steward"]
        self.assertEqual(r1[0]["sub"]["cannibalization_risk"], r1[1]["sub"]["cannibalization_risk"])
        self.assertEqual(r1[1]["score"], 0.5)

    def test_round_one_still_requires_every_field(self):
        self.configure()
        run = self.gk.start_run("manual")["run_id"]
        iid = self.candidate(run, 1)
        with self.assertRaisesRegex(Rejected, "strategic_fit"):
            self.gk.submit_analyst_review(iid, run, None, None, 0.5, [], {}, ANALYST_OK, "medium")


class Defect5QueueReconciliation(Base):
    def _queued_three(self):
        self.configure()
        g = self.gk
        run = g.start_run("scheduled")["run_id"]
        ids = [self.candidate(run, n) for n in range(1, 4)]
        for iid in ids:
            self.full_panel(iid, run, a=(0.7, 0.6), steward=0.6, objection=0.2)
        g.compute_board(run)
        g.finish_run(run)
        return ids

    def test_a_queued_item_follows_the_latest_board(self):
        ids = self._queued_three()
        g = self.gk
        before = {q["idea_id"]: q for q in g.get_queue()}
        self.assertEqual(set(before), set(ids))
        target = ids[0]
        run2 = g.start_run("scheduled")["run_id"]
        g.raise_objection(target, run2, "A late finding means the agency cannot buy this outside a contract cycle at all.", 0.8,
                          "A procurement officer confirming off-cycle purchasing")
        g.compute_board(run2)
        now = {q["idea_id"]: q for q in g.get_queue()}
        self.assertEqual(now[target]["recommended_action"], "REVIEW_OBJECTION")
        self.assertEqual(len([q for q in g.get_queue() if q["idea_id"] == target]), 1)
        old = g.q("SELECT status FROM queue_items WHERE idea_id=? ORDER BY id", (target,))
        self.assertEqual([o["status"] for o in old], ["superseded", "open"])

    def test_a_serious_objection_enters_a_full_queue(self):
        ids = self._queued_three()
        g = self.gk
        self.assertEqual(len(g.get_queue()), g.rules()["queue_size"])
        run2 = g.start_run("scheduled")["run_id"]
        d = self.candidate(run2, 9)
        self.full_panel(d, run2, a=(0.7, 0.6), steward=0.6, objection=0.8)
        g.compute_board(run2)
        queued = [q["idea_id"] for q in g.get_queue()]
        self.assertIn(d, queued)
        self.assertGreater(len(queued), g.rules()["queue_size"])

    def test_every_open_item_matches_its_board_snapshot(self):
        ids = self._queued_three()
        g = self.gk
        run2 = g.start_run("scheduled")["run_id"]
        g.raise_objection(ids[1], run2, "A late finding means the agency cannot buy this outside a contract cycle at all.", 0.8,
                          "A procurement officer confirming off-cycle purchasing")
        board = g.compute_board(run2)
        action = {r["idea_id"]: r["action"] for r in board["board"]}
        for q in g.get_queue():
            self.assertEqual(q["recommended_action"], action[q["idea_id"]], q["idea_id"])
            self.assertIsNotNone(q["snapshot_id"])

    def test_an_item_that_became_a_park_leaves_the_queue(self):
        ids = self._queued_three()
        g = self.gk
        run2 = g.start_run("scheduled")["run_id"]
        # Both voting reviewers revise sharply down after a serious objection, so the idea now scores below the park line.
        g.raise_objection(ids[2], run2, "A late finding means the agency cannot buy this outside a contract cycle at all.", 0.6,
                          "A procurement officer confirming off-cycle purchasing")
        g.submit_analyst_review(ids[2], run2, 0.1, "SD-01", 0.1, [], {}, ANALYST_OK, "medium", round=2, revision_reason="Objection changed my view")
        g.submit_steward_review(ids[2], run2, 0.1, None, None, "Revised down on the objection.", "medium", round=2,
                                revision_reason="Objection changed my view")
        board = g.compute_board(run2)
        self.assertEqual({r["idea_id"]: r["action"] for r in board["board"]}[ids[2]], "PARK")
        self.assertNotIn(ids[2], [q["idea_id"] for q in g.get_queue()])


class Defect6FinishedRunHasNoWorkingStage(Base):
    def test_finish_run_closes_open_stages(self):
        g = self.gk
        run = g.start_run("manual")["run_id"]
        g.update_run_stage(run, "panel", "running", "5 ideas with the panel")
        g.finish_run(run)
        last = g.q1("SELECT status FROM run_stages WHERE run_id=? AND stage='panel' ORDER BY id DESC", (run,))
        self.assertNotEqual(last["status"], "running")


class Defect7RunGuard(Base):
    def test_a_second_run_is_refused_while_one_is_in_progress(self):
        first = self.gk.start_run("scheduled")["run_id"]
        with self.assertRaises(Rejected):
            self.gk.start_run("scheduled")
        self.assertEqual(self.gk.q1("SELECT status FROM runs WHERE id=?", (first,))["status"], "running")


if __name__ == "__main__":
    unittest.main()

