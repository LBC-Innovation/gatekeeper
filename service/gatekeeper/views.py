"""Read models for the web app. Pure reads over the ledger: no rules live here, only shaping.

Every function returns plain dicts that become JSON. Scores are shown to people on a 0 to 100 scale; the ledger keeps 0 to 1.
Titles and one-sentence headlines are authored by agents where they exist and derived from the full text where they do not.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone

from . import deliberation as D
from .core import Gatekeeper, READINESS_DIMS, today

DIM_LABELS = {"business_case": "Business case", "product_desc": "Check defined", "design_docs": "Method",
              "resource_plan": "Cost and time", "investment_support": "Owner", "prototype": "Inputs exist"}
READY_WORD = ["missing", "stated, not shown", "shown", "confirmed"]


def pct(x):
    return None if x is None else round(x * 100)


# ----------------------------------------------------------------------------- text helpers

_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z“\"])")
_META = re.compile(r"^(Revised|Holding|Held|I |I'm |My |Fit (lowered|is)|Classified|Steelman|Best version|At its best|Round 2|IDEA-|"
                   r"The (Red Team )?objection|This (review|revision)|Panelist)|\b(my view|my score|round 1|round 2|I held|I revised)\b", re.I)


def _maths(s: str) -> bool:
    return len(re.findall(r"\d\.\d{2,}", s)) >= 2


def headline_of(text: str | None, limit: int = 240) -> str:
    """The first sentence that argues something: reviewer preambles, steelman openers and arithmetic are skipped."""
    parts = _SPLIT.split((text or "").strip())
    while len(parts) > 1 and (_META.search(parts[0]) or _maths(parts[0])):
        parts = parts[1:]
    h = parts[0] if parts else ""
    if len(h) > limit:
        h = h[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return h


def derive_title(thesis: str) -> str:
    """A fallback name for ideas filed before titles existed. New ideas carry an authored title."""
    t = (thesis or "").strip().rstrip(".")
    for sep in (": ", " — ", "; ", ", "):
        head = t.split(sep, 1)[0]
        if len(head) >= 24:
            t = head
            break
    if len(t) > 64:
        t = t[:64].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return t[:1].upper() + t[1:]


def _objection_body(text: str) -> str:
    return re.sub(r"^(Steelman|Best version( of the idea)?):?[^.]*\.\s*", "", text or "", flags=re.I)


# ----------------------------------------------------------------------------- one consistent read of the ledger

class Ledger:
    """Loads what list screens need in a handful of queries, then answers per-idea questions from memory."""

    def __init__(self, gk: Gatekeeper):
        self.gk = gk
        self.rules = gk.rules()
        self.ideas = {r["id"]: r for r in gk.q("SELECT * FROM ideas")}
        self.snap = {r["idea_id"]: r for r in gk.q(
            "SELECT * FROM board_snapshots WHERE id IN (SELECT MAX(id) FROM board_snapshots GROUP BY idea_id)")}
        self.reviews: dict[str, list[dict]] = defaultdict(list)
        for r in gk.q("SELECT * FROM reviews ORDER BY id"):
            r["sub"] = json.loads(r["sub"])
            self.reviews[r["idea_id"]].append(r)
        self.objections: dict[str, list[dict]] = defaultdict(list)
        for o in gk.q("SELECT * FROM objections ORDER BY id"):
            self.objections[o["idea_id"]].append(o)
        self.queue = {q["idea_id"]: q for q in gk.q("SELECT * FROM queue_items WHERE status='open' AND kind='decision'")}
        self.decision: dict[str, dict] = {}
        for d in gk.q("SELECT * FROM decisions ORDER BY id"):
            self.decision[d["idea_id"]] = d
        mine = gk.q1("SELECT ranking FROM my_rank ORDER BY id DESC LIMIT 1")
        self.my_pos = {iid: n + 1 for n, iid in enumerate(json.loads(mine["ranking"]))} if mine else {}

    # -- small lookups
    def latest(self, iid: str, role: str, round_: int | None = None) -> dict | None:
        rs = [r for r in self.reviews.get(iid, []) if r["role"] == role and (round_ is None or r["round"] == round_)]
        return max(rs, key=lambda r: (r["round"], r["id"])) if rs else None

    def open_objection(self, iid: str) -> dict | None:
        open_ = [o for o in self.objections.get(iid, []) if o["status"] == "open"]
        return max(open_, key=lambda o: o["id"]) if open_ else None

    def title(self, iid: str) -> str:
        i = self.ideas[iid]
        return i.get("title") or derive_title(i["thesis"])

    # -- the summary every list shows
    def summary(self, iid: str) -> dict:
        i = self.ideas[iid]
        snap = self.snap.get(iid)
        a, s, g = self.latest(iid, "analyst"), self.latest(iid, "steward"), self.latest(iid, "registrar")
        ob = self.open_objection(iid)
        q = self.queue.get(iid)
        dec = self.decision.get(iid)
        rounds = max([r["round"] for r in self.reviews.get(iid, [])], default=0)
        action = snap["action"] if snap else ({"parked": "PARK", "parked_auto": "PARK"}.get(i["stage"]))
        return {
            "id": iid, "title": self.title(iid), "thesis": i["thesis"], "cell": i["ambition_cell"], "four_p": i["four_p"],
            "stage": i["stage"], "origin": i["origin"], "action": action,
            "score": pct(snap["score"]) if snap else None, "band": pct(snap["band"]) if snap else None,
            "rank": snap["rank"] if snap else None, "my_rank": self.my_pos.get(iid),
            "spread": pct(snap["dispersion"]) if snap and snap["dispersion"] is not None else None,
            "readiness": g["sub"].get("total") if g else None, "readiness_max": 18,
            "strategy": pct(a["score"]) if a else None, "portfolio": pct(s["score"]) if s else None,
            "severity": pct(ob["severity"]) if ob else None,
            "objection_headline": (ob["headline"] or headline_of(_objection_body(ob["text"]))) if ob else None,
            "rounds": rounds, "directive_id": a["sub"].get("directive_id") if a else None,
            "snapshot_id": snap["id"] if snap else None, "snapshot_at": snap["created_at"] if snap else None,
            "queue": self.queue_view(q),
            "decision": ({"action": dec["action"], "reason": dec["reason"], "actor": dec["actor"], "via": dec.get("via"),
                          "at": dec["created_at"]} if dec and i["stage"] in ("promoted", "killed", "parked", "need_evidence") else None),
            "last_activity_at": i["last_activity_at"],
        }

    def queue_view(self, q: dict | None) -> dict | None:
        if not q:
            return None
        days = (datetime.fromisoformat(q["default_on"]).date() - today()).days
        return {"id": q["id"], "recommended_action": q["recommended_action"], "default_action": q["default_action"],
                "default_on": q["default_on"], "days_left": days, "why": q["why"], "snapshot_id": q["snapshot_id"]}


# ----------------------------------------------------------------------------- screens

def inbox(gk: Gatekeeper) -> dict:
    L = Ledger(gk)
    items = []
    for iid, q in L.queue.items():
        if iid not in L.ideas:
            continue
        s = L.summary(iid)
        items.append({"kind": "objection" if q["recommended_action"] == "REVIEW_OBJECTION" else "decision", "idea": s, "queue": s["queue"]})
    prio = D.QUEUE_PRIORITY
    items.sort(key=lambda x: (prio.get(x["queue"]["recommended_action"], 8), -(x["idea"]["score"] or 0), x["idea"]["id"]))
    runs = gk.q("SELECT * FROM runs ORDER BY id DESC LIMIT 1")
    last = runs[0] if runs else None
    port = gk.get_portfolio()
    brief = gk.get_brief()
    snaps = [r["created_at"] for r in L.snap.values()]
    return {
        "as_of": max(snaps) if snaps else None, "items": items,
        "last_run": _run_row(gk, last) if last else None, "live_run": live_run(gk),
        "portfolio": {"shares": port["shares"], "target": port["target"], "alarms": port["alarms"], "in_band": port["in_band"]},
        "brief": {"date": brief["brief_date"], "body": brief["body"], "quiet": bool(brief["quiet"])} if brief else None,
        "queue_size": L.rules["queue_size"],
        "today": today().isoformat(),
    }


def board(gk: Gatekeeper) -> dict:
    L = Ledger(gk)
    rows = [L.summary(iid) for iid, i in L.ideas.items() if i["stage"] in ("board", "need_evidence", "protected") and iid in L.snap]
    rows.sort(key=lambda r: (r["rank"] is None, r["rank"] or 0, r["id"]))   # the arbiter's order, not a re-sort of rounded scores
    in_review = [L.summary(iid) for iid, i in L.ideas.items() if i["stage"] in ("candidate", "panel")]
    r = L.rules
    return {"rows": rows, "in_review": len(in_review), "promoted": [L.summary(i) for i, x in L.ideas.items() if x["stage"] == "promoted"],
            "lines": {"fund": pct(r["promote"]), "park": pct(r["park_below"]), "ready": r["need_evidence_readiness"]},
            "as_of": max([x["snapshot_at"] for x in rows if x["snapshot_at"]], default=None)}


def idea_record(gk: Gatekeeper, iid: str) -> dict | None:
    L = Ledger(gk)
    if iid not in L.ideas:
        return None
    i = L.ideas[iid]
    rec = gk.get_idea_record(iid)
    idea = rec["idea"]
    reviews = []
    for r in L.reviews.get(iid, []):
        reviews.append({"role": r["role"], "round": r["round"], "score": pct(r["score"]), "sub": r["sub"], "rationale": r["rationale"],
                        "headline": r["sub"].get("headline") or headline_of(r["rationale"]), "headline_authored": bool(r["sub"].get("headline")),
                        "confidence": r["confidence"], "revision_reason": r["revision_reason"], "created_at": r["created_at"]})
    g = L.latest(iid, "registrar")
    dims = []
    if g:
        for k in READINESS_DIMS:
            d = g["sub"]["readiness"].get(k, {})
            dims.append({"key": k, "label": DIM_LABELS[k], "score": d.get("score", 0), "word": READY_WORD[d.get("score", 0)],
                         "gap": d.get("gap"), "owner_hint": d.get("owner_hint"), "claim_ids": d.get("claim_ids", [])})
    a = L.latest(iid, "analyst")
    s = L.latest(iid, "steward")
    first_a = L.latest(iid, "analyst", 1)
    objections = [{"id": o["id"], "headline": o["headline"] or headline_of(_objection_body(o["text"])), "headline_authored": bool(o["headline"]),
                   "text": _objection_body(o["text"]), "severity": pct(o["severity"]), "falsifier": o["falsifier"], "status": o["status"],
                   "answer": o["answer"], "created_at": o["created_at"], "run_id": o["run_id"]} for o in reversed(L.objections.get(iid, []))]
    port_names = {p["id"]: p["name"] for p in gk.list_portfolio()}
    overlaps = [{"id": x, "name": port_names.get(x, x)} for x in (s["sub"].get("overlaps", []) if s else [])]
    prb = gk.q1("SELECT * FROM problems WHERE id=?", (i["problem_id"],)) if i["problem_id"] else None
    sig = gk.q1("SELECT id, sensor, title, url, retrieved_at, excerpt, status FROM signals WHERE id=?", (i["signal_id"],)) if i["signal_id"] else None
    siblings = [L.summary(x["id"]) for x in gk.q("SELECT id FROM ideas WHERE problem_id=? ORDER BY id", (i["problem_id"],))] if i["problem_id"] else []
    snap = L.snap.get(iid)
    ev = [{**c, "created_at": c["created_at"] if "created_at" in c else None} for c in idea["claims"]]
    return {
        "summary": L.summary(iid), "description": i["description"], "technique": i["technique"], "sponsor": i["sponsor"],
        "first_check": idea.get("first_check"), "problem": prb, "signal": sig, "siblings": siblings,
        "reviews": reviews,
        "readiness": {"total": g["sub"].get("total") if g else None, "max": 18, "dims": dims,
                      "enough": (g["score"] >= L.rules["need_evidence_readiness"]) if g else None},
        "analyst": ({"fit": pct(a["sub"].get("strategic_fit")), "capability": pct(a["sub"].get("capability_match")), "directive_id": a["sub"].get("directive_id"),
                     "gaps": a["sub"].get("gaps", []), "constraints": a["sub"].get("constraints", []), "dependency": a["sub"].get("dependency", {}),
                     "round1_fit": pct(first_a["sub"].get("strategic_fit")) if first_a else None} if a else None),
        "steward": ({"mix_effect": s["sub"].get("mix_effect"), "cannibalization": pct(s["sub"].get("cannibalization_risk")), "overlaps": overlaps} if s else None),
        "objections": objections, "evidence": ev,
        "timeline": [{"id": e["id"], "at": e["at"], "actor": e["actor"], "event": e["event"], "detail": json.loads(e["detail"]) if e["detail"] else None}
                     for e in gk.q("SELECT * FROM events WHERE idea_id=? ORDER BY id", (iid,))],
        "decisions": rec["decisions"], "arithmetic": rec["deliberation"]["arithmetic"], "rank_notes": rec["deliberation"]["notes"],
        "weights": gk.weights(), "snapshot_id": snap["id"] if snap else None,
        "board_neighbours": _neighbours(L, iid),
    }


def _neighbours(L: Ledger, iid: str) -> dict:
    ranked = sorted((i for i in L.ideas if i in L.snap and L.ideas[i]["stage"] in ("board", "need_evidence", "protected")),
                    key=lambda x: (L.snap[x]["rank"] is None, L.snap[x]["rank"] or 0, x))
    if iid not in ranked:
        return {"prev": None, "next": None, "position": None, "of": len(ranked)}
    n = ranked.index(iid)
    return {"prev": ranked[n - 1] if n else None, "next": ranked[n + 1] if n + 1 < len(ranked) else None, "position": n + 1, "of": len(ranked)}


def portfolio(gk: Gatekeeper) -> dict:
    L = Ledger(gk)
    port = gk.get_portfolio()
    items = gk.list_portfolio()
    live = [x for x in items if x["kind"] != "future_goal"]
    goals = [x for x in items if x["kind"] == "future_goal"]
    by_cell = {c: [x for x in live if x["ambition_cell"] == c] for c in ("core", "adjacent", "transformational")}
    cands = {c: sorted([L.summary(i) for i, x in L.ideas.items() if x["ambition_cell"] == c and x["stage"] in ("board", "need_evidence", "protected") and i in L.snap],
                       key=lambda r: -(r["score"] or 0)) for c in ("core", "adjacent", "transformational")}
    overlaps: dict[str, list] = defaultdict(list)
    for iid in L.ideas:
        s = L.latest(iid, "steward")
        if s and iid in L.snap and L.ideas[iid]["stage"] in ("board", "need_evidence"):
            for p in s["sub"].get("overlaps", []):
                overlaps[p].append({"idea": L.summary(iid), "cannibalization": pct(s["sub"].get("cannibalization_risk"))})
    names = {p["id"]: p["name"] for p in items}
    parked_bold = [L.summary(i) for i, x in L.ideas.items() if x["ambition_cell"] == "transformational" and x["stage"] in ("parked", "parked_auto")]
    return {"counts": port["counts"], "shares": port["shares"], "target": port["target"], "alarms": port["alarms"], "in_band": port["in_band"],
            "floor": gk.strategy().get("exploratory_floor"), "items": by_cell, "goals": goals, "candidates": cands, "parked_bold": parked_bold,
            "overlaps": [{"item": {"id": p, "name": names.get(p, p)}, "ideas": v} for p, v in sorted(overlaps.items(), key=lambda kv: -len(kv[1]))],
            "stalled": port.get("stalled", [])}


def _run_row(gk: Gatekeeper, r: dict) -> dict:
    return {"id": r["id"], "trigger": r["trigger"], "status": r["status"], "started_at": r["started_at"], "finished_at": r["finished_at"],
            "note": r["note"], "counts": json.loads(r["counts"]) if r["counts"] else None}


def live_run(gk: Gatekeeper) -> dict | None:
    r = gk.q1("SELECT * FROM runs WHERE status='running' ORDER BY id DESC LIMIT 1")
    if not r:
        return None
    stages: dict[str, dict] = {}
    for s in gk.q("SELECT * FROM run_stages WHERE run_id=? ORDER BY id", (r["id"],)):
        stages[s["stage"]] = {"stage": s["stage"], "status": s["status"], "detail": s["detail"], "at": s["at"]}
    return {**_run_row(gk, r), "stages": list(stages.values()), "admitted": len(gk._admitted(r["id"]))}


def runs(gk: Gatekeeper) -> dict:
    return {"runs": [_run_row(gk, r) for r in gk.q("SELECT * FROM runs ORDER BY id DESC")], "live": live_run(gk), "stages": list(Gatekeeper.RUN_STAGES)}


def run_detail(gk: Gatekeeper, run_id: int) -> dict | None:
    r = gk.q1("SELECT * FROM runs WHERE id=?", (run_id,))
    if not r:
        return None
    activity = gk.q("SELECT actor, event, COUNT(*) n, MIN(at) start, MAX(at) end FROM events WHERE run_id=? GROUP BY actor, event ORDER BY MIN(id)", (run_id,))
    rej = gk.q("SELECT tool, COUNT(*) n FROM rejections WHERE run_id=? GROUP BY tool ORDER BY n DESC", (run_id,))
    samples = gk.q("SELECT tool, reason, created_at FROM rejections WHERE run_id=? ORDER BY id DESC LIMIT 8", (run_id,))
    unattributed = gk.q1("SELECT COUNT(*) n FROM rejections WHERE run_id IS NULL OR run_id=0")["n"]
    stages = [{"stage": s["stage"], "status": s["status"], "detail": s["detail"], "at": s["at"]}
              for s in gk.q("SELECT * FROM run_stages WHERE run_id=? ORDER BY id", (run_id,))]
    admissions = gk.q("SELECT idea_id, gate_score, admitted_at FROM panel_admissions WHERE run_id=? ORDER BY id", (run_id,))
    return {"run": _run_row(gk, r), "activity": activity, "stages": stages, "rejections": rej, "rejection_samples": samples,
            "rejections_outside_runs": unattributed, "admissions": admissions}


def signals(gk: Gatekeeper) -> dict:
    L = Ledger(gk)
    out = []
    prbs = {p["signal_id"]: p for p in gk.q("SELECT * FROM problems")}
    for s in gk.q("SELECT * FROM signals ORDER BY id DESC"):
        p = prbs.get(s["id"])
        ideas = [L.summary(x["id"]) for x in gk.q("SELECT id FROM ideas WHERE problem_id=? ORDER BY id", (p["id"],))] if p else []
        out.append({"id": s["id"], "run_id": s["run_id"], "sensor": s["sensor"], "title": s["title"], "url": s["url"], "retrieved_at": s["retrieved_at"],
                    "excerpt": s["excerpt"], "status": s["status"], "novelty": pct(s["novelty"]), "curator_note": s.get("curator_note") or s.get("note"),
                    "problem": ({"id": p["id"], "statement": p["statement"], "for_whom": p["for_whom"], "why_now": p["why_now"]} if p else None),
                    "ideas": ideas})
    return {"signals": out}


def log(gk: Gatekeeper) -> dict:
    L = Ledger(gk)
    decisions = []
    for d in gk.q("SELECT * FROM decisions ORDER BY id DESC"):
        iid = d["idea_id"]
        decisions.append({"id": d["id"], "idea_id": iid, "title": L.title(iid) if iid in L.ideas else iid, "thesis": L.ideas[iid]["thesis"] if iid in L.ideas else None,
                          "action": d["action"], "reason": d["reason"], "actor": d["actor"], "via": d.get("via"), "at": d["created_at"]})
    config = [{"id": c["id"], "section": c["section"], "reason": c["reason"], "actor": c["actor"], "at": c["created_at"]}
              for c in gk.q("SELECT id, section, reason, actor, created_at FROM config_versions ORDER BY id DESC")]
    return {"decisions": decisions, "config": config}


def config(gk: Gatekeeper) -> dict:
    c = gk.get_config()
    return {"weights": c["weights"], "rules": gk.rules(), "taste": c["taste"], "bench": c["bench"], "directives": (c["strategy"] or {}).get("directives", []),
            "capabilities": (c["capabilities"] or {}).get("capabilities", []), "exclusions": (c["strategy"] or {}).get("exclusions", []),
            "watchlist": (c["strategy"] or {}).get("watchlist", {}), "mix_target": (c["strategy"] or {}).get("mix_target"),
            "exploratory_floor": (c["strategy"] or {}).get("exploratory_floor"), "profile": c["profile"],
            "versions": {k: c.get(f"{k}_version") for k in ("profile", "strategy", "capabilities", "taste", "weights", "rules", "bench")}}


def proposals(gk: Gatekeeper) -> dict:
    return {"open": gk.list_proposals("open"), "accepted": gk.list_proposals("accepted"), "rejected": gk.list_proposals("rejected")}


def events_after(gk: Gatekeeper, after: int, limit: int = 200) -> list[dict]:
    rows = gk.q("SELECT id, idea_id, run_id, at, actor, event, detail FROM events WHERE id>? ORDER BY id LIMIT ?", (after, limit))
    for r in rows:
        r["detail"] = json.loads(r["detail"]) if r["detail"] else None
    return rows


def last_event_id(gk: Gatekeeper) -> int:
    return gk.q1("SELECT COALESCE(MAX(id),0) n FROM events")["n"]


# ----------------------------------------------------------------------------- id codes

REF_RE = re.compile(r"^(SD-\d{2}|CAP-\d{2}|PF-\d{4}|IDEA-\d{4}-\d{4}|SIG-\d{4}-\d{4}|PRB-\d{4}-\d{4})$")


def ref_card(gk: Gatekeeper, code: str) -> dict | None:
    """An at-a-glance card for any ID code that appears in prose. Read-only; each card says what the code is and what it touches."""
    if not REF_RE.match(code):
        return None
    kind = code.split("-")[0]
    facts: list[list[str]] = []
    related: list[dict] = []
    card = {"code": code, "kind": kind, "facts": facts, "related": related, "href": None}
    L = None

    def ledger():
        nonlocal L
        L = L or Ledger(gk)
        return L

    if kind == "SD":
        d = next((x for x in gk.strategy().get("directives", []) if x["id"] == code), None)
        if not d:
            return None
        card.update(label="Strategic directive", title=d["statement"])
        facts += [["Funded", "Yes" if d.get("funded") else "No"], ["Horizon", str(d.get("horizon", ""))]]
        if d.get("retired"):
            facts.append(["Status", "Retired"])
        for p in gk.list_portfolio():
            if f"({code})" in p["name"]:
                related.append({"code": p["id"], "title": p["name"].replace(f" ({code})", "")})
        L = ledger()
        for iid in L.ideas:
            a = L.latest(iid, "analyst")
            if a and a["sub"].get("directive_id") == code and iid in L.snap:
                related.append({"code": iid, "title": L.title(iid)})
    elif kind == "CAP":
        c = next((x for x in (gk._config_raw("capabilities") or {}).get("capabilities", []) if x["id"] == code), None)
        if not c:
            return None
        card.update(label="Capability", title=c["name"])
        facts.append(["Maturity", c["maturity"].replace("_", " ").capitalize()])
    elif kind == "PF":
        p = next((x for x in gk.list_portfolio() if x["id"] == code), None)
        if not p:
            return None
        sd = re.search(r"\((SD-\d{2})\)", p["name"])
        card.update(label="Portfolio item", title=re.sub(r"\s*\(SD-\d{2}\)", "", p["name"]), lede=p.get("description") or None)
        facts += [["Kind", p["kind"].replace("_", " ").capitalize()], ["Ambition", p["ambition_cell"].capitalize()]]
        if sd:
            related.append({"code": sd.group(1), "title": "Directive it serves"})
    elif kind == "IDEA":
        L = ledger()
        if code not in L.ideas:
            return None
        s = L.summary(code)
        card.update(label="Idea", title=s["title"], lede=headline_of(s["thesis"], 280), href=f"/ideas/{code}")
        facts += [["Stage", s["stage"].replace("_", " ").capitalize()], ["Ambition", (s["cell"] or "").capitalize()]]
        if s["score"] is not None:
            facts.append(["Panel strength", f"{s['score']} of 100"])
        if s["decision"]:
            facts.append(["Your decision", f"{s['decision']['action'].replace('_', ' ').capitalize()}: {s['decision']['reason']}"])
        if s["directive_id"]:
            related.append({"code": s["directive_id"], "title": "Directive it was judged against"})
    elif kind == "SIG":
        s = gk.q1("SELECT * FROM signals WHERE id=?", (code,))
        if not s:
            return None
        card.update(label="Signal", title=s["title"], lede=headline_of(s["excerpt"], 320))
        facts += [["Area", s["sensor"].replace("_", " ").capitalize()], ["Status", s["status"].capitalize()], ["Source", s["url"]], ["Retrieved", s["retrieved_at"][:10]]]
        if s["curator_note"]:
            facts.append(["Curator", s["curator_note"]])
    elif kind == "PRB":
        p = gk.q1("SELECT * FROM problems WHERE id=?", (code,))
        if not p:
            return None
        card.update(label="Problem", title=p["statement"])
        facts += [["For whom", p["for_whom"]], ["Why now", p["why_now"]]]
        related.append({"code": p["signal_id"], "title": "Signal it came from"})
        for i in gk.q("SELECT id FROM ideas WHERE problem_id=?", (code,)):
            related.append({"code": i["id"], "title": ledger().title(i["id"])})
    card.setdefault("lede", None)
    card["related"] = [r for r in related][:8]
    return card
