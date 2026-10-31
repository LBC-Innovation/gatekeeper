"""The team: who each agent is, in the order an idea meets them.

The personas and the instructions live in the agent files (claude-config/agents/). This adds only what a person wants
beside them: a short bio, when the agent works, and whether it may sit out. The file text is read from disk at request time,
so what the web app shows is always what is in the file. Only the fixed ids below are ever opened, never a path from a request.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]


def config_dir() -> Path:
    return Path(os.environ.get("GATEKEEPER_CONFIG_DIR", PROJECT / "claude-config")) / "agents"


# id, name, epithet, stage, schedule, can_sit_out, bio. Bios are drawn from each file's "Who you are" section.
AGENTS: list[dict] = [
    {"id": "scout", "name": "Scout", "epithet": "the field reporter", "stage": "source", "schedule": "Every run, one per area of change", "can_sit_out": False,
     "bio": "Goes out, reads the primary record, and comes back with what it saw and exactly where. Curious and literal. It never says whether something is a good idea; that is someone else's job."},
    {"id": "curator", "name": "Curator", "epithet": "the archivist", "stage": "source", "schedule": "Once per run", "can_sit_out": False,
     "bio": "Has a long memory and a skeptical eye, and is allergic to old things wearing new clothes. Drops duplicates, scores what is new to your ledger, and keeps only a few signals so your attention is protected."},
    {"id": "framer", "name": "Framer", "epithet": "the diagnostician", "stage": "source", "schedule": "Once per run", "can_sit_out": True,
     "bio": "Treats a signal as a symptom and writes the diagnosis: who has the problem, why it matters now, and what it is not. Patient, precise, and wary of solutions that arrive before anyone has said what is wrong."},
    {"id": "inventor", "name": "Inventor", "epithet": "the provocateur", "stage": "source", "schedule": "Once per problem", "can_sit_out": True,
     "bio": "Generous with ideas and stingy with judgment. Borrows mechanisms from unrelated fields, inverts assumptions, and keeps going past the obvious answer. Every idea comes with the smallest check that would test it."},
    {"id": "analyst", "name": "Analyst", "epithet": "the strategist", "stage": "judge", "schedule": "Once per idea, and again in round 2", "can_sit_out": False,
     "bio": "Has read every directive and capability sheet, and knows strategy is mostly about what you will not do. Fair and unsentimental. Also the first gate: a weak idea is parked before the full panel ever sees it."},
    {"id": "registrar", "name": "Registrar", "epithet": "the gatekeeper's clerk", "stage": "judge", "schedule": "Once per idea, and again in round 2", "can_sit_out": False,
     "bio": "Polite, exact and immovable. Doesn't care how exciting an idea is, only whether it is ready for the next gate. \"Someone said so\" scores a 1. Does not vote; its score decides fund the check or find out first."},
    {"id": "steward", "name": "Steward", "epithet": "the portfolio manager", "stage": "judge", "schedule": "Once per idea, and again in round 2", "can_sit_out": True,
     "bio": "Never falls in love with a single bet. Judges what an idea does to the shape of the whole book, and leans against the natural drift toward safe, incremental work."},
    {"id": "redteam", "name": "Red Team", "epithet": "the adversary", "stage": "judge", "schedule": "Once per idea", "can_sit_out": True,
     "bio": "The adversary the room needs and nobody wants to be. Argues the idea's strongest side first, then finds the one thing most likely to sink it. Never told whose idea it is, so the criticism can't play favourites."},
    {"id": "arbiter", "name": "Arbiter", "epithet": "the chair", "stage": "close", "schedule": "Once per run", "can_sit_out": False,
     "bio": "Chairs the panel and has no vote. The ranking arithmetic runs in code; the Arbiter writes short, neutral notes on who disagreed and what would settle it, like good meeting minutes."},
    {"id": "herald", "name": "Herald", "epithet": "the editor", "stage": "close", "schedule": "Once per run", "can_sit_out": False,
     "bio": "Respects your ten minutes. Writes the daily brief as a queue of decisions, cuts every word that doesn't help, and never pads a quiet day or invents a number."},
    {"id": "calibrator", "name": "Calibrator", "epithet": "the coach", "stage": "learn", "schedule": "Weekly", "can_sit_out": True,
     "bio": "Watches what you actually decide, not what you say you value, and points out patterns kindly and with evidence. Proposes up to three changes a week. Never changes anything itself."},
]
_BY_ID = {a["id"]: a for a in AGENTS}


def _split(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        if v:
            meta[k.strip()] = v.strip()
    return meta, m.group(2)


def _read(agent_id: str) -> tuple[Path, str] | None:
    p = config_dir() / f"gatekeeper-{agent_id}.md"
    return (p, p.read_text()) if p.is_file() else None


def _profile(a: dict, text: str | None, path: Path | None) -> dict:
    meta, _ = _split(text) if text else ({}, "")
    tools = [t.strip() for t in meta.get("tools", "").split(",") if t.strip()]
    prefixes = ("mcp__plugin_gatekeeper_gatekeeper__", "mcp__gatekeeper__")   # plugin install, then a checkout's own connector
    ledger = [t.removeprefix(p) for t in tools for p in prefixes if t.startswith(p)]
    other = [t for t in tools if not t.startswith("mcp__")]
    return {**a, "avatar": f"/avatars/{a['id']}.png", "model": meta.get("model"), "file": f"claude-config/agents/{path.name}" if path else None,
            "can_search_web": "WebSearch" in other, "tools": {"ledger": ledger, "other": other}}


def team() -> list[dict]:
    out = []
    for a in AGENTS:
        r = _read(a["id"])
        out.append(_profile(a, r[1] if r else None, r[0] if r else None))
    return out


def agent(agent_id: str) -> dict | None:
    a = _BY_ID.get(agent_id)
    if not a:
        return None
    r = _read(agent_id)
    return {**_profile(a, r[1] if r else None, r[0] if r else None), "markdown": r[1] if r else None}
