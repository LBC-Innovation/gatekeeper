"""The web API: auth, the decision flow with its guards, and that web and Claude write through the same rules."""

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from gatekeeper.api import create_app
from gatekeeper.auth import Auth
from test_pipeline import Base

REASON = "The falsifier is cheap to check and the law status is unclear"


class ApiBase(Base):
    def setUp(self):
        super().setUp()
        self.configure()
        g = self.gk
        run = g.start_run("scheduled")["run_id"]
        self.ids = [self.candidate(run, n) for n in range(1, 4)]
        for iid in self.ids:
            self.full_panel(iid, run, a=(0.7, 0.6), steward=0.6, objection=0.2)
        g.compute_board(run)
        g.finish_run(run)
        self.auth = Auth(Path(self.tmp.name))
        self.app = create_app(g, self.auth, port=8787, extra_hosts=("testserver",))
        self.client = TestClient(self.app, base_url="http://testserver")
        self.client.__enter__()
        self.bearer = {"Authorization": f"Bearer {self.auth.api_token}"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        super().tearDown()

    def signed_in(self):
        self.client.get(f"/auth/launch?t={self.auth.new_launch_token()}", follow_redirects=False)


class AuthTest(ApiBase):
    def test_every_data_route_needs_a_session_or_the_token(self):
        for p in ("/api/inbox", "/api/board", f"/api/ideas/{self.ids[0]}", "/api/config", "/api/stream"):
            self.assertEqual(self.client.get(p).status_code, 401, p)
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        self.assertEqual(self.client.get("/api/inbox", headers=self.bearer).status_code, 200)

    def test_a_wrong_host_is_refused(self):
        r = self.client.get("/api/inbox", headers={**self.bearer, "Host": "evil.example"})
        self.assertEqual(r.status_code, 421)

    def test_a_launch_link_survives_being_opened_twice_but_not_for_long(self):
        from unittest import mock
        t = self.auth.new_launch_token()
        self.assertEqual(self.client.get(f"/auth/launch?t={t}", follow_redirects=False).status_code, 303)
        self.assertEqual(self.client.get(f"/auth/launch?t={t}", follow_redirects=False).status_code, 303)   # a terminal preview, then the browser
        later = __import__("time").time() + 10 * 60
        with mock.patch("gatekeeper.auth.time.time", return_value=later):                                  # used, and the grace window is over
            r = self.client.get(f"/auth/launch?t={t}", follow_redirects=False)
        self.assertEqual(r.status_code, 401)
        self.assertIn("service/dev.sh open", r.text)                                                       # the failure page says what to do

    def test_an_unknown_or_expired_link_is_refused(self):
        from unittest import mock
        self.assertEqual(self.client.get("/auth/launch?t=nope", follow_redirects=False).status_code, 401)
        t = self.auth.new_launch_token()
        with mock.patch("gatekeeper.auth.time.time", return_value=__import__("time").time() + 16 * 60):
            self.assertEqual(self.client.get(f"/auth/launch?t={t}", follow_redirects=False).status_code, 401)

    def test_a_link_minted_by_another_process_works(self):
        other = Auth(Path(self.tmp.name))            # a second Auth over the same folder, as `serve.py open` is
        t = other.new_launch_token()
        self.assertEqual(self.client.get(f"/auth/launch?t={t}", follow_redirects=False).status_code, 303)

    def test_a_cookie_write_from_another_origin_is_refused(self):
        self.signed_in()
        r = self.client.post(f"/api/ideas/{self.ids[0]}/decisions", json={"action": "park", "reason": REASON},
                             headers={"Origin": "http://evil.example"})
        self.assertEqual(r.status_code, 403)
        self.assertIsNone(self.gk.q1("SELECT 1 x FROM decisions WHERE idea_id=?", (self.ids[0],)))


class DecisionFlowTest(ApiBase):
    def test_a_web_decision_is_recorded_with_its_channel_and_closes_the_queue_item(self):
        self.signed_in()
        iid = self.ids[0]
        snap = self.client.get(f"/api/ideas/{iid}").json()["snapshot_id"]
        r = self.client.post(f"/api/ideas/{iid}/decisions", json={"action": "need_evidence", "reason": REASON, "seen_snapshot_id": snap})
        self.assertEqual(r.status_code, 201, r.text)
        d = self.gk.q1("SELECT * FROM decisions WHERE idea_id=?", (iid,))
        self.assertEqual((d["action"], d["actor"], d["via"]), ("need_evidence", "human", "web"))
        self.assertNotIn(iid, [q["idea_id"] for q in self.gk.get_queue()])

    def test_a_portfolio_item_can_be_retagged_in_place_from_the_web(self):
        self.signed_in()
        item = next(x for x in self.gk.list_portfolio() if x["name"] == "Speed cameras")
        before = self.client.get("/api/portfolio").json()["counts"]
        r = self.client.patch(f"/api/portfolio/{item['id']}", json={"ambition_cell": "adjacent", "reason": "Not yet live, so it is adjacent"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["changes"]["ambition_cell"], {"from": "core", "to": "adjacent"})
        after = self.client.get("/api/portfolio").json()["counts"]
        self.assertEqual((after["core"], after["adjacent"]), (before["core"] - 1, before["adjacent"] + 1))
        self.assertEqual(next(x for x in self.gk.list_portfolio() if x["id"] == item["id"])["ambition_cell"], "adjacent")
        ev = self.gk.q1("SELECT actor FROM events WHERE event='portfolio_item_updated'")
        self.assertEqual(ev["actor"], "human")

    def test_a_retag_needs_a_real_change_a_reason_and_a_live_item(self):
        self.signed_in()
        item = self.gk.list_portfolio()[0]
        url = f"/api/portfolio/{item['id']}"
        same = self.client.patch(url, json={"ambition_cell": item["ambition_cell"], "reason": "Nothing actually changes here"})
        self.assertEqual(same.status_code, 422)
        self.assertEqual(self.client.patch(url, json={"reason": "No field given to change at all"}).status_code, 422)
        self.assertEqual(self.client.patch(url, json={"ambition_cell": "core"}).status_code, 422)
        self.assertEqual(self.client.patch("/api/portfolio/PF-9999", json={"ambition_cell": "core", "reason": "There is no such item here"}).status_code, 422)

    def test_an_item_can_be_added_and_retired_from_the_web(self):
        self.signed_in()
        before = self.client.get("/api/portfolio").json()["counts"]["transformational"]
        r = self.client.post("/api/portfolio", json={"kind": "in_flight", "name": "Pay-for-success pilot", "ambition_cell": "transformational"})
        self.assertEqual(r.status_code, 201, r.text)
        pid = r.json()["id"]
        self.assertEqual(self.client.get("/api/portfolio").json()["counts"]["transformational"], before + 1)
        self.assertEqual(self.client.post("/api/portfolio", json={"kind": "line", "name": "x", "ambition_cell": "core"}).status_code, 422)
        self.assertEqual(self.client.post(f"/api/portfolio/{pid}/retirement", json={"reason": "no"}).status_code, 422)
        r = self.client.post(f"/api/portfolio/{pid}/retirement", json={"reason": "It was entered by mistake"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.client.get("/api/portfolio").json()["counts"]["transformational"], before)
        self.assertEqual(self.client.post(f"/api/portfolio/{pid}/retirement", json={"reason": "Retiring it a second time"}).status_code, 422)

    def test_a_future_goal_is_listed_apart_and_stays_out_of_the_mix(self):
        self.signed_in()
        before = self.client.get("/api/portfolio").json()
        r = self.client.post("/api/portfolio", json={"kind": "future_goal", "name": "Distracted driving detection", "ambition_cell": "transformational"})
        self.assertEqual(r.status_code, 201, r.text)
        after = self.client.get("/api/portfolio").json()
        self.assertEqual(after["counts"], before["counts"])
        self.assertEqual(after["shares"], before["shares"])
        self.assertEqual([g["name"] for g in after["goals"]], ["Distracted driving detection"])
        self.assertNotIn("Distracted driving detection", [x["name"] for c in after["items"].values() for x in c])
        ctx = self.gk.get_context("steward")
        self.assertIn("Areas of interest", str(ctx))

    def test_an_old_ledger_learns_the_future_goal_kind(self):
        import sqlite3
        db = Path(self.tmp.name) / "old.db"
        con = sqlite3.connect(db)
        con.execute("CREATE TABLE portfolio_items (id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK (kind IN ('line','in_flight')), "
                    "name TEXT NOT NULL, description TEXT, ambition_cell TEXT NOT NULL CHECK (ambition_cell IN ('core','adjacent','transformational')), "
                    "four_p TEXT CHECK (four_p IN ('product','process','position','paradigm')), source TEXT NOT NULL, "
                    "active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL)")
        con.execute("INSERT INTO portfolio_items VALUES ('PF-0001','line','Speed cameras',NULL,'core',NULL,'old',1,'2026-01-01')")
        con.commit(); con.close()
        from gatekeeper.core import Gatekeeper
        g = Gatekeeper(db)
        try:
            self.assertEqual(g.add_portfolio_item("future_goal", "Seat belt enforcement", "adjacent", "test")["id"], "PF-0002")
            self.assertEqual(len(g.list_portfolio()), 2)
        finally:
            g.close()

    def test_an_agent_cannot_retag_the_book(self):
        from gatekeeper.registry import build_registry
        self.assertFalse(build_registry(self.gk)["update_portfolio_item"].on("pipeline"))

    def test_the_same_rules_apply_as_in_chat(self):
        self.signed_in()
        r = self.client.post(f"/api/ideas/{self.ids[0]}/decisions", json={"action": "park", "reason": "no"})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.headers["content-type"], "application/problem+json")
        self.assertIn("reason", r.json()["detail"])
        self.assertIsNone(self.gk.q1("SELECT 1 x FROM decisions"))

    def test_a_stale_view_gets_a_409_instead_of_a_decision(self):
        self.signed_in()
        iid = self.ids[0]
        run2 = self.gk.start_run("scheduled")["run_id"]
        seen = self.client.get(f"/api/ideas/{iid}").json()["snapshot_id"]
        self.gk.raise_objection(iid, run2, "A late finding means the agency cannot buy this outside a contract cycle at all.", 0.8,
                                "A procurement officer confirming off-cycle purchasing")
        self.gk.compute_board(run2)
        r = self.client.post(f"/api/ideas/{iid}/decisions", json={"action": "promote", "reason": REASON, "seen_snapshot_id": seen})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["current"]["action"], "REVIEW_OBJECTION")
        self.assertIsNone(self.gk.q1("SELECT 1 x FROM decisions WHERE idea_id=?", (iid,)))

    def test_a_repeated_idempotency_key_records_one_decision(self):
        self.signed_in()
        iid = self.ids[0]
        h = {"Idempotency-Key": "abc-123"}
        a = self.client.post(f"/api/ideas/{iid}/decisions", json={"action": "park", "reason": REASON}, headers=h)
        b = self.client.post(f"/api/ideas/{iid}/decisions", json={"action": "park", "reason": REASON}, headers=h)
        self.assertEqual((a.status_code, b.status_code), (201, 201))
        self.assertEqual(len(self.gk.q("SELECT 1 FROM decisions WHERE idea_id=?", (iid,))), 1)

    def test_an_objection_can_be_answered_and_evidence_requested(self):
        self.signed_in()
        iid = self.ids[1]
        oid = self.client.get(f"/api/ideas/{iid}").json()["objections"][0]["id"]
        self.assertEqual(self.client.post(f"/api/objections/{oid}/answers", json={"answer": "Agencies can buy off-cycle through a cooperative contract.", "status": "answered"}).status_code, 201)
        self.assertEqual(self.client.post(f"/api/ideas/{iid}/evidence-requests", json={"question": "Which cooperative contracts allow this purchase?"}).status_code, 201)


class ReadModelTest(ApiBase):
    def test_inbox_lists_the_queue_with_one_score_and_a_default_date(self):
        self.signed_in()
        j = self.client.get("/api/inbox").json()
        self.assertEqual(len(j["items"]), 3)
        it = j["items"][0]
        self.assertIsInstance(it["idea"]["score"], int)
        self.assertTrue(it["queue"]["default_on"])
        self.assertIn(it["kind"], ("decision", "objection"))

    def test_a_title_is_derived_when_none_was_authored(self):
        self.signed_in()
        t = self.client.get(f"/api/ideas/{self.ids[0]}").json()["summary"]["title"]
        self.assertTrue(t and not t.endswith("."))

    def test_the_idea_record_carries_what_the_screens_need(self):
        self.signed_in()
        j = self.client.get(f"/api/ideas/{self.ids[0]}").json()
        for k in ("summary", "reviews", "readiness", "analyst", "steward", "objections", "evidence", "timeline", "first_check", "snapshot_id"):
            self.assertIn(k, j)
        self.assertEqual(j["readiness"]["max"], 18)
        self.assertIn("constraints", j["analyst"])


if __name__ == "__main__":
    unittest.main()


class BoardOrderTest(ApiBase):
    def test_the_board_follows_the_arbiters_rank(self):
        self.signed_in()
        rows = self.client.get("/api/board").json()["rows"]
        self.assertEqual([r["rank"] for r in rows], sorted(r["rank"] for r in rows))


class IdCodeCardTest(ApiBase):
    def test_a_code_in_prose_opens_a_card_for_what_it_names(self):
        self.signed_in()
        card = self.client.get(f"/api/refs/{self.ids[0]}").json()
        self.assertEqual((card["kind"], card["code"], card["href"]), ("IDEA", self.ids[0], f"/ideas/{self.ids[0]}"))
        sd = self.client.get("/api/refs/SD-03").json()
        self.assertEqual(sd["label"], "Strategic directive")
        self.assertTrue(sd["title"])

    def test_unknown_and_malformed_codes_are_refused(self):
        self.signed_in()
        self.assertEqual(self.client.get("/api/refs/SD-99").status_code, 404)
        self.assertEqual(self.client.get("/api/refs/not-a-code").status_code, 404)
        self.assertEqual(self.client.get("/api/refs/SD-03;drop").status_code, 404)

    def test_codes_need_a_session_like_everything_else(self):
        self.assertEqual(self.client.get("/api/refs/SD-03").status_code, 401)


class TeamTest(ApiBase):
    def test_the_team_is_listed_in_pipeline_order_with_a_bio_each(self):
        self.signed_in()
        a = self.client.get("/api/agents").json()["agents"]
        self.assertEqual([x["id"] for x in a], ["scout", "curator", "framer", "inventor", "analyst", "registrar", "steward", "redteam", "arbiter", "herald", "calibrator"])
        self.assertTrue(all(x["bio"] and x["avatar"].endswith(".png") for x in a))

    def test_an_agent_returns_its_own_file(self):
        self.signed_in()
        j = self.client.get("/api/agents/redteam").json()
        self.assertIn("Red Team", j["markdown"])
        self.assertEqual(j["file"], "claude-config/agents/gatekeeper-redteam.md")
        self.assertIn("raise_objection", j["tools"]["ledger"])
        self.assertNotIn("submit_analyst_review", j["tools"]["ledger"])   # Red Team never holds a panel score tool

    def test_only_known_agents_can_be_read(self):
        self.signed_in()
        for bad in ("../../.mcp.json", "nope", "scout.md"):
            self.assertEqual(self.client.get(f"/api/agents/{bad}").status_code, 404, bad)
