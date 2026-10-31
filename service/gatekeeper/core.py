"""Gatekeeper ledger: every tool the agents and you call, as plain methods.

The MCP server (gatekeeper_server.py) is a thin wrapper over this class, so
everything here can be tested without a model in the loop.

Every write goes through a validator. A rejected write raises `Rejected` with
a message written for the agent that sent it: what was wrong and how to fix it.
Rejections are logged so you can see what agents are getting wrong.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
import sqlite3
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from . import deliberation as D
from .backlog import BacklogMixin

DRUCKER_AREAS = (
    "unexpected_occurrences", "incongruities", "process_needs", "industry_market_change",
    "demographics", "perception_shifts", "new_knowledge",
)
INTERNAL_AREAS = ("unexpected_occurrences", "incongruities", "process_needs")
TECHNIQUES = ("forced_relationship", "compare_contrast", "forced_solutions", "compounding")
FOUR_P = ("product", "process", "position", "paradigm")
PORTFOLIO_KINDS = ("line", "in_flight", "future_goal")
CELLS = D.CELLS
CONFIDENCE = ("low", "medium", "high")
ACQUISITION = ("hire", "partner", "buy", "build", "none")
READINESS_DIMS = ("business_case", "product_desc", "design_docs", "resource_plan",
                  "investment_support", "prototype")
BENCHABLE = ("steward", "redteam", "framer", "inventor", "calibrator")
LIVE_STAGES = ("board", "need_evidence", "protected", "promoted")
APPEND_ONLY = ("config_versions", "claims", "reviews", "decisions", "my_rank", "events",
               "rejections", "board_snapshots", "rank_notes", "briefs", "panel_admissions", "run_stages", "backlog_checks")
NO_PATH_CEILING = 0.5  # capability ceiling when any gap has acquisition_path "none"

STOP = set("""the and for with that this from into over under about their there they them
then than were been being have has had are was not but you your our ours its it's can could
would should will shall may might must also more most less such each per via using use used
which who whom what when where why how all any some one two new within without across""".split())


class Rejected(ValueError):
    """A write the ledger refused. The message tells the caller how to fix it."""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def today() -> date:
    return datetime.now().astimezone().date()


def tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) >= 3 and t not in STOP}


def jaccard(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return round(len(ta & tb) / len(ta | tb), 4)


def url_key(url: str) -> str:
    p = urlparse(url.strip())
    host = (p.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    q = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith("utm_")]
    path = p.path.rstrip("/") or "/"
    return urlunparse(("", host, path, "", urlencode(q), ""))


def parse_when(value: str, field: str) -> str:
    try:
        if len(value) == 10:
            return date.fromisoformat(value).isoformat()
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except Exception:
        raise Rejected(f"{field} must be an ISO date like 2026-10-08 (got {value!r}).")


_NB = r"(?<![\w.\-/#])"  # not the tail of an id (IDEA-2026-0031), a decimal (0.5833) or a path
NUMBER_RE = re.compile(
    r"(\$\s?\d[\d,]*(?:\.\d+)?\s?(?:[kmb]|thousand|million|billion)?\b"
    r"|" + _NB + r"\d[\d,]*(?:\.\d+)?\s?(?:%|percent\b|x\b|million\b|billion\b|thousand\b)"
    r"|" + _NB + r"\d{1,3}(?:,\d{3})+(?:\.\d+)?\b"
    r"|" + _NB + r"\d{3,}(?:\.\d+)?\b)",
    re.IGNORECASE,
)
# A number right after these is a citation (HB 2101, 23 CFR 655, Section 112), not a figure.
CITATION_BEFORE = re.compile(r"(?:\b[A-Z]{2,6}|\b(?:No|Section|Sec|Part|Rule|Docket|Bill|Chapter|Title|Art)\.?|§)\s*$")


# "claim 136", "claims 79/80", "claim ids 112, 114 and 141", "claims 109 to 115", "claim #108", "[c:107]".
# These point at ledger claims. They are references, not figures, and are checked against the ledger instead.
_REF_NUM = r"#?\d+"
CLAIM_REF_RE = re.compile(
    r"(?:\b[Cc]laims?\s*(?:ids?\s*)?" + _REF_NUM + r"(?:\s*(?:,|/|&amp;|&|\band\b|\bor\b|\bto\b|[-\u2013])\s*" + _REF_NUM + r")*"
    r"|\[c:\d+(?:\s*,\s*\d+)*\])")


def claim_refs(text: str) -> set[int]:
    """Claim ids a text refers to."""
    out: set[int] = set()
    for m in CLAIM_REF_RE.finditer(text or ""):
        out |= {int(n) for n in re.findall(r"\d+", m.group(0))}
    return out


RUN_GUARD_MINUTES = 30


def _digits(s: str) -> str:
    return re.sub(r"[^\d.]", "", s).rstrip(".")


def unbacked_numbers(text: str, claims: list[dict], extra_backing: str = "") -> list[str]:
    """Figures in `text` that no claim states. Years, ids and citations are ignored.

    A figure is backed when it appears in a claim's statement, value or quoted excerpt,
    or in `extra_backing` (numbers the system itself supplied, such as board scores)."""
    found = []
    backing = " ".join(f"{c.get('statement','')} {c.get('value','') or ''} {c.get('excerpt','') or ''}" for c in claims)
    backing += " " + (extra_backing or "")
    flat = backing.replace(",", "")
    backing_digits = {_digits(m) for m in NUMBER_RE.findall(backing)} | {x.rstrip(".") for x in re.findall(r"\d[\d.]*", flat)}
    # Claim references are checked against the ledger separately; they are not figures.
    text = CLAIM_REF_RE.sub(lambda m: " " * len(m.group(0)), text or "")
    for m in NUMBER_RE.finditer(text):
        raw = m.group(0)
        d = _digits(raw)
        if not d:
            continue
        if re.fullmatch(r"(19|20)\d\d", d):
            continue
        if CITATION_BEFORE.search(text[max(0, m.start() - 12):m.start()]):
            continue
        if d not in backing_digits:
            found.append(raw.strip())
    return found


def _pct_backing(obj) -> str:
    """Render numbers the system supplied, plus their percentage forms, as backing text."""
    nums = re.findall(r"\d+\.\d+|\d+", json.dumps(obj, default=str))
    out = list(nums)
    for n in nums:
        try:
            v = float(n)
            if 0 <= v <= 1:
                out += [str(round(v * 100)), f"{v * 100:.1f}".rstrip("0").rstrip("."), f"{v:.2f}", f"{v:.1f}"]
        except ValueError:
            pass
    return " ".join(out)


class Gatekeeper(BacklogMixin):
    def __init__(self, db_path: str | Path, home: str | Path | None = None):
        self.db_path = Path(db_path)
        self.home = Path(home) if home else self.db_path.parent.parent
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=8000")
        schema = (Path(__file__).parent / "schema.sql").read_text()
        with self.lock:
            self._migrate_ideas_outcomes(schema)
            self._migrate_objections_superseded(schema)
            self._migrate_portfolio_kinds(schema)
            self.conn.executescript(schema)
            # Additive column migrations for ledgers created before these columns existed.
            self._add_column("queue_items", "snapshot_id", "INTEGER")
            self._add_column("decisions", "via", "TEXT")
            self._add_column("ideas", "title", "TEXT")            # a short name for lists; the thesis stays the full sentence
            self._add_column("objections", "headline", "TEXT")    # one plain sentence a person can read without opening the argument
            for t in APPEND_ONLY:
                self.conn.execute(
                    f"CREATE TRIGGER IF NOT EXISTS {t}_no_update BEFORE UPDATE ON {t} "
                    f"BEGIN SELECT RAISE(ABORT, '{t} is append-only'); END;")
                self.conn.execute(
                    f"CREATE TRIGGER IF NOT EXISTS {t}_no_delete BEFORE DELETE ON {t} "
                    f"BEGIN SELECT RAISE(ABORT, '{t} is append-only'); END;")

    def _add_column(self, table: str, column: str, decl: str):
        cols = {r[1] for r in self.conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in cols:
            self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")

    def _migrate_ideas_outcomes(self, schema: str):
        """Databases created before 'regret_funded' existed carry the old CHECK; rebuild the table once."""
        row = self.conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='ideas'").fetchone()
        if not row or "regret_funded" in row[0]:
            return
        create = re.search(r"CREATE TABLE IF NOT EXISTS ideas \(.*?\n\);", schema, re.S).group(0)
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self.conn.execute("ALTER TABLE ideas RENAME TO ideas_old")
            self.conn.execute(create)
            self.conn.execute("INSERT INTO ideas SELECT * FROM ideas_old")
            self.conn.execute("DROP TABLE ideas_old")
            self.conn.execute("COMMIT")
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise

    def _migrate_objections_superseded(self, schema: str):
        """Databases created before 'superseded' existed carry the old CHECK; rebuild the table once."""
        row = self.conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='objections'").fetchone()
        if not row or "superseded" in row[0]:
            return
        create = re.search(r"CREATE TABLE IF NOT EXISTS objections \(.*?\n\);", schema, re.S).group(0)
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self.conn.execute("ALTER TABLE objections RENAME TO objections_old")
            self.conn.execute(create)
            self.conn.execute("INSERT INTO objections SELECT * FROM objections_old")
            self.conn.execute("DROP TABLE objections_old")
            self.conn.execute("COMMIT")
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise

    def _migrate_portfolio_kinds(self, schema: str):
        """Databases created before 'future_goal' existed carry the old CHECK; rebuild the table once."""
        row = self.conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='portfolio_items'").fetchone()
        if not row or "future_goal" in row[0]:
            return
        create = re.search(r"CREATE TABLE IF NOT EXISTS portfolio_items \(.*?\n\);", schema, re.S).group(0)
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self.conn.execute("ALTER TABLE portfolio_items RENAME TO portfolio_items_old")
            self.conn.execute(create)
            self.conn.execute("INSERT INTO portfolio_items SELECT * FROM portfolio_items_old")
            self.conn.execute("DROP TABLE portfolio_items_old")
            self.conn.execute("COMMIT")
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise

    def close(self):
        with self.lock:
            self.conn.close()

    # ------------------------------------------------------------------ plumbing

    @contextlib.contextmanager
    def tx(self):
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                yield self.conn
                self.conn.execute("COMMIT")
            except BaseException:
                self.conn.execute("ROLLBACK")
                raise

    def q(self, sql: str, args=()) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def q1(self, sql: str, args=()) -> dict | None:
        rows = self.q(sql, args)
        return rows[0] if rows else None

    def _event(self, c, idea_id, run_id, actor, event, detail=None):
        c.execute("INSERT INTO events(idea_id, run_id, at, actor, event, detail) VALUES (?,?,?,?,?,?)",
                  (idea_id, run_id, now_iso(), actor, event, json.dumps(detail) if detail is not None else None))
        if idea_id:
            c.execute("UPDATE ideas SET last_activity_at=? WHERE id=?", (now_iso(), idea_id))

    def _current_run_id(self) -> int | None:
        row = self.q1("SELECT id FROM runs WHERE status='running' ORDER BY id DESC LIMIT 1")
        return row["id"] if row else None

    def log_rejection(self, tool: str, reason: str, payload: dict | None = None, run_id=None):
        if run_id is None:
            run_id = self._current_run_id()  # most tools take no run_id; the active run is the honest attribution
        with self.tx() as c:
            c.execute("INSERT INTO rejections(run_id, tool, reason, payload, created_at) VALUES (?,?,?,?,?)",
                      (run_id, tool, reason, json.dumps(payload, default=str)[:4000] if payload else None, now_iso()))

    def _next_id(self, c, prefix: str, table: str) -> str:
        year = today().year
        row = c.execute(f"SELECT id FROM {table} WHERE id LIKE ? ORDER BY id DESC LIMIT 1",
                        (f"{prefix}-{year}-%",)).fetchone()
        n = int(row[0].rsplit("-", 1)[1]) + 1 if row else 1
        return f"{prefix}-{year}-{n:04d}"

    def _idea(self, idea_id: str) -> dict:
        row = self.q1("SELECT * FROM ideas WHERE id=?", (idea_id,))
        if not row:
            raise Rejected(f"No idea with id {idea_id}.")
        return row

    def _run(self, run_id: int | None, require_running=True) -> dict | None:
        if run_id is None:
            return None
        run = self.q1("SELECT * FROM runs WHERE id=?", (run_id,))
        if not run:
            raise Rejected(f"No run with id {run_id}. Call start_run first.")
        if require_running and run["status"] != "running":
            raise Rejected(f"Run {run_id} is {run['status']}, not running.")
        return run

    @staticmethod
    def _need(cond, msg):
        if not cond:
            raise Rejected(msg)

    @staticmethod
    def _unit(x, name) -> float:
        try:
            v = float(x)
        except Exception:
            raise Rejected(f"{name} must be a number between 0 and 1.")
        if not 0 <= v <= 1:
            raise Rejected(f"{name} must be between 0 and 1 (got {v}).")
        return v

    @staticmethod
    def _text(x, name, lo=10, hi=4000) -> str:
        if not isinstance(x, str) or len(x.strip()) < lo:
            raise Rejected(f"{name} is required and must be at least {lo} characters.")
        if len(x) > hi:
            raise Rejected(f"{name} is too long ({len(x)} characters, limit {hi}). Tighten it.")
        return x.strip()

    # ------------------------------------------------------------------ config

    def _config_raw(self, section: str) -> dict | None:
        row = self.q1("SELECT body FROM config_versions WHERE section=? ORDER BY id DESC LIMIT 1", (section,))
        return json.loads(row["body"]) if row else None

    def weights(self) -> dict:
        return {**D.DEFAULT_WEIGHTS, **(self._config_raw("weights") or {})}

    def rules(self) -> dict:
        return {**D.DEFAULT_RULES, **(self._config_raw("rules") or {})}

    def strategy(self) -> dict:
        return self._config_raw("strategy") or {}

    def benched(self) -> dict[str, str]:
        b = self._config_raw("bench") or {}
        return {x["role"]: x["reason"] for x in b.get("benched", [])}

    def required_panel(self) -> list[str]:
        out = [r for r in D.PANEL_ROLES if r not in self.benched()]
        return out

    def get_config(self, section: str | None = None) -> dict:
        sections = ["profile", "strategy", "capabilities", "taste", "weights", "rules", "bench"]
        if section:
            self._need(section in sections, f"section must be one of {sections}.")
            sections = [section]
        out = {}
        for s in sections:
            if s == "weights":
                out[s] = self.weights()
            elif s == "rules":
                out[s] = self.rules()
            else:
                out[s] = self._config_raw(s)
            ver = self.q1("SELECT id, created_at, actor, reason FROM config_versions WHERE section=? "
                          "ORDER BY id DESC LIMIT 1", (s,))
            out[f"{s}_version"] = ver
        return out

    def config_history(self, section: str, limit: int = 20) -> list[dict]:
        return self.q("SELECT id, created_at, actor, reason, body FROM config_versions WHERE section=? "
                      "ORDER BY id DESC LIMIT ?", (section, limit))

    def _validate_section(self, section: str, body: dict) -> dict:
        need, unit, text = self._need, self._unit, self._text
        need(isinstance(body, dict), "body must be an object.")
        if section == "profile":
            need(isinstance(body.get("company"), str) and body["company"].strip(), "profile.company is required.")
            need(isinstance(body.get("urls", []), list), "profile.urls must be a list of URLs.")
            for u in body.get("urls", []):
                need(isinstance(u, str) and u.startswith(("http://", "https://")), f"Bad URL in profile.urls: {u!r}")
            body.setdefault("summary", "")
            prev = self._config_raw("profile") or {}
            body["confirmed"] = bool(body.get("confirmed", prev.get("confirmed", False)))
        elif section == "strategy":
            ds = body.get("directives", [])
            need(isinstance(ds, list), "strategy.directives must be a list.")
            seen = set()
            for d in ds:
                need(isinstance(d, dict) and re.fullmatch(r"SD-\d{2,3}", str(d.get("id", ""))),
                     "Each directive needs an id like SD-01.")
                need(d["id"] not in seen, f"Duplicate directive id {d['id']}.")
                seen.add(d["id"])
                text(d.get("statement"), f"{d['id']}.statement", lo=8, hi=400)
                d["funded"] = bool(d.get("funded", False))
                d["retired"] = bool(d.get("retired", False))
            surf = body.get("surface", {})
            need(isinstance(surf, dict) and any(surf.get(k) for k in ("products", "processes", "business_models")),
                 "strategy.surface must turn on at least one of products, processes, business_models.")
            wl = body.get("watchlist", {})
            need(isinstance(wl, dict), "strategy.watchlist must map Drucker areas to lists of search terms.")
            for area, terms in wl.items():
                need(area in DRUCKER_AREAS, f"Unknown watchlist area {area!r}. Use one of {list(DRUCKER_AREAS)}.")
                need(isinstance(terms, list) and all(isinstance(t, str) and t.strip() for t in terms),
                     f"watchlist.{area} must be a list of search terms.")
            mt = body.get("mix_target", {"core": 0.6, "adjacent": 0.3, "transformational": 0.1, "tolerance": 0.05})
            for cell in CELLS:
                unit(mt.get(cell, 0), f"mix_target.{cell}")
            need(abs(sum(float(mt.get(c, 0)) for c in CELLS) - 1) <= 0.011, "mix_target core + adjacent + transformational must sum to 1.")
            need(0 <= float(mt.get("tolerance", 0.05)) <= 0.5, "mix_target.tolerance must be between 0 and 0.5.")
            mt.setdefault("tolerance", 0.05)
            body["mix_target"] = mt
            body.setdefault("exclusions", [])
            body["exploratory_floor"] = int(body.get("exploratory_floor", 2))
            body["novelty_floor"] = unit(body.get("novelty_floor", 0.35), "novelty_floor")
        elif section == "capabilities":
            caps = body.get("capabilities", [])
            need(isinstance(caps, list), "capabilities.capabilities must be a list.")
            for c in caps:
                need(re.fullmatch(r"CAP-\d{2,3}", str(c.get("id", ""))), "Each capability needs an id like CAP-01.")
                text(c.get("name"), f"{c['id']}.name", lo=3, hi=200)
                need(c.get("maturity") in ("research", "prototype", "production"),
                     f"{c['id']}.maturity must be research, prototype or production.")
            for r in body.get("reachable", []):
                text(r.get("name"), "reachable.name", lo=3, hi=200)
                need(r.get("path") in ("hire", "partner", "buy", "build"), "reachable.path must be hire, partner, buy or build.")
            body.setdefault("reachable", [])
        elif section == "taste":
            for k in ("likes", "dislikes"):
                for t in body.get(k, []):
                    need(isinstance(t, dict), f"taste.{k} entries are objects with text and supported_by.")
                    text(t.get("text"), f"taste.{k}.text", lo=8, hi=300)
                    t.setdefault("supported_by", [])
                body.setdefault(k, [])
        elif section == "weights":
            merged = {**self.weights(), **body}
            for k in D.DEFAULT_WEIGHTS:
                merged[k] = unit(merged[k], f"weights.{k}")
            need(sum(merged[r] for r in D.VOTING_ROLES) > 0, "Analyst or Steward weight must be above zero.")
            unknown = set(body) - set(D.DEFAULT_WEIGHTS)
            need(not unknown, f"Unknown weight keys {sorted(unknown)}.")
            body = merged
        elif section == "rules":
            unknown = set(body) - set(D.DEFAULT_RULES)
            need(not unknown, f"Unknown rule keys {sorted(unknown)}. Known: {sorted(D.DEFAULT_RULES)}.")
            merged = {**self.rules(), **body}
            for k, v in merged.items():
                need(isinstance(v, (int, float)), f"rules.{k} must be a number.")
            need(merged["park_below"] <= merged["promote"], "rules.park_below must not exceed rules.promote.")
            body = {k: merged[k] for k in D.DEFAULT_RULES}
        elif section == "bench":
            for b in body.get("benched", []):
                need(b.get("role") in BENCHABLE,
                     f"Only {list(BENCHABLE)} can sit out. Analyst and Registrar are the spine and always play.")
                text(b.get("reason"), f"bench reason for {b.get('role')}", lo=10, hi=400)
            body.setdefault("benched", [])
        return body

    def set_config(self, section: str, body: dict, reason: str, actor: str = "human") -> dict:
        self._need(section in ("profile", "strategy", "capabilities", "taste", "weights", "rules", "bench"),
                   "Unknown section.")
        reason = self._text(reason, "reason")
        body = self._validate_section(section, json.loads(json.dumps(body)))
        current = self._config_raw(section)
        canon = json.dumps(body, sort_keys=True)
        if current is not None and json.dumps(current, sort_keys=True) == canon:
            return {"section": section, "changed": False}
        with self.tx() as c:
            cur = c.execute("INSERT INTO config_versions(section, body, reason, actor, created_at) VALUES (?,?,?,?,?)",
                            (section, canon, reason, actor, now_iso()))
            vid = cur.lastrowid
            self._event(c, None, None, actor, "config_changed", {"section": section, "version": vid, "reason": reason})
            queued = 0
            if section in ("strategy", "capabilities") and current is not None and self._scoring_view(section, current) != self._scoring_view(section, body):
                queued = self._queue_rescore(c, f"{section} changed: {reason}")
        self.export_context()
        return {"section": section, "changed": True, "version": vid, "rescore_jobs_queued": queued}

    @staticmethod
    def _scoring_view(section: str, body: dict) -> str:
        """What reviewers actually read. The scout watch list steers searches only, so editing it never re-scores ideas."""
        b = {k: v for k, v in body.items() if k != "watchlist"} if section == "strategy" else body
        return json.dumps(b, sort_keys=True)

    def _queue_rescore(self, c, why: str) -> int:
        live = c.execute("SELECT id FROM ideas WHERE stage IN ('board','need_evidence','promoted')").fetchall()
        n = 0
        for (iid,) in live:
            for role in [r for r in ("analyst", "steward") if r in self.required_panel()]:
                exists = c.execute("SELECT 1 FROM jobs WHERE kind='rescore' AND idea_id=? AND role=? AND status='pending'",
                                   (iid, role)).fetchone()
                if not exists:
                    c.execute("INSERT INTO jobs(kind, idea_id, role, payload, status, created_at, updated_at) "
                              "VALUES ('rescore',?,?,?,'pending',?,?)", (iid, role, json.dumps({"why": why}), now_iso(), now_iso()))
                    n += 1
        return n

    # ------------------------------------------------------------------ context rendering

    def _render(self, role: str = "all") -> str:
        prof = self._config_raw("profile") or {}
        st = self.strategy()
        caps = self._config_raw("capabilities") or {}
        taste = self._config_raw("taste") or {}
        lines = [f"# Context for {role}", ""]
        if prof:
            lines += [f"## Company: {prof.get('company','')}", prof.get("summary", ""), ""]
        if st:
            surf = [k for k in ("products", "processes", "business_models") if st.get("surface", {}).get(k)]
            lines += ["## Innovation surface", "Hunting for: " + ", ".join(surf), ""]
            if role != "scout":
                lines += ["## Strategic directives"]
                for d in st.get("directives", []):
                    if not d.get("retired"):
                        lines.append(f"- {d['id']}: {d['statement']}" + (" (funded)" if d.get("funded") else "")
                                     + (f" [horizon {d['horizon']}]" if d.get("horizon") else ""))
                retired = [d for d in st.get("directives", []) if d.get("retired")]
                if retired:
                    lines += ["", "Retired directives (do not cite): " + ", ".join(d["id"] for d in retired)]
                lines.append("")
            if st.get("exclusions"):
                lines += ["## Off limits"] + [f"- {x}" for x in st["exclusions"]] + [""]
            mt = st.get("mix_target", {})
            lines += ["## Portfolio target",
                      f"core {mt.get('core')} / adjacent {mt.get('adjacent')} / transformational {mt.get('transformational')}"
                      f" (tolerance {mt.get('tolerance')}); exploratory floor {st.get('exploratory_floor')}; "
                      f"novelty floor {st.get('novelty_floor')}", ""]
        if caps and role != "scout":
            lines += ["## Capabilities"]
            for c in caps.get("capabilities", []):
                lines.append(f"- {c['id']} {c['name']} ({c['maturity']})")
            if caps.get("reachable"):
                lines += ["", "Reachable:"] + [f"- {r['name']} via {r['path']}" + (f", lead time {r['lead_time']}" if r.get("lead_time") else "")
                                               for r in caps["reachable"]]
            lines.append("")
        if taste.get("likes") or taste.get("dislikes"):
            lines += ["## What the decision-maker values"]
            lines += [f"- Likes: {t['text']}" for t in taste.get("likes", [])]
            lines += [f"- Dislikes: {t['text']}" for t in taste.get("dislikes", [])]
            lines.append("")
        if role in ("steward", "analyst", "all"):
            items = self.q("SELECT id, kind, name, ambition_cell FROM portfolio_items WHERE active=1 ORDER BY id")
            live = [i for i in items if i["kind"] != "future_goal"]
            goals = [i for i in items if i["kind"] == "future_goal"]
            if live:
                lines += ["## Current portfolio"] + [f"- {i['id']} [{i['kind']}, {i['ambition_cell']}] {i['name']}" for i in live] + [""]
            if goals:
                lines += ["## Areas of interest (considering, not funded, not counted in the mix)"] + \
                         [f"- {i['id']} [{i['ambition_cell']} if pursued] {i['name']}" for i in goals] + [""]
        ex = self._recent_examples()
        if ex and role in ("scout", "curator", "framer", "inventor", "all"):
            lines += ["## Recent decisions (examples of what was valued)"]
            lines += [f"- {e['action'].upper()}: {e['thesis']} | reason: {e['reason']}" for e in ex]
            lines.append("")
        return "\n".join(lines).strip() + "\n"

    def _recent_examples(self, n: int = 5) -> list[dict]:
        out = []
        for action in ("promote", "kill"):
            out += self.q("SELECT d.action, d.reason, i.thesis FROM decisions d JOIN ideas i ON i.id=d.idea_id "
                          "WHERE d.actor='human' AND d.action=? ORDER BY d.id DESC LIMIT ?", (action, n))
        return out

    def get_context(self, role: str) -> dict:
        roles = ("analyst", "registrar", "steward", "redteam", "framer", "inventor", "curator",
                 "arbiter", "herald", "calibrator", "scout", "all")
        self._need(role in roles, f"role must be one of {list(roles)}.")
        return {"role": role, "markdown": self._render(role)}

    def export_context(self):
        out = self.home / "context"
        out.mkdir(parents=True, exist_ok=True)
        (out / "CONTEXT.md").write_text(
            "<!-- Generated from the ledger. Edit through set_config, not here. -->\n" + self._render("all"))

    def get_watchlist(self) -> dict:
        st = self.strategy()
        self._need(st, "No strategy configured yet. Run the gatekeeper-setup interview first.")
        r = self.rules()
        taste = self._config_raw("taste") or {}
        return {
            "areas": {a: t for a, t in st.get("watchlist", {}).items() if t},
            "surface": st.get("surface"),
            "exclusions": st.get("exclusions", []),
            "taste": taste,
            "examples": self._recent_examples(),
            "signals_per_sensor": r["signals_per_sensor"],
            "inbox": str(self.home / "inbox"),
            "hygiene": "Compose search queries only from these terms. Never put directive wording, "
                       "backlog items or internal data into a public query.",
        }

    # ------------------------------------------------------------------ setup interview support

    def add_portfolio_item(self, kind: str, name: str, ambition_cell: str, source: str,
                           description: str | None = None, four_p: str | None = None) -> dict:
        self._need(kind in PORTFOLIO_KINDS, "kind must be line (sold today), in_flight (funded and under way) or "
                                            "future_goal (an area of interest, not yet funded).")
        self._need(ambition_cell in CELLS, f"ambition_cell must be one of {CELLS}.")
        self._need(four_p in (None,) + FOUR_P, f"four_p must be one of {FOUR_P}.")
        name = self._text(name, "name", lo=3, hi=200)
        source = self._text(source, "source", lo=3, hi=300)
        with self.tx() as c:
            row = c.execute("SELECT id FROM portfolio_items ORDER BY id DESC LIMIT 1").fetchone()
            pid = f"PF-{(int(row[0].split('-')[1]) + 1) if row else 1:04d}"
            c.execute("INSERT INTO portfolio_items(id, kind, name, description, ambition_cell, four_p, source, created_at) "
                      "VALUES (?,?,?,?,?,?,?,?)", (pid, kind, name, description, ambition_cell, four_p, source, now_iso()))
            c.execute("INSERT INTO search_fts(ref, kind, body) VALUES (?,?,?)", (pid, "portfolio", f"{name} {description or ''}"))
            self._event(c, None, None, "human", "portfolio_item_added", {"id": pid, "name": name})
        self.export_context()
        return {"id": pid}

    def list_portfolio(self) -> list[dict]:
        return self.q("SELECT * FROM portfolio_items WHERE active=1 ORDER BY id")

    def update_portfolio_item(self, item_id: str, reason: str, ambition_cell: str | None = None, four_p: str | None = None,
                              description: str | None = None) -> dict:
        """Retag a live item in place, so the book can be rebalanced after the interview. The id, and every review that
        names it, stays valid; only the next Steward review sees the new mix."""
        reason = self._text(reason, "reason")
        self._need(ambition_cell is not None or four_p is not None or description is not None,
                   "Give at least one of ambition_cell, four_p or description to change.")
        self._need(ambition_cell is None or ambition_cell in CELLS, f"ambition_cell must be one of {CELLS}.")
        self._need(four_p is None or four_p in FOUR_P, f"four_p must be one of {FOUR_P}.")
        with self.tx() as c:
            row = c.execute("SELECT * FROM portfolio_items WHERE id=? AND active=1", (item_id,)).fetchone()
            self._need(row is not None, f"No active portfolio item {item_id}.")
            want = {"ambition_cell": ambition_cell, "four_p": four_p, "description": description}
            changes = {k: {"from": row[k], "to": v} for k, v in want.items() if v is not None and v != row[k]}
            self._need(bool(changes), f"{item_id} already has those values.")
            for k, ch in changes.items():
                c.execute(f"UPDATE portfolio_items SET {k}=? WHERE id=?", (ch["to"], item_id))
            self._event(c, None, None, "human", "portfolio_item_updated", {"id": item_id, "changes": changes, "reason": reason})
        self.export_context()
        port = self.get_portfolio()
        return {"id": item_id, "changes": changes, "shares": port["shares"], "alarms": port["alarms"], "in_band": port["in_band"]}

    def retire_portfolio_item(self, item_id: str, reason: str) -> dict:
        reason = self._text(reason, "reason")
        with self.tx() as c:
            n = c.execute("UPDATE portfolio_items SET active=0 WHERE id=? AND active=1", (item_id,)).rowcount
            self._need(n == 1, f"No active portfolio item {item_id}.")
            self._event(c, None, None, "human", "portfolio_item_retired", {"id": item_id, "reason": reason})
        self.export_context()
        return {"id": item_id, "active": False}

    def add_exemplar(self, thesis: str, outcome: str, reason: str, ambition_cell: str, four_p: str,
                     description: str | None = None) -> dict:
        """A past idea whose fate you already know. Used to calibrate the panel."""
        self._need(outcome in ("funded", "killed", "regret_killed", "regret_funded"),
                   "outcome must be funded (glad you did), killed, regret_killed (wish you had funded it) "
                   "or regret_funded (funded, but should have said no).")
        self._need(ambition_cell in CELLS and four_p in FOUR_P, "ambition_cell and four_p are required.")
        thesis = self._text(thesis, "thesis", lo=10, hi=400)
        reason = self._text(reason, "reason")
        action = "promote" if outcome in ("funded", "regret_funded") else "kill"
        with self.tx() as c:
            iid = self._next_id(c, "IDEA", "ideas")
            c.execute("INSERT INTO ideas(id, origin, thesis, description, four_p, ambition_cell, stage, exemplar_outcome, "
                      "sponsor, created_at, last_activity_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      (iid, "exemplar", thesis, description, four_p, ambition_cell, "exemplar", outcome, "you", now_iso(), now_iso()))
            c.execute("INSERT INTO decisions(idea_id, action, reason, actor, created_at) VALUES (?,?,?,?,?)",
                      (iid, action, reason, "human", now_iso()))
            self._event(c, iid, None, "human", "exemplar_added", {"outcome": outcome})
        return {"id": iid, "outcome": outcome}

    def mark_calibrated(self, note: str) -> dict:
        note = self._text(note, "note")
        with self.tx() as c:
            c.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('calibrated', ?)",
                      (json.dumps({"at": now_iso(), "note": note}),))
            self._event(c, None, None, "human", "calibrated", {"note": note})
        return {"calibrated": True}

    def get_setup_status(self) -> dict:
        prof = self._config_raw("profile") or {}
        st = self._config_raw("strategy") or {}
        caps = self._config_raw("capabilities") or {}
        lines = self.q1("SELECT COUNT(*) n FROM portfolio_items WHERE kind='line' AND active=1")["n"]
        flight = self.q1("SELECT COUNT(*) n FROM portfolio_items WHERE kind='in_flight' AND active=1")["n"]
        ex = {r["exemplar_outcome"]: r["n"] for r in self.q(
            "SELECT exemplar_outcome, COUNT(*) n FROM ideas WHERE origin='exemplar' GROUP BY exemplar_outcome")}
        weights_set = self.q1("SELECT 1 x FROM config_versions WHERE section='weights' AND actor='human'") is not None
        calibrated = self.q1("SELECT value FROM meta WHERE key='calibrated'")
        steps = [
            ("1_read_public", bool(prof.get("urls")) and bool(prof.get("summary")),
             "Read the public record: profile with URLs and a drafted summary."),
            ("2_confirm", bool(prof.get("confirmed")), "You confirmed or corrected the drafted profile."),
            ("3_what_it_cannot_read", bool([d for d in st.get("directives", []) if not d.get("retired")])
             and bool(st.get("watchlist")) and bool(st.get("surface")),
             "Directives, innovation surface, exclusions and watch list."),
            ("4_private_inputs", lines >= 1 and flight >= 1 and bool(caps.get("capabilities")),
             f"Portfolio lines ({lines}), in-flight work ({flight}) and capabilities. The first two are not optional."),
            ("5_assemble_team", self._config_raw("bench") is not None, "Which agents play and which sit out, with reasons."),
            ("6_set_weights", weights_set, "Four dials, anchored to decisions you have already made."),
            ("7_calibrate", ex.get("funded", 0) >= 1
             and (ex.get("killed", 0) + ex.get("regret_killed", 0) + ex.get("regret_funded", 0)) >= 1
             and sum(ex.values()) >= 3 and calibrated is not None,
             f"Exemplars: funded {ex.get('funded',0)}, killed {ex.get('killed',0)}, regret killed "
             f"{ex.get('regret_killed',0)}, regret funded {ex.get('regret_funded',0)}; need at least 3, including one "
             "you are glad you funded and one that should rank low; "
             "panel run on them and ranking accepted."),
        ]
        out = [{"step": s, "done": d, "what": w} for s, d, w in steps]
        nxt = next((s for s in out if not s["done"]), None)
        return {"steps": out, "complete": nxt is None, "next_step": nxt["step"] if nxt else None,
                "home": str(self.home), "inbox": str(self.home / "inbox")}

    # ------------------------------------------------------------------ runs

    def start_run(self, trigger: str = "scheduled") -> dict:
        self._need(trigger in ("scheduled", "manual", "calibration"), "trigger must be scheduled, manual or calibration.")
        st_body = json.dumps({"s": json.loads(self._scoring_view("strategy", self._config_raw("strategy") or {})),
                              "c": self._config_raw("capabilities")}, sort_keys=True)
        h = hashlib.sha256(st_body.encode()).hexdigest()[:16]
        live = self.q1("SELECT id, started_at FROM runs WHERE status='running' ORDER BY id DESC LIMIT 1")
        if live and (datetime.now(timezone.utc) - datetime.fromisoformat(live["started_at"])) < timedelta(minutes=RUN_GUARD_MINUTES):
            raise Rejected(f"Run {live['id']} started {live['started_at']} and is still in progress. Do not start another: "
                           "stop here and report that a run is already under way. A run that started more than "
                           f"{RUN_GUARD_MINUTES} minutes ago counts as stuck and a new one may replace it.")
        with self.tx() as c:
            stale = c.execute("UPDATE runs SET status='abandoned', finished_at=?, note='superseded by a new run' "
                              "WHERE status='running'", (now_iso(),)).rowcount
            prev = c.execute("SELECT strategy_hash FROM runs WHERE strategy_hash IS NOT NULL ORDER BY id DESC LIMIT 1").fetchone()
            cur = c.execute("INSERT INTO runs(trigger, started_at, status, strategy_hash) VALUES (?,?, 'running', ?)",
                            (trigger, now_iso(), h))
            run_id = cur.lastrowid
            queued = 0
            if prev and prev[0] != h:
                queued = self._queue_rescore(c, "strategy or capabilities changed since the last run")
            defaulted = self._apply_defaults(c, run_id)
            kills = self._kill_triggers(c, run_id)
            self._event(c, None, run_id, "orchestrator", "run_started", {"trigger": trigger})
        return {
            "run_id": run_id,
            "abandoned_previous_runs": stale,
            "rescore_jobs_queued": queued,
            "defaults_executed": defaulted,
            "kill_recommendations_added": kills,
            "setup": self.get_setup_status(),
            "benched": self.benched(),
            "rules": self.rules(),
            "pending_jobs": self.list_jobs("pending"),
        }

    def _apply_defaults(self, c, run_id) -> list[dict]:
        out = []
        due = c.execute("SELECT * FROM queue_items WHERE status='open' AND default_on <= ?", (today().isoformat(),)).fetchall()
        for qi in due:
            qi = dict(qi)
            action = qi["default_action"]
            reason = (f"Default '{action}' executed on {today().isoformat()}: no decision was made by "
                      f"{qi['default_on']}. Recommended was {qi['recommended_action']}.")
            self._record_decision(c, qi["idea_id"], action, reason, "default", run_id)
            c.execute("UPDATE queue_items SET status='defaulted', resolved_at=? WHERE id=?", (now_iso(), qi["id"]))
            out.append({"idea_id": qi["idea_id"], "action": action})
        return out

    def _typical_gap_days(self, c) -> float | None:
        rows = c.execute("SELECT idea_id, at FROM events WHERE idea_id IN (SELECT id FROM ideas WHERE stage='promoted') "
                         "ORDER BY idea_id, at").fetchall()
        gaps, last = [], {}
        for iid, at in rows:
            t = datetime.fromisoformat(at)
            if iid in last:
                g = (t - last[iid]).total_seconds() / 86400
                if g > 0.01:
                    gaps.append(g)
            last[iid] = t
        return D.median_or_none(gaps)

    def stalled(self, c=None) -> list[dict]:
        c = c or self.conn
        r = self.rules()
        typical = self._typical_gap_days(c)
        out = []
        for row in c.execute("SELECT id, thesis, last_activity_at FROM ideas WHERE stage='promoted'").fetchall():
            idle = (datetime.now(timezone.utc) - datetime.fromisoformat(row[2])).total_seconds() / 86400
            ratio = D.stall_ratio(idle, typical, r["stall_days_default"])
            out.append({"idea_id": row[0], "thesis": row[1], "idle_days": round(idle, 1), "ratio": ratio,
                        "stalled": ratio >= r["stall_ratio"]})
        return sorted(out, key=lambda x: -x["ratio"])

    def get_stalled(self) -> list[dict]:
        return self.stalled()

    def _kill_triggers(self, c, run_id) -> int:
        r = self.rules()
        st = self.strategy()
        active_ids = {d["id"] for d in st.get("directives", []) if not d.get("retired")}
        n = 0
        for s in self.stalled(c):
            reasons = []
            if s["stalled"]:
                reasons.append(f"stall: idle {s['idle_days']} days, {s['ratio']}x the typical gap")
            ar = c.execute("SELECT sub FROM reviews WHERE idea_id=? AND role='analyst' ORDER BY id DESC LIMIT 1",
                           (s["idea_id"],)).fetchone()
            if ar:
                did = json.loads(ar[0]).get("directive_id")
                if did and st and did not in active_ids:
                    reasons.append(f"strategic drift: matched directive {did} is retired or gone")
            if not reasons:
                continue
            if c.execute("SELECT 1 FROM queue_items WHERE idea_id=? AND kind='kill' AND status='open'", (s["idea_id"],)).fetchone():
                continue
            c.execute("INSERT INTO queue_items(run_id, idea_id, kind, recommended_action, default_action, default_on, why, "
                      "status, created_at) VALUES (?,?,?,?,?,?,?,'open',?)",
                      (run_id, s["idea_id"], "kill", "KILL", "kill",
                       (today() + timedelta(days=int(r["default_days"]))).isoformat(), "; ".join(reasons), now_iso()))
            self._event(c, s["idea_id"], run_id, "orchestrator", "kill_recommended", {"why": reasons})
            n += 1
        return n

    def finish_run(self, run_id: int, status: str = "done", note: str | None = None) -> dict:
        self._need(status in ("done", "failed"), "status must be done or failed.")
        self._run(run_id)
        counts = {
            "signals": self.q1("SELECT COUNT(*) n FROM signals WHERE run_id=?", (run_id,))["n"],
            "kept": self.q1("SELECT COUNT(*) n FROM signals WHERE run_id=? AND status='kept'", (run_id,))["n"],
            "problems": self.q1("SELECT COUNT(*) n FROM problems WHERE run_id=?", (run_id,))["n"],
            "candidates": self.q1("SELECT COUNT(*) n FROM ideas WHERE run_id=?", (run_id,))["n"],
            "reviews": self.q1("SELECT COUNT(*) n FROM reviews WHERE run_id=?", (run_id,))["n"],
            "objections": self.q1("SELECT COUNT(*) n FROM objections WHERE run_id=?", (run_id,))["n"],
            "rejections": self.q1("SELECT COUNT(*) n FROM rejections WHERE run_id=?", (run_id,))["n"],
            "queued": self.q1("SELECT COUNT(*) n FROM queue_items WHERE run_id=?", (run_id,))["n"],
        }
        with self.tx() as c:
            c.execute("UPDATE runs SET status=?, finished_at=?, note=?, counts=? WHERE id=?",
                      (status, now_iso(), note, json.dumps(counts), run_id))
            # A finished run has no stage still working; close any left open so nothing shows "Working…" forever.
            closing = "failed" if status == "failed" else "skipped"
            open_stages = c.execute(
                "SELECT stage FROM run_stages r WHERE run_id=? AND status='running' "
                "AND id=(SELECT MAX(id) FROM run_stages WHERE run_id=r.run_id AND stage=r.stage)", (run_id,)).fetchall()
            for st in open_stages:
                c.execute("INSERT INTO run_stages(run_id, stage, status, detail, at) VALUES (?,?,?,?,?)",
                          (run_id, st[0], closing, "Closed when the run finished", now_iso()))
            self._event(c, None, run_id, "orchestrator", "run_finished", {"status": status, **counts})
        return {"run_id": run_id, "status": status, "counts": counts}

    # ------------------------------------------------------------------ sensing

    def submit_signal(self, run_id: int, sensor: str, title: str, url: str, retrieved_at: str,
                      excerpt: str, query: str | None = None) -> dict:
        self._run(run_id)
        self._need(sensor in DRUCKER_AREAS, f"sensor must be one of {list(DRUCKER_AREAS)}.")
        self._need(isinstance(url, str) and url.startswith(("http://", "https://", "file://")),
                   "url must be the http(s) address of the page you actually read, or a file:// path to an "
                   "export in inbox/ for internal sensors.")
        if url.startswith("file://"):
            self._need(sensor in INTERNAL_AREAS, f"file:// sources are for internal sensors {list(INTERNAL_AREAS)}.")
            p = Path(re.split(r"[#?]", url[7:])[0]).expanduser().resolve()
            self._need(str(p).startswith(str((self.home / "inbox").resolve())) and p.exists(),
                       "file:// sources must point at an existing file inside the inbox/ folder.")
        retrieved_at = parse_when(retrieved_at, "retrieved_at")
        title = self._text(title, "title", lo=5, hi=300)
        excerpt = self._text(excerpt, "excerpt (the passage that triggered this signal, quoted from the page)", lo=20, hi=1500)
        cap = self.rules()["signals_per_sensor"]
        n = self.q1("SELECT COUNT(*) n FROM signals WHERE run_id=? AND sensor=?", (run_id, sensor))["n"]
        self._need(n < cap, f"Cap reached: {cap} signals for {sensor} in this run. Submit only your strongest.")
        key = url if url.startswith("file://") else url_key(url)   # file://...#row-12 keeps its row anchor
        dup = self.q1("SELECT id FROM signals WHERE url_key=?", (key,))
        self._need(not dup, f"Already in the ledger as {dup['id'] if dup else ''}. Find a different source.")
        with self.tx() as c:
            sid = self._next_id(c, "SIG", "signals")
            c.execute("INSERT INTO signals(id, run_id, sensor, title, url, url_key, retrieved_at, excerpt, query, status, created_at) "
                      "VALUES (?,?,?,?,?,?,?,?,?, 'new', ?)", (sid, run_id, sensor, title, url, key, retrieved_at, excerpt, query, now_iso()))
            c.execute("INSERT INTO search_fts(ref, kind, body) VALUES (?,?,?)", (sid, "signal", f"{title} {excerpt}"))
            self._event(c, None, run_id, f"scout:{sensor}", "signal_submitted", {"id": sid})
        return {"id": sid, "remaining_for_sensor": cap - n - 1}

    def list_new_signals(self, run_id: int | None = None) -> list[dict]:
        if run_id is None:
            return self.q("SELECT id, run_id, sensor, title, url, retrieved_at, excerpt FROM signals WHERE status='new' ORDER BY id")
        return self.q("SELECT id, run_id, sensor, title, url, retrieved_at, excerpt FROM signals WHERE status='new' AND run_id=? ORDER BY id",
                      (run_id,))

    def find_similar(self, text: str, k: int = 5, exclude: str | None = None) -> list[dict]:
        toks = sorted(tokens(text))
        if not toks:
            return []
        match = " OR ".join(f'"{t}"' for t in toks[:40])
        rows = self.q("SELECT ref, kind, body FROM search_fts WHERE search_fts MATCH ? ORDER BY bm25(search_fts) LIMIT 40", (match,))
        out = []
        for r in rows:
            if r["ref"] == exclude:
                continue
            if r["kind"] == "signal":
                st = self.q1("SELECT status FROM signals WHERE id=?", (r["ref"],))
                if st and st["status"] == "dropped":
                    continue
            out.append({"id": r["ref"], "kind": r["kind"], "text": r["body"][:240], "overlap": jaccard(text, r["body"])})
        out.sort(key=lambda x: -x["overlap"])
        return out[:k]

    def curate_signal(self, signal_id: str, keep: bool, reason: str, novelty: float | None = None,
                      four_p: str | None = None, duplicate_override: str | None = None) -> dict:
        sig = self.q1("SELECT * FROM signals WHERE id=?", (signal_id,))
        self._need(sig, f"No signal {signal_id}.")
        self._need(sig["status"] == "new", f"{signal_id} was already curated ({sig['status']}).")
        reason = self._text(reason, "reason")
        if keep:
            floor = self.strategy().get("novelty_floor", 0.35)
            nv = self._unit(novelty, "novelty")
            self._need(nv >= floor, f"Novelty {nv} is below the floor {floor}. Drop it, with a reason.")
            self._need(four_p in FOUR_P, f"four_p must be one of {FOUR_P} when keeping a signal.")
            r = self.rules()
            kept = self.q1("SELECT COUNT(*) n FROM signals WHERE run_id=? AND status='kept'", (sig["run_id"],))["n"]
            self._need(kept < r["kept_per_run"], f"Cap reached: {r['kept_per_run']} kept signals per run. "
                                                  "Keep only the strongest; drop the rest with reasons.")
            kept_ids = {r["id"] for r in self.q("SELECT id FROM signals WHERE status='kept'")}
            sims = [s for s in self.find_similar(f"{sig['title']} {sig['excerpt']}", 10, exclude=signal_id)
                    if s["kind"] == "idea" or s["id"] in kept_ids]
            top = sims[0] if sims else None
            if top and top["overlap"] >= r["duplicate_jaccard"] and not duplicate_override:
                raise Rejected(f"Looks like a duplicate of {top['id']} (overlap {top['overlap']}). Drop it, or pass "
                               "duplicate_override explaining what is genuinely new.")
        with self.tx() as c:
            c.execute("UPDATE signals SET status=?, novelty=?, four_p=?, curator_note=? WHERE id=?",
                      ("kept" if keep else "dropped", novelty if keep else None, four_p, reason, signal_id))
            self._event(c, None, sig["run_id"], "curator", "signal_kept" if keep else "signal_dropped",
                        {"id": signal_id, "reason": reason, "duplicate_override": duplicate_override})
        return {"id": signal_id, "status": "kept" if keep else "dropped"}

    # ------------------------------------------------------------------ framing and inventing

    def get_signal(self, signal_id: str) -> dict:
        s = self.q1("SELECT * FROM signals WHERE id=?", (signal_id,))
        self._need(s, f"No signal {signal_id}.")
        return s

    def frame_problem(self, signal_id: str, statement: str, for_whom: str, why_now: str,
                      alternatives: list[str] | None = None) -> dict:
        s = self.get_signal(signal_id)
        self._need(s["status"] == "kept", f"{signal_id} is {s['status']}; only kept signals are framed.")
        self._need(not self.q1("SELECT id FROM problems WHERE signal_id=?", (signal_id,)),
                   f"{signal_id} already has a framed problem. One problem per signal.")
        statement = self._text(statement, "statement", lo=20, hi=600)
        for_whom = self._text(for_whom, "for_whom", lo=3, hi=300)
        why_now = self._text(why_now, "why_now", lo=10, hi=600)
        with self.tx() as c:
            pid = self._next_id(c, "PRB", "problems")
            c.execute("INSERT INTO problems(id, signal_id, run_id, statement, for_whom, why_now, alternatives, created_at) "
                      "VALUES (?,?,?,?,?,?,?,?)", (pid, signal_id, s["run_id"], statement, for_whom, why_now,
                                                    json.dumps(alternatives or []), now_iso()))
            self._event(c, None, s["run_id"], "framer", "problem_framed", {"id": pid, "signal": signal_id})
        return {"id": pid}

    def list_unframed(self, run_id: int) -> list[dict]:
        return self.q("SELECT s.id, s.title, s.sensor, s.four_p FROM signals s WHERE s.run_id=? AND s.status='kept' "
                      "AND NOT EXISTS (SELECT 1 FROM problems p WHERE p.signal_id=s.id)", (run_id,))

    def get_problem(self, problem_id: str) -> dict:
        p = self.q1("SELECT * FROM problems WHERE id=?", (problem_id,))
        self._need(p, f"No problem {problem_id}.")
        p["alternatives"] = json.loads(p["alternatives"] or "[]")
        p["signal"] = self.q1("SELECT id, title, url, excerpt, four_p FROM signals WHERE id=?", (p["signal_id"],))
        p["candidates_so_far"] = self.q("SELECT id, thesis, technique FROM ideas WHERE problem_id=?", (problem_id,))
        return p

    def _check_claims(self, claims: list[dict] | None) -> list[dict]:
        out = []
        for i, cl in enumerate(claims or []):
            self._need(isinstance(cl, dict), f"claims[{i}] must be an object.")
            kind = cl.get("kind")
            self._need(kind in ("source", "estimate"),
                       f"claims[{i}].kind must be 'source' (with url, retrieved_at, excerpt) or 'estimate' (with confidence, basis).")
            self._text(cl.get("statement"), f"claims[{i}].statement", lo=5, hi=600)
            self._need(isinstance(cl.get("field"), str) and cl["field"].strip(), f"claims[{i}].field names what the claim supports.")
            if kind == "source":
                self._need(str(cl.get("url", "")).startswith(("http://", "https://", "file://")),
                           f"claims[{i}].url is required for a sourced claim.")
                cl["retrieved_at"] = parse_when(str(cl.get("retrieved_at", "")), f"claims[{i}].retrieved_at")
                self._text(cl.get("excerpt"), f"claims[{i}].excerpt", lo=10, hi=1500)
            else:
                self._need(cl.get("confidence") in CONFIDENCE, f"claims[{i}].confidence must be low, medium or high.")
                self._text(cl.get("basis"), f"claims[{i}].basis (how the estimate was reached)", lo=10, hi=600)
            out.append(cl)
        return out

    def _insert_claims(self, c, claims, idea_id=None, signal_id=None, actor="agent") -> list[int]:
        ids = []
        for cl in claims:
            same = c.execute("SELECT id FROM claims WHERE idea_id IS ? AND statement=? AND kind=? AND url IS ?",
                             (idea_id, cl["statement"], cl["kind"], cl.get("url"))).fetchone()
            if same:  # a retry re-sending the same claim
                ids.append(same[0])
                continue
            cur = c.execute("INSERT INTO claims(idea_id, signal_id, field, statement, value, kind, url, retrieved_at, excerpt, "
                            "confidence, basis, created_by, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (idea_id, signal_id, cl["field"], cl["statement"], None if cl.get("value") is None else str(cl["value"]),
                             cl["kind"], cl.get("url"), cl.get("retrieved_at"), cl.get("excerpt"), cl.get("confidence"),
                             cl.get("basis"), actor, now_iso()))
            ids.append(cur.lastrowid)
        return ids

    def _fidelity(self, text: str, claims: list[dict], where: str, extra_backing: str = ""):
        refs = claim_refs(text)
        if refs:
            known = {r["id"] for r in self.q(f"SELECT id FROM claims WHERE id IN ({','.join('?' * len(refs))})", tuple(refs))}
            gone = sorted(refs - known)
            if gone:
                raise Rejected(f"Fidelity rule: {where} cites claim {gone[0]}, which is not in the ledger. "
                               "Cite claim ids returned by get_evidence, or add the claim first.")
        missing = unbacked_numbers(text, claims, extra_backing)
        if missing:
            raise Rejected(f"Fidelity rule: {where} states {', '.join(repr(m) for m in missing[:5])} with no claim behind it. "
                           "Add a claim for each figure (kind 'source' with url, retrieved_at, excerpt; or kind 'estimate' "
                           "with confidence and basis) whose statement, value or excerpt contains it, or remove the figure.")

    def submit_candidate(self, problem_id: str, thesis: str, description: str, technique: str, ambition_cell: str,
                         four_p: str, first_check: dict, claims: list[dict] | None = None, title: str | None = None) -> dict:
        p = self.get_problem(problem_id)
        r = self.rules()
        self._need(len(p["candidates_so_far"]) < r["candidates_per_problem"],
                   f"Cap reached: {r['candidates_per_problem']} candidates for {problem_id}.")
        self._need(technique in TECHNIQUES, f"technique must be one of {list(TECHNIQUES)}.")
        self._need(ambition_cell in CELLS, f"ambition_cell must be one of {CELLS}.")
        self._need(four_p in FOUR_P, f"four_p must be one of {FOUR_P}.")
        thesis = self._text(thesis, "thesis (one sentence: what it is and who it is for)", lo=15, hi=300)
        if title is not None:
            title = self._text(title, "title (a short name, 3 to 8 words, for lists and the web app)", lo=5, hi=90)
        description = self._text(description, "description", lo=30, hi=3000)
        self._need(isinstance(first_check, dict), "first_check is required.")
        for k in ("smallest_commitment", "uncertainty_retired", "what_must_be_true"):
            self._text(first_check.get(k), f"first_check.{k}", lo=10, hi=600)
        claims = self._check_claims(claims)
        self._fidelity(f"{thesis} {description} {json.dumps(first_check)}", claims, "the candidate")
        sims = [s for s in self.find_similar(f"{thesis} {description}", 3) if s["kind"] in ("idea", "portfolio")]
        if sims and sims[0]["overlap"] >= r["duplicate_jaccard"]:
            raise Rejected(f"Too close to {sims[0]['id']} (overlap {sims[0]['overlap']}). Diverge further.")
        sig = p["signal"] or {}
        with self.tx() as c:
            iid = self._next_id(c, "IDEA", "ideas")
            run_id = c.execute("SELECT run_id FROM problems WHERE id=?", (problem_id,)).fetchone()[0]
            c.execute("INSERT INTO ideas(id, problem_id, signal_id, run_id, origin, thesis, description, technique, four_p, "
                      "ambition_cell, first_check, sponsor, stage, created_at, last_activity_at, title) "
                      "VALUES (?,?,?,?, 'pipeline', ?,?,?,?,?,?,?, 'candidate', ?, ?, ?)",
                      (iid, problem_id, sig.get("id"), run_id, thesis, description, technique, four_p, ambition_cell,
                       json.dumps(first_check), f"sensor:{self.get_signal(sig['id'])['sensor']}" if sig else None,
                       now_iso(), now_iso(), title))
            c.execute("INSERT INTO search_fts(ref, kind, body) VALUES (?,?,?)", (iid, "idea", f"{thesis} {description}"))
            self._insert_claims(c, claims, idea_id=iid, actor="inventor")
            self._event(c, iid, run_id, "inventor", "candidate_submitted", {"technique": technique})
        return {"id": iid}

    # ------------------------------------------------------------------ panel

    def _idea_view(self, idea_id: str, blind: bool) -> dict:
        i = self._idea(idea_id)
        i["first_check"] = json.loads(i["first_check"]) if i["first_check"] else None
        out = {k: i[k] for k in ("id", "title", "thesis", "description", "technique", "four_p", "ambition_cell",
                                 "first_check", "stage", "created_at")}
        if not blind:
            out.update({"origin": i["origin"], "sponsor": i["sponsor"], "notes": i["notes"]})
        if i["problem_id"]:
            p = self.q1("SELECT statement, for_whom, why_now FROM problems WHERE id=?", (i["problem_id"],))
            out["problem"] = p
        if i["signal_id"]:
            s = self.q1("SELECT title, url, retrieved_at, excerpt, sensor FROM signals WHERE id=?", (i["signal_id"],))
            if blind:
                s.pop("sensor", None)
            out["signal"] = s
        out["claims"] = self.get_evidence(idea_id)
        return out

    def get_idea(self, idea_id: str) -> dict:
        return self._idea_view(idea_id, blind=False)

    def get_idea_blind(self, idea_id: str) -> dict:
        """For Red Team: no sponsor, no origin, no source sensor, no notes."""
        return self._idea_view(idea_id, blind=True)

    def get_evidence(self, idea_id: str) -> list[dict]:
        return self.q("SELECT id, field, statement, value, kind, url, retrieved_at, excerpt, confidence, basis, created_by "
                      "FROM claims WHERE idea_id=? ORDER BY id", (idea_id,))

    def add_evidence(self, idea_id: str, claims: list[dict], actor: str = "panel") -> dict:
        self._idea(idea_id)
        claims = self._check_claims(claims)
        self._need(claims, "Pass at least one claim.")
        with self.tx() as c:
            ids = self._insert_claims(c, claims, idea_id=idea_id, actor=actor)
            self._event(c, idea_id, None, actor, "evidence_added", {"claim_ids": ids})
        return {"claim_ids": ids}

    def _counts(self) -> dict[str, int]:
        counts = {c: 0 for c in CELLS}
        for r in self.q("SELECT ambition_cell, COUNT(*) n FROM portfolio_items WHERE active=1 AND kind != 'future_goal' GROUP BY ambition_cell"):
            counts[r["ambition_cell"]] += r["n"]
        for r in self.q("SELECT ambition_cell, COUNT(*) n FROM ideas WHERE stage='promoted' GROUP BY ambition_cell"):
            if r["ambition_cell"]:
                counts[r["ambition_cell"]] += r["n"]
        return counts

    def get_portfolio(self, idea_id: str | None = None) -> dict:
        st = self.strategy()
        target = st.get("mix_target", {"core": 0.6, "adjacent": 0.3, "transformational": 0.1, "tolerance": 0.05})
        counts = self._counts()
        shares = D.mix(counts)
        alarms = []
        for cell in CELLS:
            gap = shares[cell] - target.get(cell, 0)
            if sum(counts.values()) and abs(gap) > target.get("tolerance", 0.05):
                alarms.append(f"{cell} at {shares[cell]:.0%} vs target {target.get(cell,0):.0%} "
                              f"({'over' if gap > 0 else 'under'})")
        floor = st.get("exploratory_floor", 0)
        if counts["transformational"] < floor:
            alarms.append(f"exploratory floor: {counts['transformational']} live transformational items, floor is {floor}")
        out = {"counts": counts, "shares": {k: round(v, 3) for k, v in shares.items()}, "target": target,
               "alarms": alarms, "in_band": not alarms, "stalled": [s for s in self.stalled() if s["stalled"]]}
        if idea_id:
            i = self._idea(idea_id)
            if i["ambition_cell"]:
                out["mix_effect_of_this_idea"] = D.mix_delta(counts, target, i["ambition_cell"])
            sims = [s for s in self.find_similar(f"{i['thesis']} {i['description'] or ''}", 8) if s["kind"] == "portfolio"]
            out["possible_overlaps"] = sims[:3]
        return out

    def _reviews(self, idea_id: str) -> list[D.Review]:
        return [D.Review(role=r["role"], round=r["round"], score=r["score"], rationale=r["rationale"], sub=json.loads(r["sub"]))
                for r in self.q("SELECT * FROM reviews WHERE idea_id=? ORDER BY id", (idea_id,))]

    def _objections(self, idea_id: str) -> list[D.Objection]:
        return [D.Objection(severity=o["severity"], status=o["status"], text=o["text"])
                for o in self.q("SELECT * FROM objections WHERE idea_id=? ORDER BY id", (idea_id,))]

    # -- Defect 1: the cap is a count of admissions per run, recorded once --------------------------------

    def _gate_score(self, idea_id: str) -> float:
        """The Analyst's first round-1 review, which is the gate. Frozen: later revisions do not move it."""
        row = self.q1("SELECT score FROM reviews WHERE idea_id=? AND role='analyst' AND round=1 ORDER BY id LIMIT 1", (idea_id,))
        return row["score"] if row else 0.0

    def _admitted(self, run_id: int) -> list[str]:
        return [r["idea_id"] for r in self.q("SELECT idea_id FROM panel_admissions WHERE run_id=? ORDER BY id", (run_id,))]

    def _admit_up_to_cap(self, run_id: int) -> list[str]:
        """Admit the highest gate scores to this run's full panel until the cap is reached. Idempotent."""
        cap = int(self.rules()["panel_per_run"])
        have = set(self._admitted(run_id))
        room = cap - len(have)
        if room <= 0:
            return []
        waiting = sorted((-self._gate_score(r["id"]), r["id"]) for r in self.q("SELECT id FROM ideas WHERE stage='panel'")
                         if r["id"] not in have)
        new = [iid for _, iid in waiting[:room]]
        if new:
            with self.tx() as c:
                for iid in new:
                    c.execute("INSERT OR IGNORE INTO panel_admissions(run_id, idea_id, gate_score, admitted_at) VALUES (?,?,?,?)",
                              (run_id, iid, self._gate_score(iid), now_iso()))
                    self._event(c, iid, run_id, "orchestrator", "panel_admitted", {"gate_score": self._gate_score(iid)})
        return new

    def _require_admission(self, idea_id: str, run_id: int | None):
        """Round-1 full-panel writes need a seat in this run. A caller that never asked for the worklist is admitted
        on its first write, while seats remain; otherwise the idea is held for the next run."""
        rid = run_id or self._current_run_id()
        if rid is None:
            return
        if idea_id in self._admitted(rid):
            return
        cap = int(self.rules()["panel_per_run"])
        if len(self._admitted(rid)) >= cap:
            raise Rejected(f"{idea_id} is not admitted to the panel in run {rid}: the panel takes {cap} ideas per run and "
                           "this one is held for the next run. Work only the ideas in list_panel_work.")
        with self.tx() as c:
            c.execute("INSERT OR IGNORE INTO panel_admissions(run_id, idea_id, gate_score, admitted_at) VALUES (?,?,?,?)",
                      (rid, idea_id, self._gate_score(idea_id), now_iso()))
            self._event(c, idea_id, rid, "orchestrator", "panel_admitted", {"gate_score": self._gate_score(idea_id)})

    def _round1_review(self, idea_id: str, role: str) -> dict | None:
        row = self.q1("SELECT * FROM reviews WHERE idea_id=? AND role=? AND round=1 ORDER BY id DESC LIMIT 1", (idea_id, role))
        if row:
            row["sub"] = json.loads(row["sub"])
        return row

    def _headline(self, sub: dict, headline: str | None):
        """An optional one-sentence summary the web app shows first. The full rationale stays one click away."""
        if headline is not None:
            sub["headline"] = self._text(headline, "headline (one plain sentence, 20 words or fewer)", lo=10, hi=200)

    def _panel_guard(self, idea_id: str, role: str, round: int, revision_reason: str | None, run_id: int | None = None) -> dict:
        i = self._idea(idea_id)
        allowed = ("candidate", "panel", "board", "need_evidence", "promoted", "exemplar") if role == "analyst" \
            else ("panel", "board", "need_evidence", "promoted", "exemplar")
        self._need(i["stage"] in allowed, f"{idea_id} is at stage {i['stage']}; {role} cannot review it now."
                   + (" Analyst must clear it first." if i["stage"] == "candidate" else ""))
        self._need(round in (1, 2), "round must be 1 or 2.")
        if round == 1 and i["stage"] == "panel" and role != "analyst" and not self.q1(
                "SELECT 1 x FROM jobs WHERE kind='rescore' AND idea_id=? AND role=? AND status='pending'", (idea_id, role)):
            self._require_admission(idea_id, run_id)  # a re-score is not a new admission
        if round == 2:
            revs = self._reviews(idea_id)
            ok, why = D.needs_round2(revs, self._objections(idea_id), self.rules())
            self._need(ok, f"No second round for {idea_id}: the panel agrees and no serious objection is open.")
            mine = [r for r in revs if r.role == role]
            self._need(mine and mine[-1].round == 1, f"{role} has no open round-1 review to revise on {idea_id}.")
            self._text(revision_reason, "revision_reason (why you changed, or why you held, after round 2)")
        return i

    def _system_numbers(self, idea_id: str, role: str | None = None) -> str:
        """Numbers the panel was handed by the system: earlier reviews, board entries, portfolio arithmetic."""
        parts = [self.q("SELECT score, sub FROM reviews WHERE idea_id=?", (idea_id,)),
                 self.q("SELECT score, band, dispersion, components FROM board_snapshots WHERE idea_id=?", (idea_id,)),
                 self.q("SELECT severity FROM objections WHERE idea_id=?", (idea_id,)),
                 self.weights(), self.rules()]
        if role in ("steward", "arbiter"):
            parts.append(self.get_portfolio(idea_id))
        return _pct_backing(parts)

    def _file_review(self, idea_id, run_id, role, round, score, sub, rationale, confidence, revision_reason, claims):
        self._need(confidence in CONFIDENCE, "confidence must be low, medium or high.")
        rationale = self._text(rationale, "rationale", lo=30, hi=3000)
        claims = self._check_claims(claims)
        self._fidelity(rationale, self.get_evidence(idea_id) + claims, f"the {role} rationale",
                       self._system_numbers(idea_id, role) + " " + _pct_backing([score, sub]))
        with self.tx() as c:
            if claims:
                self._insert_claims(c, claims, idea_id=idea_id, actor=role)
            cur = c.execute("INSERT INTO reviews(idea_id, run_id, role, round, score, sub, rationale, confidence, "
                            "revision_reason, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                            (idea_id, run_id, role, round, round_(score), json.dumps(sub), rationale, confidence,
                             revision_reason, now_iso()))
            self._event(c, idea_id, run_id, role, f"review_round{round}", {"score": round_(score)})
            rid = cur.lastrowid
            self._mark_rescore_done(c, idea_id, role)
        return rid

    def _mark_rescore_done(self, c, idea_id, role):
        c.execute("UPDATE jobs SET status='done', updated_at=?, note='re-scored' WHERE kind='rescore' AND idea_id=? "
                  "AND role=? AND status='pending'", (now_iso(), idea_id, role))

    def submit_analyst_review(self, idea_id: str, run_id: int | None, strategic_fit: float | None, directive_id: str | None,
                              capability_match: float | None, gaps: list[dict] | None, dependency: dict | None, rationale: str,
                              confidence: str, round: int = 1, revision_reason: str | None = None,
                              claims: list[dict] | None = None, headline: str | None = None) -> dict:
        i = self._panel_guard(idea_id, "analyst", round, revision_reason, run_id)
        if round == 2:
            # Round 2 is a delta: anything left out (or null) keeps its round-1 value.
            prior = (self._round1_review(idea_id, "analyst") or {}).get("sub", {})
            if strategic_fit is None:
                strategic_fit = prior.get("strategic_fit")
            if directive_id is None:
                directive_id = prior.get("directive_id")
            if capability_match is None:
                capability_match = prior.get("capability_filed", prior.get("capability_match"))
            if gaps is None:
                gaps = prior.get("gaps")
            if dependency is None:
                dependency = prior.get("dependency")
        self._need(strategic_fit is not None, "strategic_fit is required (a number between 0 and 1).")
        self._need(capability_match is not None, "capability_match is required (a number between 0 and 1).")
        fit = self._unit(strategic_fit, "strategic_fit")
        cap = filed = self._unit(capability_match, "capability_match")
        st = self.strategy()
        active = {d["id"] for d in st.get("directives", []) if not d.get("retired")}
        if fit > 0:
            self._need(directive_id in active, f"strategic_fit above 0 must cite an active directive id. "
                                                f"Active: {sorted(active) or 'none configured'}. Otherwise score 0.")
        self._need(isinstance(gaps, list), "gaps must be a list (empty if none).")
        no_path = []
        for g in gaps:
            self._need(isinstance(g, dict) and isinstance(g.get("capability"), str) and g.get("acquisition_path") in ACQUISITION,
                       f"Each gap needs capability and acquisition_path in {list(ACQUISITION)}.")
            if g["acquisition_path"] == "none":
                no_path.append(g["capability"])
        capped = bool(no_path) and cap > NO_PATH_CEILING
        if capped:
            cap = NO_PATH_CEILING
        self._need(isinstance(dependency, dict), "dependency must be an object (ours_to_build, crowding, "
                                                  "incumbent_curve, limiting_factor).")
        score = (fit + cap) / 2
        # Defect 2: every review records whether each rule was evaluated, whether it applied and whether it bound,
        # so a rule that never bit still leaves a visible trace.
        constraints = [{"rule": "no_path_gap", "applies": bool(no_path), "binding": capped, "ceiling": NO_PATH_CEILING,
                        "capabilities": no_path}]
        sub = {"strategic_fit": fit, "directive_id": directive_id, "capability_match": cap, "capability_filed": filed,
               "capability_capped": capped, "constraints": constraints, "gaps": gaps, "dependency": dependency}
        self._headline(sub, headline)
        rid = self._file_review(idea_id, run_id, "analyst", round, score, sub, rationale, confidence, revision_reason, claims)
        stage = i["stage"]
        if i["stage"] == "candidate":
            gate = self.rules()["analyst_gate"]
            stage = "parked_auto" if score < gate else "panel"
            with self.tx() as c:
                c.execute("UPDATE ideas SET stage=? WHERE id=?", (stage, idea_id))
                self._event(c, idea_id, run_id, "analyst", "gate_" + ("parked" if stage == "parked_auto" else "passed"),
                            {"score": round_(score), "gate": gate})
        return {"review_id": rid, "score": round_(score), "capability_capped": capped, "constraints": constraints, "stage": stage}

    def submit_registrar_review(self, idea_id: str, run_id: int | None, readiness: dict | None, rationale: str, confidence: str,
                                round: int = 1, revision_reason: str | None = None,
                                claims: list[dict] | None = None, headline: str | None = None) -> dict:
        self._panel_guard(idea_id, "registrar", round, revision_reason, run_id)
        if round == 2:
            # Round 2 is a delta: send only the dimensions you change; the rest keep their round-1 scores and gaps.
            prior = (self._round1_review(idea_id, "registrar") or {}).get("sub", {}).get("readiness", {})
            merged = json.loads(json.dumps(prior))
            for k, v in (readiness or {}).items():
                self._need(k in READINESS_DIMS, f"readiness has an unknown dimension {k!r}. Use {list(READINESS_DIMS)}.")
                merged[k] = v
            readiness = merged
        self._need(isinstance(readiness, dict) and set(readiness) == set(READINESS_DIMS),
                   f"readiness must have exactly these keys: {list(READINESS_DIMS)}.")
        self._need(confidence in CONFIDENCE, "confidence must be low, medium or high.")
        self._text(rationale, "rationale", lo=30, hi=3000)
        for dim in READINESS_DIMS:
            d = readiness[dim]
            self._need(isinstance(d, dict) and d.get("score") in (0, 1, 2, 3), f"readiness.{dim}.score must be 0, 1, 2 or 3.")
            if d["score"] < 3:
                self._text(d.get("gap"), f"readiness.{dim}.gap (what is missing and where it would come from)", lo=10, hi=600)
        claims = self._check_claims(claims)
        if claims:
            self.add_evidence(idea_id, claims, actor="registrar")
            claims = []
        ev = {c["id"]: c for c in self.get_evidence(idea_id)}
        total, worklist = 0, []
        for dim in READINESS_DIMS:
            d = readiness[dim]
            self._need(isinstance(d, dict) and d.get("score") in (0, 1, 2, 3), f"readiness.{dim}.score must be 0, 1, 2 or 3.")
            ids = d.get("claim_ids", []) or []
            for cid in ids:
                self._need(cid in ev, f"readiness.{dim} cites claim {cid}, which is not evidence on {idea_id}.")
            if d["score"] >= 2:
                self._need(ids, f"readiness.{dim} = {d['score']} means evidenced; cite the claim ids that show it. "
                                "Without evidence the most it can be is 1 (asserted).")
            if d["score"] == 3:
                self._need(any(ev[c]["kind"] == "source" for c in ids),
                           f"readiness.{dim} = 3 means validated against reality; it needs a sourced claim, not an estimate.")
            if d["score"] < 3:
                self._text(d.get("gap"), f"readiness.{dim}.gap (what is missing and where it would come from)", lo=10, hi=600)
                worklist.append({"dimension": dim, "score": d["score"], "gap": d["gap"], "owner_hint": d.get("owner_hint")})
            total += d["score"]
        score = total / 18
        sub = {"readiness": readiness, "total": total, "worklist": worklist}
        self._headline(sub, headline)
        rid = self._file_review(idea_id, run_id, "registrar", round, score, sub, rationale, confidence, revision_reason, None)
        return {"review_id": rid, "score": round_(score), "readiness_total": f"{total}/18", "worklist_items": len(worklist)}

    def submit_steward_review(self, idea_id: str, run_id: int | None, score: float | None, cannibalization_risk: float | None,
                              overlaps: list[str] | None, rationale: str, confidence: str, round: int = 1,
                              revision_reason: str | None = None, headline: str | None = None) -> dict:
        i = self._panel_guard(idea_id, "steward", round, revision_reason, run_id)
        if round == 2:
            prior = self._round1_review(idea_id, "steward") or {}
            if score is None:
                score = prior.get("score")
            if cannibalization_risk is None:
                cannibalization_risk = prior.get("sub", {}).get("cannibalization_risk")
            if overlaps is None:
                overlaps = prior.get("sub", {}).get("overlaps")
        self._need(score is not None, "score is required (a number between 0 and 1).")
        self._need(cannibalization_risk is not None, "cannibalization_risk is required (a number between 0 and 1).")
        s = self._unit(score, "score")
        cr = self._unit(cannibalization_risk, "cannibalization_risk")
        known = {p["id"] for p in self.list_portfolio()} | {r["id"] for r in self.q("SELECT id FROM ideas WHERE stage='promoted'")}
        for o in overlaps or []:
            self._need(o in known, f"overlap {o} is not a live portfolio item or promoted idea.")
        port = self.get_portfolio(idea_id)
        sub = {"cannibalization_risk": cr, "overlaps": overlaps or [],
               "mix_effect": port.get("mix_effect_of_this_idea"), "cell": i["ambition_cell"]}
        self._headline(sub, headline)
        rid = self._file_review(idea_id, run_id, "steward", round, s, sub, rationale, confidence, revision_reason, None)
        return {"review_id": rid, "score": round_(s), "mix_effect": sub["mix_effect"]}

    def raise_objection(self, idea_id: str, run_id: int | None, text: str, severity: float, falsifier: str,
                        claims: list[dict] | None = None, headline: str | None = None) -> dict:
        i = self._idea(idea_id)
        self._need(i["stage"] in ("panel", "board", "need_evidence", "promoted", "exemplar"),
                   f"{idea_id} is at stage {i['stage']}; Red Team argues only against ideas in front of the panel.")
        if i["stage"] == "panel":
            self._require_admission(idea_id, run_id)
        text = self._text(text, "text (the strongest case against)", lo=40, hi=2000)
        sev = self._unit(severity, "severity")
        falsifier = self._text(falsifier, "falsifier (what evidence would answer this objection)", lo=15, hi=600)
        if headline is not None:
            headline = self._text(headline, "headline (one plain sentence, 20 words or fewer)", lo=10, hi=200)
        claims = self._check_claims(claims)
        self._fidelity(text, self.get_evidence(idea_id) + claims, "the objection", self._system_numbers(idea_id))
        with self.tx() as c:
            if claims:
                self._insert_claims(c, claims, idea_id=idea_id, actor="redteam")
            # Red Team's latest case against an idea is its current one. Earlier open objections are kept, marked
            # superseded, so a re-argued severity replaces the old band instead of sitting under it.
            prior = [r[0] for r in c.execute("SELECT id FROM objections WHERE idea_id=? AND status='open'", (idea_id,))]
            cur = c.execute("INSERT INTO objections(idea_id, run_id, text, severity, falsifier, status, created_at, updated_at, headline) "
                            "VALUES (?,?,?,?,?, 'open', ?, ?, ?)", (idea_id, run_id, text, sev, falsifier, now_iso(), now_iso(), headline))
            new_id = cur.lastrowid
            for oid in prior:
                c.execute("UPDATE objections SET status='superseded', answer=?, updated_at=? WHERE id=?",
                          (f"Superseded by objection {new_id}.", now_iso(), oid))
            self._event(c, idea_id, run_id, "redteam", "objection_raised", {"severity": sev, "supersedes": prior})
        return {"objection_id": new_id, "superseded": prior}

    def list_panel_work(self, run_id: int | None = None) -> dict:
        """What the panel still owes, in order. The orchestrator works from this list."""
        r = self.rules()
        need = self.required_panel()
        redteam_on = "redteam" not in self.benched()
        analyst_todo = [x["id"] for x in self.q("SELECT id FROM ideas WHERE stage='candidate' ORDER BY id")]
        # Defect 1: admission is recorded per run and ranked on the frozen gate score, so round-2 revisions
        # and the order in which work finishes cannot let a held idea slide in.
        rid = run_id or self._current_run_id()
        panel = [(row["id"], self._gate_score(row["id"]), self._reviews(row["id"]))
                 for row in self.q("SELECT id FROM ideas WHERE stage='panel' ORDER BY id")]
        panel.sort(key=lambda x: (-x[1], x[0]))
        if rid is not None:
            self._admit_up_to_cap(rid)
            seats = set(self._admitted(rid))
        else:  # no run: show who would be admitted, without recording it
            seats = {iid for iid, _, _ in panel[: int(r["panel_per_run"])]}
        admitted = [x for x in panel if x[0] in seats]
        full = []
        for iid, _, revs in admitted:
            have = {x.role for x in revs}
            missing = [x for x in need if x not in have]
            if redteam_on and not self.q1("SELECT 1 x FROM objections WHERE idea_id=?", (iid,)):
                missing.append("redteam")
            if missing:
                full.append({"idea_id": iid, "roles": missing})
        if redteam_on:
            for row in self.q("SELECT id FROM ideas i WHERE stage IN ('board','need_evidence') AND NOT EXISTS "
                              "(SELECT 1 FROM objections o WHERE o.idea_id=i.id) ORDER BY id"):
                full.append({"idea_id": row["id"], "roles": ["redteam"]})
        round2 = []
        for row in self.q("SELECT id FROM ideas WHERE stage IN ('panel','board','exemplar') ORDER BY id"):
            revs = self._reviews(row["id"])
            ok, why = D.needs_round2(revs, self._objections(row["id"]), r)
            if not ok:
                continue
            latest = D.latest_by_role(revs)
            pending = [role for role in need if role in latest and latest[role].round == 1]
            have_all = all(role in latest for role in need)
            if pending and have_all:
                round2.append({"idea_id": row["id"], "roles": pending, "why": why})
        exemplars = []
        for row in self.q("SELECT id FROM ideas WHERE stage='exemplar' ORDER BY id"):
            have = {x.role for x in self._reviews(row["id"])}
            missing = [x for x in need if x not in have]
            if missing:
                exemplars.append({"idea_id": row["id"], "roles": missing})
        rescore = self.q("SELECT id, idea_id, role, payload FROM jobs WHERE kind='rescore' AND status='pending' ORDER BY id")
        evidence = self.q("SELECT id, idea_id, role, payload FROM jobs WHERE kind='need_evidence' AND status='pending' ORDER BY id")
        waiting = len([x for x in panel if x[0] not in seats])
        return {"analyst_gate": analyst_todo, "full_panel": full, "round2": round2, "rescore": rescore,
                "evidence_requests": evidence, "exemplars_unreviewed": exemplars,
                "held_for_next_run": waiting}

    def get_round2_packet(self, idea_id: str, role: str) -> dict:
        self._need(role in D.PANEL_ROLES, f"role must be one of {D.PANEL_ROLES}.")
        revs = self._reviews(idea_id)
        objs = self._objections(idea_id)
        ok, why = D.needs_round2(revs, objs, self.rules())
        self._need(ok, f"No second round for {idea_id}.")
        latest1 = D.latest_by_role(revs, round_only=1)
        self._need(role in latest1, f"{role} has no round-1 review on {idea_id}.")
        others = [x for x in latest1.values() if x.role != role]
        labels = iter("ABCDEFG")
        scores = [x.score for x in latest1.values()]
        r1 = self._round1_review(idea_id, role)
        return {
            "idea": self.get_idea_blind(idea_id),
            "why_round2": why,
            # Defect 4: the whole round-1 review comes back, so a hold reproduces it exactly instead of being re-derived from prose.
            "your_round1": {"score": r1["score"], "rationale": r1["rationale"], "confidence": r1["confidence"], "sub": r1["sub"]},
            "resubmit_template": self._resubmit_template(idea_id, role, r1),
            "other_panelists": [{"panelist": f"Panelist {next(labels)}", "score": x.score, "rationale": x.rationale} for x in others],
            "spread": {"min": min(scores), "max": max(scores), "median": D.median_or_none(scores)},
            "open_objections": [{"text": o.text, "severity": o.severity} for o in objs if o.status == "open"],
            "instructions": "Revise once or hold. Either way, file a round-2 review with revision_reason. "
                            "Do not move toward the median to be agreeable; move only if an argument changed your mind.",
        }

    def _resubmit_template(self, idea_id: str, role: str, r1: dict) -> dict:
        sub = r1["sub"]
        if role == "analyst":
            args = {"idea_id": idea_id, "strategic_fit": sub.get("strategic_fit"), "directive_id": sub.get("directive_id"),
                    "capability_match": sub.get("capability_filed", sub.get("capability_match")), "gaps": sub.get("gaps"),
                    "dependency": sub.get("dependency")}
        elif role == "registrar":
            args = {"idea_id": idea_id, "readiness": sub.get("readiness")}
        else:
            args = {"idea_id": idea_id, "score": r1["score"], "cannibalization_risk": sub.get("cannibalization_risk"),
                    "overlaps": sub.get("overlaps", [])}
        args.update({"round": 2, "rationale": "<your round-2 reasoning>", "confidence": r1["confidence"],
                     "revision_reason": "<why you changed, or why you held>"})
        return {"tool": f"submit_{role}_review", "arguments": args,
                "how_to_use": "Add run_id. Send only the fields you want to change; any field you leave out, or send as null, keeps "
                              "its round-1 value shown here. A hold needs only rationale, confidence and revision_reason."}

    # ------------------------------------------------------------------ resolve

    def _resolve_idea(self, idea_id: str):
        i = self._idea(idea_id)
        return D.resolve(self._reviews(idea_id), self._objections(idea_id), self.weights(), self.rules(),
                         protected=(i["stage"] == "protected"))

    def compute_board(self, run_id: int | None = None) -> dict:
        need = self.required_panel()
        r = self.rules()
        rows, held = [], []
        candidates = self.q("SELECT id, stage, ambition_cell, thesis FROM ideas WHERE stage IN ('panel','board','need_evidence','protected')")
        for i in candidates:
            if i["stage"] != "protected":
                have = {x.role for x in self._reviews(i["id"])}
                missing = [x for x in need if x not in have]
                if missing:
                    held.append({"idea_id": i["id"], "missing": missing})
                    continue
            o = self._resolve_idea(i["id"])
            pending2 = False
            if i["stage"] != "protected":
                ok, _ = D.needs_round2(self._reviews(i["id"]), self._objections(i["id"]), r)
                pending2 = ok and o.rounds_used < 2
                if pending2:
                    o.flags.append("round 2 not yet run")
            rows.append({"idea_id": i["id"], "thesis": i["thesis"], "ambition_cell": i["ambition_cell"], "stage": i["stage"],
                         "score": o.score, "band": o.band, "low": o.low, "high": o.high, "dispersion": o.dispersion,
                         "readiness": o.readiness, "components": o.components, "flags": o.flags, "action": o.action,
                         "rounds": o.rounds_used})
        scored = sorted([x for x in rows if x["score"] is not None], key=lambda x: -x["score"])
        for n, x in enumerate(scored, 1):
            x["rank"] = n
        for x in rows:
            x.setdefault("rank", None)
        changes = {"superseded": [], "added": []}
        with self.tx() as c:
            for x in rows:
                cur = c.execute("INSERT INTO board_snapshots(run_id, idea_id, rank, score, band, dispersion, components, flags, action, created_at) "
                                "VALUES (?,?,?,?,?,?,?,?,?,?)", (run_id, x["idea_id"], x["rank"], x["score"], x["band"], x["dispersion"],
                                                                json.dumps(x["components"]), json.dumps(x["flags"]), x["action"], now_iso()))
                x["snapshot_id"] = cur.lastrowid
                if x["stage"] == "panel":
                    c.execute("UPDATE ideas SET stage='board' WHERE id=?", (x["idea_id"],))
                    self._event(c, x["idea_id"], run_id, "arbiter", "on_board", {"score": x["score"], "action": x["action"]})
            # Defect 5: the queue is a reconciled projection of this board, not a pile of write-once snapshots.
            open_items = [dict(q) for q in c.execute("SELECT id, idea_id, recommended_action, default_action, default_on, why "
                                                     "FROM queue_items WHERE status='open' AND kind='decision' ORDER BY id")]
            plan = D.reconcile_queue(rows, open_items, r, today().isoformat())
            for s in plan["supersede"]:
                c.execute("UPDATE queue_items SET status='superseded', resolved_at=? WHERE id=?", (now_iso(), s["id"]))
                changes["superseded"].append(s)
            for item_id, snap in plan["refresh"]:
                c.execute("UPDATE queue_items SET snapshot_id=? WHERE id=?", (snap, item_id))
            for p in plan["insert"]:
                c.execute("INSERT INTO queue_items(run_id, idea_id, kind, recommended_action, default_action, default_on, why, status, "
                          "created_at, snapshot_id) VALUES (?,?, 'decision', ?,?,?,?, 'open', ?, ?)",
                          (run_id, p["idea_id"], p["action"], p["default_action"], p["default_on"], p["why"], now_iso(), p["snapshot_id"]))
                changes["added"].append({"idea_id": p["idea_id"], "action": p["action"], "forced": p["forced"], "replaces": p["replaces"]})
            if plan["supersede"] or plan["insert"]:
                self._event(c, None, run_id, "arbiter", "queue_reconciled", changes)
        return {"board": rows, "held_back": held, "queue": self.get_queue(), "queue_changes": changes}

    def get_queue(self) -> list[dict]:
        out = self.q("SELECT q.id, q.idea_id, q.kind, q.recommended_action, q.default_action, q.default_on, q.why, q.snapshot_id, i.thesis "
                     "FROM queue_items q JOIN ideas i ON i.id=q.idea_id WHERE q.status='open' ORDER BY q.kind DESC, q.id")
        return out

    def get_reviews(self, idea_id: str) -> dict:
        self._idea(idea_id)
        snap = self.q1("SELECT * FROM board_snapshots WHERE idea_id=? ORDER BY id DESC LIMIT 1", (idea_id,))
        if snap:
            snap["components"], snap["flags"] = json.loads(snap["components"]), json.loads(snap["flags"])
        return {
            "reviews": [{**r, "sub": json.loads(r["sub"])} for r in
                        self.q("SELECT role, round, score, sub, rationale, confidence, revision_reason, created_at "
                               "FROM reviews WHERE idea_id=? ORDER BY id", (idea_id,))],
            "objections": self.q("SELECT id, text, headline, severity, falsifier, status, answer, created_at FROM objections WHERE idea_id=? ORDER BY id", (idea_id,)),
            "latest_board": snap,
            "weights": self.weights(),
        }

    def annotate_rank(self, idea_id: str, run_id: int | None, note: str) -> dict:
        self._idea(idea_id)
        note = self._text(note, "note", lo=20, hi=800)
        self._fidelity(note, self.get_evidence(idea_id), "the rank note", self._system_numbers(idea_id, "arbiter"))
        with self.tx() as c:
            c.execute("INSERT INTO rank_notes(idea_id, run_id, note, created_at) VALUES (?,?,?,?)", (idea_id, run_id, note, now_iso()))
        return {"ok": True}

    # ------------------------------------------------------------------ brief

    def get_brief_data(self, run_id: int) -> dict:
        run = self._run(run_id, require_running=False)
        prev = self.q1("SELECT finished_at FROM runs WHERE id<? AND status='done' ORDER BY id DESC LIMIT 1", (run_id,))
        since = prev["finished_at"] if prev else "1970-01-01"
        ev = self.q("SELECT event, COUNT(*) n FROM events WHERE at > ? GROUP BY event ORDER BY n DESC", (since,))
        new_on_board = self.q(
            "SELECT b.idea_id, i.thesis, i.ambition_cell, i.four_p, b.score, b.band, b.action, b.flags, i.first_check, "
            "(SELECT novelty FROM signals s WHERE s.id=i.signal_id) novelty FROM board_snapshots b JOIN ideas i ON i.id=b.idea_id "
            "WHERE b.run_id=? AND i.run_id=? ORDER BY b.score DESC LIMIT 3", (run_id, run_id))
        for x in new_on_board:
            x["flags"] = json.loads(x["flags"])
            x["first_check"] = json.loads(x["first_check"]) if x["first_check"] else None
            ar = self.q1("SELECT sub FROM reviews WHERE idea_id=? AND role='analyst' ORDER BY id DESC LIMIT 1", (x["idea_id"],))
            x["directive_id"] = json.loads(ar["sub"]).get("directive_id") if ar else None
            x["gaps"] = json.loads(ar["sub"]).get("gaps") if ar else None
        port = self.get_portfolio()
        queue = self.get_queue()
        kills = [q for q in queue if q["kind"] == "kill"]
        watch = [s for s in self.stalled() if not s["stalled"] and s["ratio"] >= 0.66 * self.rules()["stall_ratio"]]
        contested = [x for x in self.q("SELECT idea_id, action FROM board_snapshots WHERE run_id=? AND action='CONTESTED'", (run_id,))]
        defaults = self.q("SELECT idea_id, action, reason FROM decisions WHERE actor='default' AND created_at > ?", (since,))
        quiet = not new_on_board and not kills and port["in_band"] and not defaults and not \
            self.q1("SELECT 1 x FROM queue_items WHERE run_id=?", (run_id,))
        return {"run_id": run_id, "since": since, "events_since": ev, "new_candidates": new_on_board,
                "portfolio": {"shares": port["shares"], "target": port["target"], "alarms": port["alarms"], "in_band": port["in_band"]},
                "queue": queue, "kill_recommendations": kills, "watch": {"approaching_stall": watch, "contested": contested},
                "defaults_executed": defaults, "quiet_day": quiet,
                "format_rules": "Six sections in order: Since yesterday (max 3 lines), New candidates (max 3), Portfolio state "
                                "(one line, say 'in band' explicitly when it is), Decisions waiting on you (each with default "
                                "and date), Kill recommendations (with evidence), Watch list. On a quiet day write at most 5 lines "
                                "saying so. No figures that are not in this data."}

    def write_brief(self, run_id: int, body: str, quiet: bool) -> dict:
        self._run(run_id, require_running=False)
        body = self._text(body, "body", lo=20, hi=12000)
        if quiet:
            self._need(len([l for l in body.splitlines() if l.strip()]) <= 5, "A quiet-day brief is at most 5 lines.")
        d = today().isoformat()
        folder = self.home / "briefs"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{d}.md"
        n = 2
        while path.exists():
            path = folder / f"{d}-{n}.md"
            n += 1
        path.write_text(body if body.endswith("\n") else body + "\n")
        with self.tx() as c:
            c.execute("INSERT INTO briefs(run_id, brief_date, body, quiet, created_at) VALUES (?,?,?,?,?)",
                      (run_id, d, body, int(bool(quiet)), now_iso()))
        return {"path": str(path)}

    def get_brief(self, brief_date: str | None = None) -> dict | None:
        if brief_date:
            return self.q1("SELECT * FROM briefs WHERE brief_date=? ORDER BY id DESC LIMIT 1", (brief_date,))
        return self.q1("SELECT * FROM briefs ORDER BY id DESC LIMIT 1")

    # ------------------------------------------------------------------ your tools

    def get_board(self, cell: str | None = None, four_p: str | None = None, action: str | None = None,
                  min_score: float | None = None, include_promoted: bool = False, limit: int = 25) -> dict:
        stages = ["board", "need_evidence", "protected"] + (["promoted"] if include_promoted else [])
        ideas = self.q(f"SELECT id, thesis, ambition_cell, four_p, stage, signal_id, created_at FROM ideas "
                       f"WHERE stage IN ({','.join('?'*len(stages))})", stages)
        mine = self.q1("SELECT ranking FROM my_rank ORDER BY id DESC LIMIT 1")
        my_pos = {iid: n + 1 for n, iid in enumerate(json.loads(mine["ranking"]))} if mine else {}
        rows = []
        for i in ideas:
            snap = self.q1("SELECT * FROM board_snapshots WHERE idea_id=? ORDER BY id DESC LIMIT 1", (i["id"],))
            if not snap:
                continue
            comps = {c["role"]: c["score"] for c in json.loads(snap["components"])}
            ar = self.q1("SELECT sub FROM reviews WHERE idea_id=? AND role='analyst' ORDER BY id DESC LIMIT 1", (i["id"],))
            asub = json.loads(ar["sub"]) if ar else {}
            nov = self.q1("SELECT novelty FROM signals WHERE id=?", (i["signal_id"],)) if i["signal_id"] else None
            rows.append({"idea_id": i["id"], "thesis": i["thesis"], "cell": i["ambition_cell"], "four_p": i["four_p"],
                         "stage": i["stage"], "novelty": nov["novelty"] if nov else None,
                         "fit": asub.get("strategic_fit"), "capability": asub.get("capability_match"),
                         "readiness": comps.get("registrar"), "score": snap["score"], "band": snap["band"],
                         "action": snap["action"], "flags": json.loads(snap["flags"]), "board_rank": snap["rank"],
                         "my_rank": my_pos.get(i["id"])})
        if cell:
            rows = [r for r in rows if r["cell"] == cell]
        if four_p:
            rows = [r for r in rows if r["four_p"] == four_p]
        if action:
            rows = [r for r in rows if r["action"] == action]
        if min_score is not None:
            rows = [r for r in rows if (r["score"] or 0) >= min_score]
        rows.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0)))
        port = self.get_portfolio()
        week = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        header = {
            "signals_this_week": self.q1("SELECT COUNT(*) n FROM signals WHERE created_at > ?", (week,))["n"],
            "kept_this_week": self.q1("SELECT COUNT(*) n FROM signals WHERE created_at > ? AND status='kept'", (week,))["n"],
            "waiting_on_you": len(self.get_queue()),
            "exploratory_live": port["counts"]["transformational"],
            "exploratory_floor": self.strategy().get("exploratory_floor"),
        }
        return {"header": header, "alarms": port["alarms"], "in_band": port["in_band"], "rows": rows[:limit],
                "queue": self.get_queue()}

    def get_idea_record(self, idea_id: str) -> dict:
        idea = self.get_idea(idea_id)
        rv = self.get_reviews(idea_id)
        snap = rv["latest_board"]
        arithmetic = None
        if snap and snap["score"] is not None:
            parts = " + ".join(f"{c['weight']:.2f} x {c['score']:.2f} ({c['role']})" for c in snap["components"]
                               if c.get("voting", True))
            arithmetic = f"{parts} = {snap['score']:.2f}; band +/- {snap['band']:.2f} from open objections"
            ready = [c for c in snap["components"] if not c.get("voting", True)]
            if ready:
                arithmetic += f"; readiness for the first check {ready[0]['score']:.2f} (gates promote, not in the score)"
        latest = D.latest_by_role(self._reviews(idea_id))
        nxt = {"first_check": idea.get("first_check"),
               "readiness_worklist": latest["registrar"].sub.get("worklist") if "registrar" in latest else None,
               "capability_gaps": latest["analyst"].sub.get("gaps") if "analyst" in latest else None}
        return {
            "idea": idea,
            "deliberation": {"arithmetic": arithmetic, "board": snap, "reviews": rv["reviews"],
                             "notes": self.q("SELECT note, created_at FROM rank_notes WHERE idea_id=? ORDER BY id DESC", (idea_id,))},
            "objections": rv["objections"],
            "evidence": idea["claims"],
            "what_happens_next": nxt,
            "decisions": self.q("SELECT action, reason, actor, created_at FROM decisions WHERE idea_id=? ORDER BY id", (idea_id,)),
            "open_queue_items": self.q("SELECT * FROM queue_items WHERE idea_id=? AND status='open'", (idea_id,)),
        }

    def _record_decision(self, c, idea_id, action, reason, actor, run_id=None, via=None):
        stage_for = {"promote": "promoted", "kill": "killed", "park": "parked", "need_evidence": "need_evidence"}
        c.execute("INSERT INTO decisions(idea_id, action, reason, actor, created_at, via) VALUES (?,?,?,?,?,?)",
                  (idea_id, action, reason, actor, now_iso(), via or ("default" if actor == "default" else None)))
        if action in stage_for:
            c.execute("UPDATE ideas SET stage=? WHERE id=?", (stage_for[action], idea_id))
        if action == "need_evidence":
            c.execute("INSERT INTO jobs(kind, idea_id, role, payload, status, created_at, updated_at) "
                      "VALUES ('need_evidence', ?, 'registrar', ?, 'pending', ?, ?)",
                      (idea_id, json.dumps({"question": reason}), now_iso(), now_iso()))
        self._event(c, idea_id, run_id, actor, f"decision_{action}", {"reason": reason})

    def decide(self, idea_id: str, action: str, reason: str, via: str | None = None) -> dict:
        i = self._idea(idea_id)
        self._need(action in ("promote", "kill", "park", "need_evidence", "keep"),
                   "action must be promote, kill, park, need_evidence or keep.")
        reason = self._text(reason, "reason", lo=10, hi=1000)
        self._need(len(reason.split()) >= 3, "Give a real reason (a short sentence). It is how the system learns what you value.")
        open_kill = self.q1("SELECT id FROM queue_items WHERE idea_id=? AND status='open' AND kind='kill'", (idea_id,))
        if action == "keep":
            self._need(open_kill, "keep answers a kill recommendation; there is none open for this idea.")
        self._need(i["stage"] not in ("exemplar",), "Exemplars are fixed history. Add a new exemplar instead.")
        with self.tx() as c:
            self._record_decision(c, idea_id, action, reason, "human", via=via)
            if action == "keep":
                c.execute("UPDATE ideas SET last_activity_at=? WHERE id=?", (now_iso(), idea_id))
            c.execute("UPDATE queue_items SET status='decided', resolved_at=? WHERE idea_id=? AND status='open'", (now_iso(), idea_id))
        return {"idea_id": idea_id, "action": action, "stage": self._idea(idea_id)["stage"]}

    def set_my_rank(self, idea_ids: list[str], note: str | None = None) -> dict:
        self._need(isinstance(idea_ids, list) and len(idea_ids) >= 2, "Pass at least two idea ids, best first.")
        self._need(len(set(idea_ids)) == len(idea_ids), "Each idea may appear once.")
        for iid in idea_ids:
            st = self._idea(iid)["stage"]
            self._need(st in LIVE_STAGES, f"{iid} is {st}; you can rank only live ideas.")
        board_order = [r["idea_id"] for r in self.get_board(include_promoted=True, limit=500)["rows"] if r["score"] is not None]
        with self.tx() as c:
            c.execute("INSERT INTO my_rank(ranking, note, created_at) VALUES (?,?,?)", (json.dumps(idea_ids), note, now_iso()))
            self._event(c, None, None, "human", "my_rank_set", {"ranking": idea_ids})
        return {"saved": True, "disagreements_with_board": D.rank_disagreements(idea_ids, board_order)}

    def answer_objection(self, objection_id: int, answer: str, status: str) -> dict:
        self._need(status in ("answered", "accepted"),
                   "status: 'answered' (the objection is met) or 'accepted' (it stands and you accept the risk).")
        answer = self._text(answer, "answer")
        o = self.q1("SELECT * FROM objections WHERE id=?", (objection_id,))
        self._need(o, f"No objection {objection_id}.")
        with self.tx() as c:
            c.execute("UPDATE objections SET status=?, answer=?, updated_at=? WHERE id=?", (status, answer, now_iso(), objection_id))
            self._event(c, o["idea_id"], None, "human", "objection_" + status, {"id": objection_id})
        return {"objection_id": objection_id, "status": status}

    def request_evidence(self, idea_id: str, question: str, role: str = "registrar") -> dict:
        self._idea(idea_id)
        self._need(role in ("registrar", "analyst"),
                   "role must be registrar (readiness evidence) or analyst (fit, capability, competition).")
        question = self._text(question, "question")
        with self.tx() as c:
            cur = c.execute("INSERT INTO jobs(kind, idea_id, role, payload, status, created_at, updated_at) "
                            "VALUES ('need_evidence', ?,?,?, 'pending', ?, ?)",
                            (idea_id, role, json.dumps({"question": question}), now_iso(), now_iso()))
            self._event(c, idea_id, None, "human", "evidence_requested", {"question": question, "role": role})
        return {"job_id": cur.lastrowid}

    def submit_my_idea(self, thesis: str, description: str, ambition_cell: str, four_p: str, note: str | None = None) -> dict:
        """The protected channel: your own reframes go straight to the board, unscored."""
        self._need(ambition_cell in CELLS and four_p in FOUR_P, "ambition_cell and four_p are required.")
        thesis = self._text(thesis, "thesis", lo=10, hi=400)
        with self.tx() as c:
            iid = self._next_id(c, "IDEA", "ideas")
            c.execute("INSERT INTO ideas(id, origin, thesis, description, four_p, ambition_cell, sponsor, notes, stage, "
                      "created_at, last_activity_at) VALUES (?, 'human', ?,?,?,?, 'you', ?, 'protected', ?, ?)",
                      (iid, thesis, description, four_p, ambition_cell, note, now_iso(), now_iso()))
            c.execute("INSERT INTO search_fts(ref, kind, body) VALUES (?,?,?)", (iid, "idea", f"{thesis} {description or ''}"))
            self._event(c, iid, None, "human", "protected_idea_added", {})
        return {"id": iid, "stage": "protected"}

    def list_jobs(self, status: str = "pending") -> list[dict]:
        return self.q("SELECT * FROM jobs WHERE status=? ORDER BY id", (status,))

    def update_job(self, job_id: int, status: str, note: str) -> dict:
        self._need(status in ("running", "done", "failed"), "status must be running, done or failed.")
        note = self._text(note, "note", lo=5, hi=1000)
        job = self.q1("SELECT * FROM jobs WHERE id=?", (job_id,))
        self._need(job, f"No job {job_id}.")
        with self.tx() as c:
            c.execute("UPDATE jobs SET status=?, note=?, updated_at=? WHERE id=?", (status, note, now_iso(), job_id))
            if status == "done" and job["kind"] == "need_evidence" and job["idea_id"]:
                st = c.execute("SELECT stage FROM ideas WHERE id=?", (job["idea_id"],)).fetchone()
                if st and st[0] == "need_evidence":
                    # Evidence gathered: back on the board so it re-enters your queue.
                    c.execute("UPDATE ideas SET stage='board' WHERE id=?", (job["idea_id"],))
                self._event(c, job["idea_id"], None, "orchestrator", "evidence_job_done", {"job": job_id, "note": note})
        return {"job_id": job_id, "status": status}

    RUN_STAGES = ("scout", "curate", "frame", "invent", "gate", "panel", "round2", "resolve", "brief", "calibrate")

    def update_run_stage(self, run_id: int, stage: str, status: str, detail: str | None = None) -> dict:
        """The orchestrator reports progress so the web app can show a live run banner. Pure bookkeeping."""
        self._run(run_id, require_running=False)
        self._need(stage in self.RUN_STAGES, f"stage must be one of {list(self.RUN_STAGES)}.")
        self._need(status in ("running", "done", "failed", "skipped"), "status must be running, done, failed or skipped.")
        if detail is not None:
            detail = self._text(detail, "detail", lo=3, hi=300)
        with self.tx() as c:
            c.execute("INSERT INTO run_stages(run_id, stage, status, detail, at) VALUES (?,?,?,?,?)", (run_id, stage, status, detail, now_iso()))
            self._event(c, None, run_id, "orchestrator", "run_stage", {"stage": stage, "status": status, "detail": detail})
        return {"ok": True}

    def get_pipeline_status(self) -> dict:
        stages = {r["stage"]: r["n"] for r in self.q("SELECT stage, COUNT(*) n FROM ideas GROUP BY stage")}
        runs = self.q("SELECT id, trigger, started_at, finished_at, status, counts, note FROM runs ORDER BY id DESC LIMIT 7")
        for r in runs:
            r["counts"] = json.loads(r["counts"]) if r["counts"] else None
        return {
            "runs": runs,
            "pending_jobs": self.list_jobs("pending"),
            "recent_rejections": self.q("SELECT run_id, tool, reason, created_at FROM rejections ORDER BY id DESC LIMIT 20"),
            "rejections_by_tool_7d": self.q("SELECT tool, COUNT(*) n FROM rejections WHERE created_at > ? GROUP BY tool ORDER BY n DESC",
                                            ((datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),)),
            "ideas_by_stage": stages,
            "queue": self.get_queue(),
            "setup": self.get_setup_status(),
        }

    # ------------------------------------------------------------------ calibration

    def calibration_report(self) -> dict:
        items, unscored = [], []
        need = self.required_panel()
        for e in self.q("SELECT id, thesis, exemplar_outcome FROM ideas WHERE origin='exemplar'"):
            have = {x.role for x in self._reviews(e["id"])}
            if any(r not in have for r in need):
                unscored.append(e["id"])
                continue
            o = D.resolve(self._reviews(e["id"]), self._objections(e["id"]), self.weights(), self.rules())
            items.append({"idea_id": e["id"], "thesis": e["thesis"], "outcome": e["exemplar_outcome"], "score": o.score,
                          "components": o.components})
        items.sort(key=lambda x: -(x["score"] or 0))
        return {"exemplars_ranked": items, "not_yet_reviewed": unscored, "agreement": D.pairwise_agreement(items),
                "weights": self.weights(),
                "reading": "Agreement is the share of pairs with different real outcomes that the panel ordered correctly. "
                           "If it contradicts your judgement, the weights are wrong, not your judgement."}

    def what_if_weights(self, weights: dict) -> dict:
        """Preview: re-resolve exemplars and the live board under other weights. Changes nothing."""
        w = self._validate_section("weights", dict(weights))
        def ranked(ids):
            out = []
            for iid in ids:
                o = D.resolve(self._reviews(iid), self._objections(iid), w, self.rules())
                out.append({"idea_id": iid, "score": o.score})
            return sorted(out, key=lambda x: -(x["score"] or 0))
        need = self.required_panel()
        def complete(iid):
            have = {x.role for x in self._reviews(iid)}
            return all(r in have for r in need)
        ex = [e["id"] for e in self.q("SELECT id FROM ideas WHERE origin='exemplar'") if complete(e["id"])]
        live = [e["id"] for e in self.q("SELECT id FROM ideas WHERE stage IN ('board','need_evidence','promoted')") if complete(e["id"])]
        exr = ranked(ex)
        outcomes = {e["id"]: e["exemplar_outcome"] for e in self.q("SELECT id, exemplar_outcome FROM ideas WHERE origin='exemplar'")}
        agree = D.pairwise_agreement([{**x, "outcome": outcomes[x["idea_id"]]} for x in exr])
        return {"weights": w, "exemplars": exr, "exemplar_agreement": agree, "live_board": ranked(live)}

    def get_decisions(self, days: int = 30) -> dict:
        since = (datetime.now(timezone.utc) - timedelta(days=int(days))).isoformat()
        ds = self.q("SELECT d.idea_id, d.action, d.reason, d.actor, d.created_at, i.thesis, i.ambition_cell, i.four_p "
                    "FROM decisions d JOIN ideas i ON i.id=d.idea_id WHERE d.created_at > ? AND i.origin != 'exemplar' "
                    "ORDER BY d.id", (since,))
        for d in ds:
            s = self.q1("SELECT score, action, components FROM board_snapshots WHERE idea_id=? AND created_at <= ? "
                        "ORDER BY id DESC LIMIT 1", (d["idea_id"], d["created_at"]))
            d["board_at_decision"] = {"score": s["score"], "recommended": s["action"],
                                      "components": json.loads(s["components"])} if s else None
        mine = self.q1("SELECT ranking FROM my_rank ORDER BY id DESC LIMIT 1")
        board_order = [r["idea_id"] for r in self.get_board(include_promoted=True, limit=500)["rows"] if r["score"] is not None]
        return {"decisions": ds,
                "rank_disagreements": D.rank_disagreements(json.loads(mine["ranking"]), board_order) if mine else [],
                "weights": self.weights(), "taste": self._config_raw("taste") or {}}

    def propose_calibration(self, kind: str, body: dict, rationale: str) -> dict:
        self._need(kind in ("weights", "taste", "rules"), "kind must be weights, taste or rules.")
        rationale = self._text(rationale, "rationale", lo=30, hi=3000)
        self._validate_section(kind, json.loads(json.dumps(body)))
        if kind == "taste":
            known = {r["idea_id"] for r in self.q("SELECT idea_id FROM decisions WHERE actor='human'")}
            for k in ("likes", "dislikes"):
                for t in body.get(k, []):
                    self._need(t.get("supported_by"), f"Every proposed taste line needs supported_by: the idea ids whose "
                                                      f"decisions show it. Missing on: {t.get('text')!r}")
                    bad = [x for x in t["supported_by"] if x not in known]
                    self._need(not bad, f"supported_by cites ideas you never decided on: {bad}.")
        with self.tx() as c:
            cur = c.execute("INSERT INTO calibration_proposals(kind, body, rationale, status, created_at) VALUES (?,?,?, 'open', ?)",
                            (kind, json.dumps(body), rationale, now_iso()))
        return {"proposal_id": cur.lastrowid}

    def list_proposals(self, status: str = "open") -> list[dict]:
        out = self.q("SELECT * FROM calibration_proposals WHERE status=? ORDER BY id", (status,))
        for p in out:
            p["body"] = json.loads(p["body"])
        return out

    def decide_proposal(self, proposal_id: int, accept: bool, reason: str) -> dict:
        p = self.q1("SELECT * FROM calibration_proposals WHERE id=?", (proposal_id,))
        self._need(p and p["status"] == "open", f"No open proposal {proposal_id}.")
        reason = self._text(reason, "reason")
        applied = None
        if accept:
            applied = self.set_config(p["kind"], json.loads(p["body"]), f"Calibration proposal {proposal_id}: {reason}",
                                      actor="human")
        with self.tx() as c:
            c.execute("UPDATE calibration_proposals SET status=?, decided_reason=?, decided_at=? WHERE id=?",
                      ("accepted" if accept else "rejected", reason, now_iso(), proposal_id))
        return {"proposal_id": proposal_id, "accepted": bool(accept), "applied": applied}


def round_(x: float) -> float:
    return round(float(x), 4)
