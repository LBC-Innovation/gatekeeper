"""The deliberation mechanism, as pure functions.

No model touches this arithmetic. Agents supply judgments (scores with
rationales); this module turns them into a ranked board, deterministically,
so every number on the board can be reproduced by hand.

Protocol (see docs/DELIBERATION.md for the argument behind it):

  Round 1  Analyst, Registrar and Steward score independently and blind to
           each other. Red Team files objections without seeing the sponsor.
  Trigger  A second round runs only when the panel disagrees (spread of
           round-1 scores >= rules.round2_dispersion) or Red Team raised a
           serious objection (severity >= rules.round2_severity).
  Round 2  Each panelist sees the objection and the other panelists'
           rationales, anonymized, plus the spread. Each may revise once,
           and must say why. Silence keeps the round-1 score.
  Resolve  Weighted score from the latest round per voting role (Analyst,
           Steward). The Registrar does not vote: its readiness for the
           first check gates PROMOTE versus NEED_EVIDENCE instead. Red Team
           sets a confidence band instead of a share of the score. Rules turn
           the result into a recommended action and a place in your queue.

Why the Registrar does not vote: it scores a different construct (is the
case built for the next gate) on a scale that sits low by construction for a
new idea. Averaged in, it capped every score; counted in the spread, it made
almost every idea look contested. See docs/DELIBERATION.md.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

PANEL_ROLES = ("analyst", "registrar", "steward")
VOTING_ROLES = ("analyst", "steward")  # the score and the spread come from these; registrar gates readiness

DEFAULT_WEIGHTS = {"analyst": 0.35, "steward": 0.30, "registrar": 0.20, "redteam_band": 0.15}

DEFAULT_RULES = {
    "promote": 0.65,                 # score at or above: recommend promote
    "park_below": 0.45,              # score below: recommend park
    "need_evidence_readiness": 0.34, # registrar readiness below this blocks promote
    "must_review_severity": 0.70,    # open objection at or above: always in your queue
    "round2_dispersion": 0.25,       # spread of round-1 scores that triggers round 2
    "round2_severity": 0.50,         # objection severity that triggers round 2
    "contested_dispersion": 0.25,    # spread still at or above this after round 2 = contested
    "analyst_gate": 0.30,            # analyst score below this parks the idea before the full panel
    "stall_ratio": 3.0,              # idle days / typical gap at or above this = stalled
    "stall_days_default": 14,        # typical gap used until there is history to measure
    "default_days": 7,               # days before a queued item's default action executes
    "queue_size": 3,                 # decisions put in front of you per run
    "signals_per_sensor": 5,
    "kept_per_run": 3,
    "candidates_per_problem": 6,
    "panel_per_run": 5,
    "duplicate_jaccard": 0.85,       # text overlap treated as a duplicate
}

ACTIONS = ("PROMOTE", "NEED_EVIDENCE", "CONSIDER", "PARK", "REVIEW_OBJECTION", "CONTESTED", "PROTECTED")


@dataclass
class Review:
    role: str
    round: int
    score: float
    rationale: str = ""
    sub: dict = field(default_factory=dict)


@dataclass
class Objection:
    severity: float
    status: str  # open | answered | accepted
    text: str = ""


@dataclass
class Outcome:
    score: float | None
    band: float
    low: float | None
    high: float | None
    dispersion: float | None
    readiness: float | None
    components: list[dict]
    flags: list[str]
    action: str
    rounds_used: int


def latest_by_role(reviews: list[Review], round_only: int | None = None) -> dict[str, Review]:
    """Reviews arrive in filing order. The last one filed per role wins, so a
    round-2 revision supersedes round 1, and a later re-score supersedes both."""
    out: dict[str, Review] = {}
    for r in reviews:
        if round_only is not None and r.round != round_only:
            continue
        out[r.role] = r
    return out


def spread(scores: list[float]) -> float | None:
    return (max(scores) - min(scores)) if len(scores) >= 2 else None


def needs_round2(reviews: list[Review], objections: list[Objection], rules: dict) -> tuple[bool, list[str]]:
    r1 = [r.score for r in latest_by_role(reviews, round_only=1).values() if r.role in VOTING_ROLES]
    reasons = []
    s = spread(r1)
    if s is not None and s >= rules["round2_dispersion"]:
        reasons.append(f"panel spread {s:.2f} >= {rules['round2_dispersion']:.2f}")
    sev = max([o.severity for o in objections if o.status == "open"], default=0.0)
    if sev >= rules["round2_severity"]:
        reasons.append(f"open objection severity {sev:.2f} >= {rules['round2_severity']:.2f}")
    return (bool(reasons), reasons)


def normalize_weights(weights: dict) -> dict:
    """Voting weights, normalized to sum to 1. A registrar weight in config is ignored: it does not vote."""
    total = sum(weights[r] for r in VOTING_ROLES)
    if total <= 0:
        raise ValueError("Analyst and Steward weights must sum to more than zero.")
    return {r: weights[r] / total for r in VOTING_ROLES}


def resolve(reviews: list[Review], objections: list[Objection], weights: dict, rules: dict,
            protected: bool = False) -> Outcome:
    if protected:
        return Outcome(None, 0.0, None, None, None, None, [], ["protected: your own idea, not scored"],
                       "PROTECTED", 0)

    latest = latest_by_role(reviews)
    missing = [r for r in PANEL_ROLES if r not in latest]
    norm = normalize_weights(weights)

    present = [r for r in VOTING_ROLES if r in latest]
    if not present:
        raise ValueError("No voting reviews (analyst or steward) to resolve.")
    # Renormalize over the roles that actually reviewed (a benched role is not a zero).
    wsum = sum(norm[r] for r in present)
    components = []
    score = 0.0
    for r in present:
        w = norm[r] / wsum
        contribution = w * latest[r].score
        score += contribution
        components.append({
            "role": r, "score": round(latest[r].score, 4), "weight": round(w, 4),
            "contribution": round(contribution, 4), "round": latest[r].round,
        })
    if "registrar" in latest:
        # Shown beside the score, never in it.
        components.append({"role": "registrar", "score": round(latest["registrar"].score, 4), "weight": 0.0,
                           "contribution": 0.0, "round": latest["registrar"].round, "voting": False})

    open_sev = max([o.severity for o in objections if o.status == "open"], default=0.0)
    band = weights.get("redteam_band", 0.0) * open_sev
    final_scores = [latest[r].score for r in present]
    disp = spread(final_scores)
    readiness = latest["registrar"].score if "registrar" in latest else None
    rounds_used = max(latest[r].round for r in present)

    flags: list[str] = []
    if missing:
        flags.append("missing review: " + ", ".join(missing))
    if open_sev >= rules["must_review_severity"]:
        flags.append(f"open objection, severity {open_sev:.2f}")
    if disp is not None and rounds_used >= 2 and disp >= rules["contested_dispersion"]:
        flags.append(f"contested after round 2, spread {disp:.2f}")

    if open_sev >= rules["must_review_severity"]:
        action = "REVIEW_OBJECTION"
    elif disp is not None and rounds_used >= 2 and disp >= rules["contested_dispersion"]:
        action = "CONTESTED"
    elif score >= rules["promote"]:
        action = "PROMOTE" if (readiness is None or readiness >= rules["need_evidence_readiness"]) else "NEED_EVIDENCE"
    elif score < rules["park_below"]:
        action = "PARK"
    elif readiness is not None and readiness < rules["need_evidence_readiness"]:
        action = "NEED_EVIDENCE"
    else:
        action = "CONSIDER"

    return Outcome(
        score=round(score, 4), band=round(band, 4),
        low=round(max(0.0, score - band), 4), high=round(min(1.0, score + band), 4),
        dispersion=None if disp is None else round(disp, 4),
        readiness=readiness, components=components, flags=flags, action=action,
        rounds_used=rounds_used,
    )


# Queue selection -----------------------------------------------------------

QUEUE_PRIORITY = {"REVIEW_OBJECTION": 0, "PROTECTED": 1, "CONTESTED": 2, "PROMOTE": 3,
                  "NEED_EVIDENCE": 4, "CONSIDER": 5, "PARK": 9}


def default_for(action: str) -> str:
    """The conservative default that executes if you do not decide in time."""
    return "need_evidence" if action == "NEED_EVIDENCE" else "park"


def pick_queue(rows: list[dict], size: int) -> list[dict]:
    """rows: dicts with idea_id, action, score, ambition_cell.

    PARK items never enter the queue, and neither do your own protected ideas:
    they sit on the board until you decide, with no default that could park them. One slot is reserved for the
    transformational cell when any eligible item exists, ranked on score only
    (taste is never applied to this slot by construction: score comes from
    the panel, not from your history).
    """
    eligible = [r for r in rows if r["action"] not in ("PARK", "PROTECTED")]
    eligible.sort(key=lambda r: (QUEUE_PRIORITY.get(r["action"], 8), -(r["score"] or 0)))
    picked: list[dict] = []
    explore = [r for r in eligible if r.get("ambition_cell") == "transformational"]
    if explore and size > 0:
        best = sorted(explore, key=lambda r: -(r["score"] or 0))[0]
        picked.append({**best, "slot": "exploratory"})
    for r in eligible:
        if len(picked) >= size:
            break
        if any(p["idea_id"] == r["idea_id"] for p in picked):
            continue
        picked.append({**r, "slot": "ranked"})
    picked.sort(key=lambda r: (QUEUE_PRIORITY.get(r["action"], 8), -(r["score"] or 0)))
    return picked


def queue_why(row: dict, slot: str = "ranked") -> str:
    return row["action"] + (f" ({slot} slot)" if slot == "exploratory" else "") + \
        ("; " + "; ".join(row["flags"]) if row["flags"] else "")


def reconcile_queue(rows: list[dict], open_items: list[dict], rules: dict, today_iso: str) -> dict:
    """The decision queue as a projection of the latest board. Pure: no I/O, the date is passed in.

    rows        latest board rows: idea_id, action, score, ambition_cell, stage, flags, snapshot_id
    open_items  open decision items: id, idea_id, recommended_action, default_action, default_on, why

    - An open item whose advice changed is superseded and re-queued with the new advice. It keeps its original
      default date unless the default action itself changed, so silence is never rewarded with extra time.
    - An open item whose idea now reads PARK or PROTECTED leaves the queue: there is nothing left to decide.
    - A serious objection (REVIEW_OBJECTION, severity at or above must_review_severity) always enters the queue,
      even when it is already full. This is the rule DELIBERATION.md states; v1 enforced it only when a slot was free.
    - Remaining slots go to the usual priority order with its reserved exploratory seat.
    """
    from datetime import date, timedelta
    by = {r["idea_id"]: r for r in rows}
    size = int(rules["queue_size"])
    fresh_default = (date.fromisoformat(today_iso) + timedelta(days=int(rules["default_days"]))).isoformat()
    supersede: list[dict] = []
    refresh: list[tuple[int, int]] = []
    insert: list[dict] = []
    taken: set[str] = set()

    for it in sorted(open_items, key=lambda x: x["id"]):
        r = by.get(it["idea_id"])
        if r is None:                      # not on this board (still being reviewed): leave it alone
            taken.add(it["idea_id"])
            continue
        if r["action"] in ("PARK", "PROTECTED"):
            supersede.append({"id": it["id"], "idea_id": it["idea_id"], "reason": f"the board now reads {r['action']}"})
            continue
        slot = "exploratory" if "(exploratory slot)" in (it["why"] or "") else "ranked"
        why = queue_why(r, slot)
        taken.add(it["idea_id"])
        if r["action"] == it["recommended_action"] and why == it["why"]:
            if r.get("snapshot_id") is not None:
                refresh.append((it["id"], r["snapshot_id"]))
            continue
        d_action = default_for(r["action"])
        why_changed = (f"advice changed from {it['recommended_action']} to {r['action']}" if r["action"] != it["recommended_action"]
                       else "the numbers behind the advice changed")
        supersede.append({"id": it["id"], "idea_id": it["idea_id"], "reason": why_changed})
        insert.append({"idea_id": it["idea_id"], "action": r["action"], "why": why, "default_action": d_action,
                       "default_on": it["default_on"] if d_action == it["default_action"] else fresh_default,
                       "snapshot_id": r.get("snapshot_id"), "forced": False, "replaces": it["id"]})

    forced = sorted((r for r in rows if r["action"] == "REVIEW_OBJECTION" and r["stage"] != "protected" and r["idea_id"] not in taken),
                    key=lambda r: (-(r["score"] or 0), r["idea_id"]))
    for r in forced:
        insert.append({"idea_id": r["idea_id"], "action": r["action"], "why": queue_why(r), "default_action": default_for(r["action"]),
                       "default_on": fresh_default, "snapshot_id": r.get("snapshot_id"), "forced": True, "replaces": None})
        taken.add(r["idea_id"])

    slots = max(0, size - len(taken))
    pool = [r for r in rows if r["idea_id"] not in taken and r["stage"] != "need_evidence"]
    for p in pick_queue(pool, slots):
        insert.append({"idea_id": p["idea_id"], "action": p["action"], "why": queue_why(p, p["slot"]),
                       "default_action": default_for(p["action"]), "default_on": fresh_default,
                       "snapshot_id": p.get("snapshot_id"), "forced": False, "replaces": None})
    return {"supersede": supersede, "refresh": refresh, "insert": insert}


# Portfolio arithmetic ------------------------------------------------------

CELLS = ("core", "adjacent", "transformational")


def mix(counts: dict[str, int]) -> dict[str, float]:
    total = sum(counts.get(c, 0) for c in CELLS)
    return {c: (counts.get(c, 0) / total if total else 0.0) for c in CELLS}


def mix_distance(shares: dict[str, float], target: dict[str, float]) -> float:
    return sum(abs(shares[c] - target.get(c, 0.0)) for c in CELLS)


def mix_delta(counts: dict[str, int], target: dict[str, float], cell: str) -> float:
    """Positive = adding one item in `cell` moves the mix toward target."""
    before = mix_distance(mix(counts), target)
    after_counts = dict(counts)
    after_counts[cell] = after_counts.get(cell, 0) + 1
    after = mix_distance(mix(after_counts), target)
    return round(before - after, 4)


# Calibration ---------------------------------------------------------------

# regret_funded: funded in reality, but in hindsight should have been declined. It belongs at the bottom.
OUTCOME_ORDER = {"funded": 2, "regret_killed": 1, "killed": 0, "regret_funded": 0}


def pairwise_agreement(items: list[dict]) -> dict:
    """items: dicts with idea_id, outcome (funded/regret_killed/killed/regret_funded), score.

    For every pair whose real outcomes differ, did the panel score the better
    outcome higher? Returns the agreement rate and the pairs it got wrong.
    """
    pairs, agree, wrong = 0, 0, []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            oa, ob = OUTCOME_ORDER[a["outcome"]], OUTCOME_ORDER[b["outcome"]]
            if oa == ob or a["score"] is None or b["score"] is None:
                continue
            pairs += 1
            better, worse = (a, b) if oa > ob else (b, a)
            if better["score"] > worse["score"]:
                agree += 1
            else:
                wrong.append({"should_rank_higher": better["idea_id"], "than": worse["idea_id"],
                              "scores": [better["score"], worse["score"]]})
    return {"pairs": pairs, "agreement": (agree / pairs) if pairs else None, "wrong": wrong}


def rank_disagreements(my_order: list[str], board_order: list[str]) -> list[dict]:
    """Pairs you ordered differently from the board. The calibrator's best signal."""
    pos_board = {iid: i for i, iid in enumerate(board_order)}
    out = []
    mine = [i for i in my_order if i in pos_board]
    for i in range(len(mine)):
        for j in range(i + 1, len(mine)):
            hi, lo = mine[i], mine[j]
            if pos_board[hi] > pos_board[lo]:
                out.append({"you_prefer": hi, "over": lo,
                            "board_rank": [pos_board[hi] + 1, pos_board[lo] + 1]})
    return out


def stall_ratio(idle_days: float, typical_gap_days: float | None, default_gap: float) -> float:
    gap = typical_gap_days if typical_gap_days and typical_gap_days > 0 else default_gap
    return round(idle_days / gap, 2)


def median_or_none(xs: list[float]) -> float | None:
    return statistics.median(xs) if xs else None
