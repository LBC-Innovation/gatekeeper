"""One declaration per command. The MCP adapter and the REST API both read this table; neither holds any logic.

A command is a Gatekeeper method plus: a description, whether it only reads, and which surface may call it.
Agents get the `pipeline` surface; the person's Claude and the web app get `person`, which adds the decisions
an agent must never be able to make. Surface separation is enforced here, in the registry, not by prompt.
"""

from __future__ import annotations

import inspect
import typing
from dataclasses import dataclass
from typing import Any, Callable, Union, get_args, get_origin

from .core import Gatekeeper, Rejected
from .types import OVERRIDES

TOOLS: dict[str, tuple[str, bool]] = {
    # setup and configuration
    "get_setup_status": ("Which of the seven setup steps are done and what comes next.", True),
    "get_config": ("Current configuration. section: profile, strategy, capabilities, taste, weights, rules, bench; omit for all.", True),
    "config_history": ("Past versions of one configuration section, newest first, with who changed it and why.", True),
    "set_config": ("Save a new version of one configuration section (full body for that section) with a reason. "
                   "Changing strategy or capabilities queues re-scoring of live ideas.", False),
    "get_context": ("The business context rendered for one role (analyst, registrar, steward, redteam, framer, inventor, "
                    "curator, arbiter, herald, calibrator, scout, all).", True),
    "add_portfolio_item": ("Record a current product line (kind=line), an in-flight project (kind=in_flight) or a future goal, an area of interest not yet funded (kind=future_goal). Future goals do not count in the live mix.", False),
    "list_portfolio": ("Active portfolio items.", True),
    "update_portfolio_item": ("Retag a live portfolio item in place (ambition cell, four P, description), with a reason, to rebalance the book.", False),
    "retire_portfolio_item": ("Mark a portfolio item inactive, with a reason.", False),
    "add_exemplar": ("Record a past idea with a known fate and your reason: funded (glad you did), killed, regret_killed "
                     "(wish you had funded it) or regret_funded (funded, but should have said no). Used to calibrate.", False),
    "mark_calibrated": ("Record that the panel's ranking of the exemplars now matches your judgement.", False),
    # runs
    "start_run": ("Begin a pipeline run. Executes due defaults, adds kill recommendations, queues re-scores. Returns run_id.", False),
    "finish_run": ("Close a run with status done or failed.", False),
    "list_jobs": ("Jobs by status (pending, running, done, failed).", True),
    "update_job": ("Mark a job running, done or failed with a note.", False),
    # sensing
    "get_watchlist": ("Search terms per Drucker area, exclusions and taste. Scouts compose queries only from this.", True),
    "submit_signal": ("File one signal: sensor (Drucker area), title, url actually read, retrieved_at date, quoted excerpt.", False),
    "list_new_signals": ("Signals not yet curated.", True),
    "find_similar": ("Closest existing signals, ideas and portfolio items to a text, with word-overlap scores.", True),
    "curate_signal": ("Keep or drop a signal with a reason. Keeping needs novelty (0-1, at or above the floor) and four_p.", False),
    # generating
    "get_signal": ("One signal in full.", True),
    "list_unframed": ("Kept signals in a run that have no framed problem yet.", True),
    "frame_problem": ("State the problem behind a kept signal: statement, for_whom, why_now, and the alternatives you rejected.", False),
    "get_problem": ("One framed problem with its signal and the candidates drafted so far.", True),
    "submit_candidate": ("File one candidate idea for a problem, with technique, cell, four_p, first_check and claims for any figure.", False),
    # panel
    "get_idea": ("One idea with problem, signal and evidence. Not for Red Team.", True),
    "get_idea_blind": ("One idea with sponsor, origin and source sensor removed. Red Team uses this.", True),
    "get_evidence": ("All claims recorded against an idea.", True),
    "add_evidence": ("Attach sourced or estimated claims to an idea.", False),
    "get_portfolio": ("Live mix against target, alarms, stalled items; with idea_id, that idea's effect on the mix and overlaps.", True),
    "list_panel_work": ("What the panel still owes: analyst gate, full panel, round 2, re-scores, evidence requests, exemplars.", True),
    "submit_analyst_review": ("Analyst review: strategic_fit with directive_id, capability_match, gaps with acquisition paths, dependency.", False),
    "submit_registrar_review": ("Registrar review: six readiness dimensions scored 0-3, citing claim ids for 2 and above.", False),
    "submit_steward_review": ("Steward review: portfolio score, cannibalization risk, overlapping portfolio ids.", False),
    "raise_objection": ("Red Team: the strongest case against an idea, severity 0-1, and what evidence would answer it.", False),
    "get_round2_packet": ("Round-2 packet for one panelist: the objection and the other panelists' rationales, anonymized.", True),
    # resolve and deliver
    "compute_board": ("Resolve every fully reviewed idea into a score, band and action; fill your decision queue.", False),
    "get_reviews": ("All reviews, objections and the latest board entry for one idea.", True),
    "annotate_rank": ("Arbiter: two-line note on why an idea ranked where it did and where the panel disagreed.", False),
    "get_brief_data": ("Everything the daily brief may say for a run. The brief may not state anything not in here.", True),
    "write_brief": ("Save the daily brief (markdown) to briefs/ and the ledger.", False),
    "get_brief": ("A saved brief by date (YYYY-MM-DD), or the latest.", True),
    # you
    "get_board": ("The ranked board with header counts, alarms and your decision queue. Filters: cell, four_p, action, min_score.", True),
    "get_queue": ("Open decisions waiting on you, each with a default action and the date it executes.", True),
    "get_idea_record": ("Full record: deliberation arithmetic, every review and round, objections, evidence, what happens next.", True),
    "decide": ("Your decision on an idea: promote, kill, park, need_evidence, or keep (answers a kill recommendation). Reason required.", False),
    "set_my_rank": ("Save your own ordering of live ideas, best first. Returns where you disagree with the board.", False),
    "answer_objection": ("Answer a Red Team objection (answered) or accept the risk (accepted).", False),
    "request_evidence": ("Ask the panel for specific evidence on an idea before you decide.", False),
    "submit_my_idea": ("Your own idea or reframe: goes straight to the board, unscored and protected.", False),
    "get_pipeline_status": ("Runs, pending jobs, rejected writes, ideas by stage, queue and setup status.", True),
    "get_stalled": ("Promoted ideas by how long they have been idle relative to the typical gap.", True),
    # calibration
    "calibration_report": ("How well the panel orders the exemplars whose fate you know.", True),
    "what_if_weights": ("Preview rankings under other weights. Changes nothing.", True),
    "get_decisions": ("Your recent decisions with the board's view at the time, and your rank disagreements.", True),
    "propose_calibration": ("Calibrator: propose a weights, taste or rules change with rationale. You accept or reject.", False),
    "list_proposals": ("Calibration proposals by status (open, accepted, rejected).", True),
    "decide_proposal": ("Accept or reject a calibration proposal with a reason. Accepting applies it.", False),
    # backlog
    "sync_backlog": ("Load Epics and Features from the Azure DevOps snapshot into the searchable backlog index. Replaces the last load.", False),
    "find_backlog_matches": ("Backlog Epics and Features that may overlap one idea, with state, child rollup and idle days. Empty when "
                             "nothing matches well. Pass extra_terms with your own synonyms for a second try.", True),
    "submit_backlog_check": ("Cartographer: file the backlog check for one idea: a headline and a verdict (done, in_flight, pull_forward, "
                             "related, unrelated) with a reason for each item judged. Non-unrelated verdicts become sourced claims.", False),
    "get_backlog_check": ("The latest backlog check for an idea, with each item's current state and whether the backlog has been "
                          "reloaded since.", True),
    "update_run_stage": ("Orchestrator: report progress (scout, curate, frame, invent, gate, panel, round2, resolve, brief) so the web app "
                         "can show a live run banner.", False),
}


# Tools an agent must never hold: they record the person's judgement or change what every reviewer reads.
PERSON_ONLY = frozenset({
    "decide", "set_my_rank", "answer_objection", "request_evidence", "submit_my_idea", "set_config", "decide_proposal",
    "add_exemplar", "mark_calibrated", "add_portfolio_item", "update_portfolio_item", "retire_portfolio_item", "sync_backlog",
})


@dataclass
class Command:
    name: str
    description: str
    read_only: bool
    person_only: bool
    method: Callable
    signature: inspect.Signature     # typed, optional-aware: what the MCP and OpenAPI schemas are built from
    returns: Any

    def on(self, surface: str) -> bool:
        return surface == "person" or not self.person_only


def _nullable(t) -> bool:
    return t is type(None) or (get_origin(t) in (Union, getattr(__import__("types"), "UnionType", Union)) and type(None) in get_args(t))


def _typed_signature(method: Callable) -> tuple[inspect.Signature, Any]:
    hints = typing.get_type_hints(method, include_extras=True)
    params = []
    for name, p in inspect.signature(method).parameters.items():
        if name == "self":
            continue
        orig = hints.get(name, Any)
        ann = OVERRIDES.get(name, orig)
        if name in OVERRIDES and _nullable(orig):
            ann = Union[ann, None]
        default = p.default
        if default is inspect.Parameter.empty and _nullable(ann):
            default = None  # nullable means optional on the wire; the rules still require what round 1 needs
        params.append(inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, default=default, annotation=ann))
    return inspect.Signature(params), hints.get("return", Any)


def build_registry(gk: Gatekeeper) -> dict[str, Command]:
    out: dict[str, Command] = {}
    for name, (desc, ro) in TOOLS.items():
        method = getattr(gk, name)
        sig, ret = _typed_signature(method)
        out[name] = Command(name, desc, ro, name in PERSON_ONLY, method, sig, ret)
    return out


def invoke(gk: Gatekeeper, cmd: Command, args: dict, *, via: str | None = None) -> Any:
    """Call a command. A Rejected write is logged against the active run and re-raised for the adapter to present."""
    if via and "via" in cmd.signature.parameters:
        args = {**args, "via": via}
    try:
        return cmd.method(**args)
    except Rejected as e:
        gk.log_rejection(cmd.name, str(e), args, run_id=args.get("run_id"))
        raise
