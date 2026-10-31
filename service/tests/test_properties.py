"""Invariants that must hold for any board and any queue, checked with generated inputs (docs/06, section 8)."""

from hypothesis import given, settings, strategies as st

from gatekeeper import deliberation as D

RULES = dict(D.DEFAULT_RULES)
ACTIONS = ["PROMOTE", "NEED_EVIDENCE", "CONSIDER", "PARK", "REVIEW_OBJECTION", "CONTESTED"]
CELLS = ["core", "adjacent", "transformational"]


@st.composite
def boards(draw):
    n = draw(st.integers(0, 9))
    rows = []
    for k in range(n):
        rows.append({"idea_id": f"IDEA-{k:04d}", "action": draw(st.sampled_from(ACTIONS)), "score": draw(st.floats(0, 1)),
                     "ambition_cell": draw(st.sampled_from(CELLS)), "stage": draw(st.sampled_from(["board", "need_evidence"])),
                     "flags": draw(st.lists(st.sampled_from(["open objection, severity 0.80", "contested after round 2, spread 0.30"]),
                                            max_size=2, unique=True)),
                     "snapshot_id": 100 + k})
    return rows


@st.composite
def worlds(draw):
    rows = draw(boards())
    open_items = []
    for k, r in enumerate(rows):
        # A reachable queue: the system never leaves more open non-urgent items than the queue size.
        if len(open_items) < RULES["queue_size"] and draw(st.booleans()):
            stale = draw(st.sampled_from(ACTIONS))
            open_items.append({"id": k + 1, "idea_id": r["idea_id"], "recommended_action": stale, "default_action": D.default_for(stale),
                               "default_on": "2026-11-01", "why": D.queue_why({**r, "action": stale})})
    return rows, open_items


def apply(rows, open_items, plan):
    """The open queue after the plan, as (idea_id -> action)."""
    gone = {s["id"] for s in plan["supersede"]}
    q = {i["idea_id"]: i["recommended_action"] for i in open_items if i["id"] not in gone}
    for p in plan["insert"]:
        q[p["idea_id"]] = p["action"]
    return q


@settings(max_examples=300, deadline=None)
@given(worlds())
def test_queue_invariants(world):
    rows, open_items = world
    plan = D.reconcile_queue(rows, open_items, RULES, "2026-10-28")
    q = apply(rows, open_items, plan)
    by = {r["idea_id"]: r for r in rows}
    for iid, action in q.items():
        assert action == by[iid]["action"], "every open item states the board's current advice"
        assert action not in ("PARK", "PROTECTED"), "nothing to decide on a PARK"
    for r in rows:
        if r["action"] == "REVIEW_OBJECTION":
            assert r["idea_id"] in q, "a serious objection is always queued, even when the queue is full"
    non_urgent = [iid for iid in q if by[iid]["action"] != "REVIEW_OBJECTION"]
    assert len(non_urgent) <= RULES["queue_size"], "the cap binds everything except serious objections"


@settings(max_examples=200, deadline=None)
@given(worlds())
def test_reconcile_is_idempotent(world):
    rows, open_items = world
    plan = D.reconcile_queue(rows, open_items, RULES, "2026-10-28")
    gone = {s["id"] for s in plan["supersede"]}
    nxt = [i for i in open_items if i["id"] not in gone]
    base = max([i["id"] for i in open_items], default=0)
    for k, p in enumerate(plan["insert"]):
        nxt.append({"id": base + k + 1, "idea_id": p["idea_id"], "recommended_action": p["action"],
                    "default_action": p["default_action"], "default_on": p["default_on"], "why": p["why"]})
    again = D.reconcile_queue(rows, nxt, RULES, "2026-10-28")
    assert again["supersede"] == [] and again["insert"] == [], "a second pass on an unchanged board changes nothing"


@settings(max_examples=200, deadline=None)
@given(st.lists(st.tuples(st.text("abcdef", min_size=1, max_size=3), st.floats(0, 1)), max_size=12, unique_by=lambda x: x[0]),
       st.integers(1, 6))
def test_pick_queue_never_exceeds_size(items, size):
    rows = [{"idea_id": k, "action": "CONSIDER", "score": s, "ambition_cell": "core"} for k, s in items]
    assert len(D.pick_queue(rows, size)) <= size
