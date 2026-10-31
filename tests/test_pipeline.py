"""End-to-end test of the ledger rules and the deliberation mechanism, no model needed.

Run:  python -m unittest discover -s tests -v
"""

import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from gatekeeper import core  # noqa: E402
from gatekeeper import deliberation as D  # noqa: E402
from gatekeeper.core import Gatekeeper, Rejected  # noqa: E402

SRC = {"kind": "source", "url": "https://example.org/report", "retrieved_at": "2026-10-08",
       "excerpt": "The test fixture quotes the source passage here."}

STRATEGY = {
    "directives": [
        {"id": "SD-01", "statement": "Grow recurring software revenue from existing customers", "funded": True},
        {"id": "SD-02", "statement": "Enter adjacent enforcement categories with existing hardware", "funded": True},
        {"id": "SD-03", "statement": "Legacy directive kept for drift testing", "retired": False},
    ],
    "surface": {"products": True, "processes": True, "business_models": True},
    "exclusions": ["Nothing that requires new state legislation to sell"],
    "watchlist": {"new_knowledge": ["edge inference camera"], "industry_market_change": ["enforcement legislation"]},
    "mix_target": {"core": 0.6, "adjacent": 0.3, "transformational": 0.1, "tolerance": 0.05},
    "exploratory_floor": 1,
    "novelty_floor": 0.35,
}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        home = Path(self.tmp.name)
        self.gk = Gatekeeper(home / "data" / "gatekeeper.db", home)

    def tearDown(self):
        self.gk.close()
        self.tmp.cleanup()

    # -- helpers ---------------------------------------------------------------

    def configure(self):
        g = self.gk
        g.set_config("profile", {"company": "Fixture Co", "urls": ["https://example.org"], "summary": "Synthetic test company.",
                                 "confirmed": True}, "test fixture setup")
        g.set_config("strategy", json.loads(json.dumps(STRATEGY)), "test fixture setup")
        g.set_config("capabilities", {"capabilities": [{"id": "CAP-01", "name": "Camera hardware", "maturity": "production"}],
                                      "reachable": [{"name": "Edge ML team", "path": "hire"}]}, "test fixture setup")
        g.set_config("bench", {"benched": []}, "all agents play in the test")
        g.set_config("weights", {"analyst": 0.35, "steward": 0.30, "registrar": 0.20, "redteam_band": 0.15}, "defaults confirmed")
        g.add_portfolio_item("line", "Speed cameras", "core", "test fixture")
        g.add_portfolio_item("line", "Back office platform", "core", "test fixture")
        g.add_portfolio_item("in_flight", "Noise enforcement pilot", "adjacent", "test fixture")

    def signal(self, run, n, sensor="new_knowledge", text=None):
        return self.gk.submit_signal(run, sensor, f"Signal number {n} about topic {n}",
                                     f"https://example.org/s{n}", "2026-10-08",
                                     text or f"Unique excerpt {n} describing development alpha{n} beta{n} gamma{n} in detail.")["id"]

    def candidate(self, run, n, cell="adjacent", text=None):
        sid = self.signal(run, n)
        self.gk.curate_signal(sid, True, "Fresh angle not seen in the ledger", novelty=0.7, four_p="product")
        pid = self.gk.frame_problem(sid, f"Agencies cannot do thing {n} without manual work today",
                                    "municipal agencies", "New capability makes it feasible now")["id"]
        return self.gk.submit_candidate(pid, text or f"Offer automated thing {n} to municipal agencies",
                                        f"A description of candidate {n} with mechanism delta{n} and epsilon{n} for agencies.",
                                        "forced_relationship", cell, "product",
                                        {"smallest_commitment": "Two week bench test with one camera",
                                         "uncertainty_retired": "Whether detection works at night",
                                         "what_must_be_true": "Detection holds up in low light"})["id"]

    def full_panel(self, iid, run, a=(0.8, 0.7), reg=None, steward=0.6, objection=None):
        g = self.gk
        g.submit_analyst_review(iid, run, a[0], "SD-01" if a[0] > 0 else None, a[1], [], {"ours_to_build": True},
                                "Fits the recurring revenue directive and uses camera hardware we ship today.", "medium")
        cid = g.add_evidence(iid, [dict(SRC, field="business_case", statement="A source says demand exists")])["claim_ids"][0]
        dims = reg or {d: {"score": 2, "claim_ids": [cid], "gap": "Needs a validated pilot"} for d in core.READINESS_DIMS}
        g.submit_registrar_review(iid, run, dims, "Evidence exists for each dimension but nothing is validated yet.", "medium")
        g.submit_steward_review(iid, run, steward, 0.1, [], "Moves the mix toward the adjacent target with little overlap.", "medium")
        if objection is not None:
            g.raise_objection(iid, run, "Agencies may not have budget authority to buy this outside a contract cycle.",
                              objection, "A signed letter of intent from one agency")


class PipelineTest(Base):

    def test_setup_status_walks_all_steps(self):
        st = self.gk.get_setup_status()
        self.assertEqual(st["next_step"], "1_read_public")
        self.configure()
        for outcome in ("funded", "killed", "regret_killed"):
            self.gk.add_exemplar(f"Past idea that was {outcome}", outcome, "Known outcome from earlier years",
                                 "adjacent", "product")
        st = self.gk.get_setup_status()
        self.assertEqual(st["next_step"], "7_calibrate")
        self.gk.mark_calibrated("Ranking matched my judgement on the three exemplars")
        self.assertTrue(self.gk.get_setup_status()["complete"])
        self.assertTrue((Path(self.tmp.name) / "context" / "CONTEXT.md").exists())

    def test_config_validation(self):
        with self.assertRaises(Rejected):
            self.gk.set_config("strategy", {**STRATEGY, "mix_target": {"core": 0.9, "adjacent": 0.3, "transformational": 0.1}}, "bad mix")
        with self.assertRaises(Rejected):
            self.gk.set_config("bench", {"benched": [{"role": "analyst", "reason": "trying to bench the spine"}]}, "bad bench")
        with self.assertRaises(Rejected):
            self.gk.set_config("weights", {"analyst": 1.5}, "out of range")

    def test_signal_rules(self):
        self.configure()
        run = self.gk.start_run("manual")["run_id"]
        self.signal(run, 1)
        with self.assertRaisesRegex(Rejected, "Already in the ledger"):
            self.gk.submit_signal(run, "new_knowledge", "Same page again", "https://www.example.org/s1/?utm_source=x",
                                  "2026-10-08", "The same page reached through a tracking link should be caught.")
        with self.assertRaisesRegex(Rejected, "sensor"):
            self.gk.submit_signal(run, "astrology", "Bad sensor", "https://example.org/z", "2026-10-08", "Excerpt long enough here.")
        for n in range(2, 6):
            self.signal(run, n)
        with self.assertRaisesRegex(Rejected, "Cap reached"):
            self.signal(run, 6)

    def test_internal_sensor_file_source(self):
        self.configure()
        run = self.gk.start_run("manual")["run_id"]
        inbox = Path(self.tmp.name) / "inbox"
        inbox.mkdir()
        f = inbox / "tickets.csv"
        f.write_text("id,summary\n1,Agency asks for night mode again\n")
        sid = self.gk.submit_signal(run, "unexpected_occurrences", "Repeated night mode requests", f"file://{f}",
                                    "2026-10-08", "Agency asks for night mode again, third ticket this month.")["id"]
        self.assertTrue(sid.startswith("SIG-"))
        with self.assertRaisesRegex(Rejected, "internal sensors"):
            self.gk.submit_signal(run, "new_knowledge", "Wrong area", f"file://{f}", "2026-10-08", "External area cannot use files.")
        with self.assertRaisesRegex(Rejected, "inbox"):
            self.gk.submit_signal(run, "process_needs", "Outside inbox", "file:///etc/hosts", "2026-10-08", "Should be refused here.")

    def test_curation_floor_duplicate_and_cap(self):
        self.configure()
        run = self.gk.start_run("manual")["run_id"]
        s1 = self.signal(run, 1, text="Edge inference chips cut power for roadside cameras sharply this year")
        s2 = self.signal(run, 2, text="Edge inference chips cut power for roadside cameras sharply this year!")
        with self.assertRaisesRegex(Rejected, "below the floor"):
            self.gk.curate_signal(s1, True, "Interesting but not new at all", novelty=0.2, four_p="product")
        self.gk.curate_signal(s1, True, "Power drop changes deployment economics", novelty=0.6, four_p="product")
        with self.assertRaisesRegex(Rejected, "duplicate"):
            self.gk.curate_signal(s2, True, "Same story from another outlet", novelty=0.6, four_p="product")
        self.gk.curate_signal(s2, True, "Second outlet confirms with a new detail", novelty=0.6, four_p="product",
                              duplicate_override="Adds the vendor's shipping date")
        s3 = self.signal(run, 3)
        self.gk.curate_signal(s3, True, "Different topic entirely kept", novelty=0.5, four_p="process")
        s4 = self.signal(run, 4)
        with self.assertRaisesRegex(Rejected, "Cap reached"):
            self.gk.curate_signal(s4, True, "Over the kept cap for the run", novelty=0.9, four_p="process")

    def test_fidelity_rule_blocks_uncited_figures(self):
        self.configure()
        run = self.gk.start_run("manual")["run_id"]
        sid = self.signal(run, 1)
        self.gk.curate_signal(sid, True, "Keep for the fidelity test", novelty=0.6, four_p="product")
        pid = self.gk.frame_problem(sid, "Agencies pay too much for camera maintenance visits",
                                    "agencies", "Maintenance costs rose this year")["id"]
        fc = {"smallest_commitment": "Price a pilot with one agency", "uncertainty_retired": "Willingness to pay",
              "what_must_be_true": "Agencies see maintenance as a line item"}
        with self.assertRaisesRegex(Rejected, "Fidelity rule"):
            self.gk.submit_candidate(pid, "Remote diagnostics that cut maintenance visits by 40%",
                                     "Sell a $12,000 annual diagnostics add-on to existing customers.",
                                     "compounding", "core", "product", fc)
        ok = self.gk.submit_candidate(pid, "Remote diagnostics that cut maintenance visits by 40%",
                                      "Sell a $12,000 annual diagnostics add-on to existing customers.",
                                      "compounding", "core", "product", fc,
                                      claims=[dict(SRC, field="effect", statement="Vendor case study reports 40% fewer visits"),
                                              {"kind": "estimate", "field": "price", "statement": "Price of $12,000 per year",
                                               "confidence": "low", "basis": "Analogy to existing support contract pricing"}])
        self.assertTrue(ok["id"].startswith("IDEA-"))
        ev = self.gk.get_evidence(ok["id"])
        self.assertEqual({e["kind"] for e in ev}, {"source", "estimate"})

    def test_analyst_gate_and_directive_rule(self):
        self.configure()
        run = self.gk.start_run("manual")["run_id"]
        iid = self.candidate(run, 1)
        with self.assertRaisesRegex(Rejected, "Analyst must clear it first"):
            self.gk.submit_steward_review(iid, run, 0.5, 0.1, [], "Too early for the steward to review this one.", "low")
        with self.assertRaisesRegex(Rejected, "active directive"):
            self.gk.submit_analyst_review(iid, run, 0.6, None, 0.5, [], {}, "Fits something but no directive cited here.", "low")
        r = self.gk.submit_analyst_review(iid, run, 0.05, "SD-01", 0.9,
                                          [{"capability": "Night vision", "acquisition_path": "none"}], {},
                                          "Weak strategic fit and a capability gap with no path to close it.", "medium")
        self.assertTrue(r["capability_capped"])
        self.assertAlmostEqual(r["score"], 0.275, places=4)   # (0.05 + capped 0.5) / 2
        self.assertEqual(r["stage"], "parked_auto")            # below the 0.30 gate

    def test_registrar_evidence_rules(self):
        self.configure()
        run = self.gk.start_run("manual")["run_id"]
        iid = self.candidate(run, 1)
        self.gk.submit_analyst_review(iid, run, 0.8, "SD-01", 0.7, [], {}, "Strong fit with the recurring revenue directive.", "high")
        dims = {d: {"score": 2, "claim_ids": [], "gap": "Missing evidence"} for d in core.READINESS_DIMS}
        with self.assertRaisesRegex(Rejected, "evidenced"):
            self.gk.submit_registrar_review(iid, run, dims, "Claims readiness without citing any evidence at all.", "low")
        est = self.gk.add_evidence(iid, [{"kind": "estimate", "field": "prototype", "statement": "Prototype likely feasible",
                                          "confidence": "low", "basis": "Similar firmware exists in house"}])["claim_ids"][0]
        dims = {d: {"score": 1, "gap": "Only asserted so far"} for d in core.READINESS_DIMS}
        dims["prototype"] = {"score": 3, "claim_ids": [est]}
        with self.assertRaisesRegex(Rejected, "validated"):
            self.gk.submit_registrar_review(iid, run, dims, "Prototype marked validated on an estimate alone.", "low")
        dims["prototype"] = {"score": 2, "claim_ids": [est], "gap": "Needs a bench test"}
        r = self.gk.submit_registrar_review(iid, run, dims, "Mostly asserted; prototype has an estimate behind it.", "medium")
        self.assertAlmostEqual(r["score"], 7 / 18, places=4)

    def test_redteam_blind_view(self):
        self.configure()
        run = self.gk.start_run("manual")["run_id"]
        iid = self.candidate(run, 1)
        blind = self.gk.get_idea_blind(iid)
        self.assertNotIn("sponsor", blind)
        self.assertNotIn("origin", blind)
        self.assertNotIn("sensor", blind.get("signal", {}))
        self.assertIn("sponsor", self.gk.get_idea(iid))

    def test_deliberation_round2_and_board(self):
        self.configure()
        run = self.gk.start_run("manual")["run_id"]
        a = self.candidate(run, 1)                      # agreeable panel
        b = self.candidate(run, 2)                      # split panel -> round 2
        c = self.candidate(run, 3, cell="transformational")  # severe objection
        self.full_panel(a, run, a=(0.8, 0.8), steward=0.75, objection=0.2)
        self.full_panel(b, run, a=(0.9, 0.9), steward=0.2, objection=0.1)
        self.full_panel(c, run, a=(0.7, 0.6), steward=0.7, objection=0.8)

        work = self.gk.list_panel_work(run)
        r2 = {x["idea_id"]: x for x in work["round2"]}
        self.assertIn(b, r2)                            # spread 0.9 vs 0.2
        self.assertIn(c, r2)                            # severity 0.8
        self.assertNotIn(a, r2)

        pkt = self.gk.get_round2_packet(b, "steward")
        self.assertTrue(all(o["panelist"].startswith("Panelist") for o in pkt["other_panelists"]))
        with self.assertRaisesRegex(Rejected, "revision_reason"):
            self.gk.submit_steward_review(b, run, 0.5, 0.1, [], "Revising after seeing the other rationales here.", "medium",
                                          round=2)
        self.gk.submit_steward_review(b, run, 0.5, 0.1, [], "Revising after seeing the other rationales here.", "medium",
                                      round=2, revision_reason="Analyst showed the overlap is smaller than I assumed")
        with self.assertRaisesRegex(Rejected, "no open round-1"):
            self.gk.submit_steward_review(b, run, 0.6, 0.1, [], "Trying to revise a second time in round two.", "medium",
                                          round=2, revision_reason="Second revision should be refused")

        board = self.gk.compute_board(run)
        rows = {r["idea_id"]: r for r in board["board"]}
        self.assertEqual(rows[c]["action"], "REVIEW_OBJECTION")
        self.assertAlmostEqual(rows[c]["band"], 0.15 * 0.8, places=4)
        # arithmetic for a: analyst and steward vote; registrar readiness gates promote but is not in the score
        w = D.normalize_weights(self.gk.weights())
        exp = w["analyst"] * 0.8 + w["steward"] * 0.75
        self.assertAlmostEqual(rows[a]["score"], round(exp, 4), places=4)
        self.assertEqual(rows[a]["action"], "PROMOTE")
        q = board["queue"]
        self.assertLessEqual(len(q), 3)
        self.assertIn(c, [x["idea_id"] for x in q])     # objection and exploratory slot
        self.assertTrue(all(x["default_on"] for x in q))

        rec = self.gk.get_idea_record(a)
        self.assertIn("=", rec["deliberation"]["arithmetic"])
        self.assertIn("readiness for the first check", rec["deliberation"]["arithmetic"])

    def test_new_objection_supersedes_open_one(self):
        self.configure()
        run = self.gk.start_run("manual")["run_id"]
        iid = self.candidate(run, 1)
        self.full_panel(iid, run, objection=0.8)
        before = self.gk.compute_board(run)["board"][0]
        self.assertAlmostEqual(before["band"], 0.15 * 0.8, places=4)
        r = self.gk.raise_objection(iid, run, "Re-argued: the first check would surface the budget question in one call.",
                                    0.25, "One agency confirms budget authority in writing")
        self.assertEqual(len(r["superseded"]), 1)
        objs = {o["id"]: o for o in self.gk.get_idea_record(iid)["objections"]}
        self.assertEqual(objs[r["superseded"][0]]["status"], "superseded")
        after = [x for x in self.gk.compute_board(run)["board"] if x["idea_id"] == iid][0]
        self.assertAlmostEqual(after["band"], 0.15 * 0.25, places=4)   # the new severity replaces the old band

    def test_decisions_rank_defaults_and_kill_triggers(self):
        self.configure()
        run = self.gk.start_run("manual")["run_id"]
        a = self.candidate(run, 1)
        b = self.candidate(run, 2)
        self.full_panel(a, run, a=(0.8, 0.8), steward=0.75, objection=0.1)
        self.full_panel(b, run, a=(0.7, 0.6), steward=0.6, objection=0.1)
        self.gk.compute_board(run)
        with self.assertRaisesRegex(Rejected, "real reason"):
            self.gk.decide(a, "promote", "looks good!!")
        self.gk.decide(a, "promote", "Fits SD-01 and the pilot is cheap")
        self.assertEqual(self.gk._idea(a)["stage"], "promoted")
        res = self.gk.set_my_rank([b, a], note="I like b more")
        self.assertTrue(res["disagreements_with_board"])
        self.gk.finish_run(run)

        # Default executes when the date passes.
        open_items = self.gk.get_queue()
        self.assertTrue(any(x["idea_id"] == b for x in open_items))
        real_today = core.today
        core.today = lambda: real_today() + timedelta(days=30)
        try:
            # Strategic drift: retire the directive the promoted idea matched.
            st = json.loads(json.dumps(STRATEGY))
            st["directives"][0]["retired"] = True
            out = self.gk.set_config("strategy", st, "SD-01 retired by the board")
            self.assertGreater(out["rescore_jobs_queued"], 0)
            r2 = self.gk.start_run("scheduled")
            self.assertTrue(any(d["idea_id"] == b and d["action"] == "park" for d in r2["defaults_executed"]))
            self.assertEqual(r2["kill_recommendations_added"], 1)
            kills = [x for x in self.gk.get_queue() if x["kind"] == "kill"]
            self.assertIn("strategic drift", kills[0]["why"])
            self.gk.decide(a, "keep", "Still worth it under SD-02, re-scoring next run")
        finally:
            core.today = real_today

    def test_brief_and_quiet_day(self):
        self.configure()
        run = self.gk.start_run("manual")["run_id"]
        data = self.gk.get_brief_data(run)
        self.assertIn("quiet_day", data)
        with self.assertRaisesRegex(Rejected, "at most 5 lines"):
            self.gk.write_brief(run, "\n".join(f"line {i} of a long quiet brief" for i in range(8)), quiet=True)
        out = self.gk.write_brief(run, "Quiet day. Nothing crossed a threshold.\nPortfolio in band.", quiet=True)
        self.assertTrue(Path(out["path"]).exists())

    def test_calibration(self):
        self.configure()
        ids = {}
        for outcome, s in (("funded", (0.9, 0.8)), ("killed", (0.4, 0.3)), ("regret_killed", (0.7, 0.6))):
            ids[outcome] = self.gk.add_exemplar(f"Exemplar idea {outcome} for calibration", outcome,
                                                "Known outcome from earlier years", "adjacent", "product")["id"]
        run = self.gk.start_run("calibration")["run_id"]
        for outcome, iid in ids.items():
            sc = {"funded": (0.9, 0.8), "killed": (0.4, 0.3), "regret_killed": (0.7, 0.6)}[outcome]
            self.full_panel(iid, run, a=sc, steward=sc[1])
        rep = self.gk.calibration_report()
        self.assertEqual(rep["agreement"]["pairs"], 3)
        self.assertEqual(rep["agreement"]["agreement"], 1.0)
        prev = self.gk.what_if_weights({"analyst": 0.1, "steward": 0.1, "registrar": 0.8, "redteam_band": 0.1})
        self.assertEqual(len(prev["exemplars"]), 3)
        with self.assertRaisesRegex(Rejected, "supported_by"):
            self.gk.propose_calibration("taste", {"likes": [{"text": "Prefers reuse of hardware", "supported_by": []}]},
                                        "Pattern seen across several promote decisions this month.")
        p = self.gk.propose_calibration("weights", {"analyst": 0.4, "steward": 0.25, "registrar": 0.2, "redteam_band": 0.15},
                                        "Your promotes track analyst fit more than steward balance so far.")
        self.gk.decide_proposal(p["proposal_id"], True, "Agree, fit matters most to me")
        self.assertAlmostEqual(self.gk.weights()["analyst"], 0.4)

    def test_orchestrator_worklist_drives_a_full_run(self):
        """Walk a run the way the gatekeeper-run skill does, using only list_panel_work."""
        self.configure()
        g = self.gk
        run = g.start_run("scheduled")["run_id"]
        ideas = [self.candidate(run, n) for n in range(1, 4)]
        work = g.list_panel_work(run)
        self.assertEqual(sorted(work["analyst_gate"]), sorted(ideas))
        for iid in ideas:
            g.submit_analyst_review(iid, run, 0.7, "SD-02", 0.6, [], {}, "Advances the adjacent category directive clearly.", "medium")
        work = g.list_panel_work(run)
        self.assertEqual(work["analyst_gate"], [])
        self.assertEqual({x["idea_id"] for x in work["full_panel"]}, set(ideas))
        self.assertEqual(set(work["full_panel"][0]["roles"]), {"registrar", "steward", "redteam"})
        for iid in ideas:
            cid = g.add_evidence(iid, [dict(SRC, field="business_case", statement="A source says demand exists")])["claim_ids"][0]
            g.submit_registrar_review(iid, run, {d: {"score": 2, "claim_ids": [cid], "gap": "Not validated"} for d in core.READINESS_DIMS},
                                      "Evidence for each dimension, nothing validated.", "medium")
            g.submit_steward_review(iid, run, 0.6, 0.1, [], "Neutral to slightly positive on the mix.", "medium")
            g.raise_objection(iid, run, "Budget cycles at agencies may delay any purchase well past the pilot.", 0.2,
                              "A procurement officer confirming off-cycle purchasing")
        work = g.list_panel_work(run)
        self.assertEqual(work["full_panel"], [])
        self.assertEqual(work["round2"], [])
        board = g.compute_board(run)
        self.assertEqual(len(board["board"]), 3)
        b = board["board"][0]["idea_id"]
        # You ask for evidence; the next run's worklist carries it; finishing the job returns the idea to the board.
        g.decide(b, "need_evidence", "Need proof that agencies can buy off-cycle")
        g.finish_run(run)
        run2 = g.start_run("scheduled")["run_id"]
        jobs = g.list_panel_work(run2)["evidence_requests"]
        self.assertEqual(jobs[0]["idea_id"], b)
        g.update_job(jobs[0]["id"], "done", "Found a cooperative purchasing contract that allows it")
        self.assertEqual(g._idea(b)["stage"], "board")
        # Strategy change queues re-scores that show up in the worklist and clear when re-filed.
        st = json.loads(json.dumps(STRATEGY))
        st["exclusions"].append("No consumer products")
        g.set_config("strategy", st, "Added an exclusion")
        rescore = g.list_panel_work(run2)["rescore"]
        self.assertTrue(rescore)
        for job in rescore:
            if job["role"] == "analyst":
                g.submit_analyst_review(job["idea_id"], run2, 0.6, "SD-02", 0.6, [], {}, "Re-scored after the exclusion change.", "medium")
            else:
                g.submit_steward_review(job["idea_id"], run2, 0.6, 0.1, [], "Re-scored after the exclusion change.", "medium")
        self.assertEqual(g.list_panel_work(run2)["rescore"], [])

    def test_protected_channel(self):
        self.configure()
        r = self.gk.submit_my_idea("Reframe the company as a road safety data business", "Paradigm shift idea.",
                                   "transformational", "paradigm")
        board = self.gk.compute_board(None)
        row = [x for x in board["board"] if x["idea_id"] == r["id"]][0]
        self.assertEqual(row["action"], "PROTECTED")
        self.assertIsNone(row["score"])

    def test_append_only(self):
        self.configure()
        with self.assertRaises(sqlite3.IntegrityError):
            with self.gk.tx() as c:
                c.execute("DELETE FROM config_versions")
        with self.assertRaises(sqlite3.IntegrityError):
            with self.gk.tx() as c:
                c.execute("UPDATE events SET actor='someone else'")


class RegretFundedTest(Base):
    def test_regret_funded_counts_and_ranks_low(self):
        self.configure()
        f = self.gk.add_exemplar("Fixed-site sensor network", "funded", "Became the core of the business", "core", "product")["id"]
        a = self.gk.add_exemplar("ALPR products for agencies", "regret_funded",
                                 "No sales team to support it and no engineering capacity to keep up", "adjacent", "product")["id"]
        self.gk.add_exemplar("Vehicle based work zone enforcement", "funded", "Opened work zones", "core", "product")
        st = self.gk.get_setup_status()
        self.assertEqual(st["next_step"], "7_calibrate")
        self.assertIn("regret funded 1", [s for s in st["steps"] if s["step"] == "7_calibrate"][0]["what"])
        agree = D.pairwise_agreement([{"idea_id": f, "outcome": "funded", "score": 0.8},
                                      {"idea_id": a, "outcome": "regret_funded", "score": 0.4}])
        self.assertEqual(agree["agreement"], 1.0)

    def test_old_database_is_migrated(self):
        home = Path(self.tmp.name) / "old"
        (home / "data").mkdir(parents=True)
        db = home / "data" / "gatekeeper.db"
        old_schema = (Path(core.__file__).parent / "schema.sql").read_text().replace(",'regret_funded'", "")
        con = sqlite3.connect(db)
        con.executescript(old_schema)
        con.execute("INSERT INTO ideas(id, origin, thesis, stage, created_at, last_activity_at) "
                    "VALUES ('IDEA-2026-0001','human','Kept across migration','protected','x','x')")
        con.commit()
        con.close()
        g = Gatekeeper(db, home)
        try:
            self.assertEqual(g._idea("IDEA-2026-0001")["thesis"], "Kept across migration")
            g.add_exemplar("ALPR products for agencies", "regret_funded", "Should have said no to this one", "adjacent", "product")
        finally:
            g.close()


class ReviewRegressionTest(Base):
    """Defects found in the independent review, pinned so they stay fixed."""

    def test_fidelity_ignores_ids_scores_and_citations(self):
        ok = ("IDEA-2026-0031 overlaps PF-0003 and PRB-2026-0007; score 0.5833 and 0.599; SD-02, CAP-01, SD-101; "
              "Week 8; 3 agencies; FY2027; HB 2101 and 23 CFR 655 and Section 112 apply.")
        self.assertEqual(core.unbacked_numbers(ok, []), [])
        self.assertEqual(core.unbacked_numbers("Costs $500 per unit and grows 40%.", []), ["$500", "40%"])
        excerpt_claim = [dict(SRC, field="cost", statement="Unit cost from the vendor page",
                              excerpt="List price is $500 per unit with 40% volume growth.")]
        self.assertEqual(core.unbacked_numbers("Costs $500 per unit and grows 40%.", excerpt_claim), [])

    def _on_board(self):
        self.configure()
        run = self.gk.start_run("manual")["run_id"]
        iid = self.candidate(run, 1)
        self.full_panel(iid, run, objection=0.2)
        board = self.gk.compute_board(run)
        return run, iid, board

    def test_steward_and_arbiter_can_quote_system_numbers(self):
        self.configure()
        run = self.gk.start_run("manual")["run_id"]
        iid = self.candidate(run, 1)
        self.gk.submit_analyst_review(iid, run, 0.7, "SD-02", 0.6, [], {}, "Advances SD-02 with existing hardware.", "medium")
        port = self.gk.get_portfolio(iid)
        core_pct = round(port["shares"]["core"] * 100)
        self.gk.submit_steward_review(iid, run, 0.7, 0.2, ["PF-0003"],
                                      f"Core is at {core_pct}% against a 60% target, so an adjacent idea helps; overlaps PF-0003.",
                                      "medium")
        cid = self.gk.add_evidence(iid, [dict(SRC, field="business_case", statement="Demand exists")])["claim_ids"][0]
        self.gk.submit_registrar_review(iid, run, {d: {"score": 2, "claim_ids": [cid], "gap": "Not validated"} for d in core.READINESS_DIMS},
                                        "Evidence on each dimension, none validated.", "medium")
        self.gk.raise_objection(iid, run, "Agencies may not buy outside their budget cycle at any reasonable price.", 0.2,
                                "A cooperative purchasing contract")
        board = self.gk.compute_board(run)
        sc = board["board"][0]["score"]
        self.gk.annotate_rank(iid, run, f"Ranked at {sc} on analyst fit with SD-02; steward and analyst agree, overlap with PF-0003 is minor.")

    def test_profile_resave_keeps_confirmation(self):
        self.configure()
        self.gk.set_config("profile", {"company": "Fixture Co", "urls": ["https://example.org"], "summary": "Synthetic.",
                                       "pain_points": ["Install lead times"]}, "adding pain points in step 4")
        self.assertTrue(self.gk._config_raw("profile")["confirmed"])

    def test_partial_weights_update_keeps_the_rest(self):
        self.configure()
        self.gk.set_config("weights", {"steward": 0.1}, "lower steward")
        self.gk.set_config("weights", {"analyst": 0.45}, "raise analyst")
        self.assertAlmostEqual(self.gk.weights()["steward"], 0.1)

    def test_protected_never_queued_or_defaulted(self):
        self.configure()
        self.gk.submit_my_idea("Reframe as a road safety data business", "Paradigm idea.", "transformational", "paradigm")
        self.gk.compute_board(None)
        self.assertEqual(self.gk.get_queue(), [])

    def test_benched_steward_gets_no_rescore_jobs(self):
        run, iid, _ = self._on_board()
        self.gk.set_config("bench", {"benched": [{"role": "steward", "reason": "no portfolio to protect in this test"}]}, "bench steward for the test")
        st = json.loads(json.dumps(STRATEGY))
        st["exclusions"].append("No consumer products")
        self.gk.set_config("strategy", st, "exclusion added for the test")
        roles = {j["role"] for j in self.gk.list_jobs("pending")}
        self.assertEqual(roles, {"analyst"})

    def test_inbox_rows_are_separate_signals(self):
        self.configure()
        run = self.gk.start_run("manual")["run_id"]
        inbox = Path(self.tmp.name) / "inbox"
        inbox.mkdir()
        f = inbox / "tickets.csv"
        f.write_text("id,summary\n1,a\n2,b\n")
        self.gk.submit_signal(run, "process_needs", "Row one issue", f"file://{f}#row-1", "2026-10-08", "Row one says a thing worth noting.")
        self.gk.submit_signal(run, "process_needs", "Row two issue", f"file://{f}#row-2", "2026-10-08", "Row two says another thing entirely.")

    def test_redteam_retried_for_board_idea_without_objection(self):
        self.configure()
        run = self.gk.start_run("manual")["run_id"]
        iid = self.candidate(run, 1)
        self.full_panel(iid, run)              # no objection filed
        self.gk.compute_board(run)
        work = self.gk.list_panel_work(run)
        self.assertIn({"idea_id": iid, "roles": ["redteam"]}, work["full_panel"])

    def test_evidence_request_roles(self):
        run, iid, _ = self._on_board()
        with self.assertRaises(Rejected):
            self.gk.request_evidence(iid, "Is there a competitor already shipping this?", role="steward")
        self.gk.request_evidence(iid, "Is there a competitor already shipping this?", role="analyst")


class DeliberationUnitTest(unittest.TestCase):
    def test_pick_queue_reserves_exploratory_slot(self):
        rows = [{"idea_id": f"I{i}", "action": "PROMOTE", "score": 0.9 - i * 0.01, "ambition_cell": "core"} for i in range(5)]
        rows.append({"idea_id": "X", "action": "CONSIDER", "score": 0.5, "ambition_cell": "transformational"})
        q = D.pick_queue(rows, 3)
        self.assertIn("X", [r["idea_id"] for r in q])
        self.assertEqual(len(q), 3)

    def test_mix_delta(self):
        self.assertGreater(D.mix_delta({"core": 9, "adjacent": 1, "transformational": 0},
                                       {"core": 0.6, "adjacent": 0.3, "transformational": 0.1}, "transformational"), 0)

    def test_benched_role_renormalizes(self):
        o = D.resolve([D.Review("analyst", 1, 0.8), D.Review("registrar", 1, 0.4)], [], D.DEFAULT_WEIGHTS, D.DEFAULT_RULES)
        self.assertAlmostEqual(sum(c["weight"] for c in o.components), 1.0, places=3)
        self.assertIn("missing review: steward", o.flags)

    def test_registrar_gates_but_does_not_vote(self):
        revs = [D.Review("analyst", 2, 0.6), D.Review("steward", 2, 0.5), D.Review("registrar", 2, 0.2)]
        o = D.resolve(revs, [], D.DEFAULT_WEIGHTS, D.DEFAULT_RULES)
        w = D.normalize_weights(D.DEFAULT_WEIGHTS)
        self.assertAlmostEqual(o.score, round(w["analyst"] * 0.6 + w["steward"] * 0.5, 4), places=4)
        self.assertAlmostEqual(o.dispersion, 0.1, places=4)      # registrar's low scale no longer reads as a split
        self.assertNotEqual(o.action, "CONTESTED")
        self.assertEqual(o.readiness, 0.2)
        reg = [c for c in o.components if c["role"] == "registrar"][0]
        self.assertEqual((reg["weight"], reg["voting"]), (0.0, False))
        hi = D.resolve([D.Review("analyst", 1, 0.9), D.Review("steward", 1, 0.8), D.Review("registrar", 1, 0.2)],
                       [], D.DEFAULT_WEIGHTS, D.DEFAULT_RULES)
        self.assertEqual(hi.action, "NEED_EVIDENCE")              # strong score, first check not ready to run


if __name__ == "__main__":
    unittest.main()
