"""The engineering backlog, as a small searchable index the pipeline can ask about one idea at a time.

An Azure DevOps snapshot (a SQLite file written by the person's own sync) is loaded here at Epic and Feature level only.
Search is plain full text in code, so it costs no tokens, and it returns a handful of rows or nothing. The Cartographer
agent judges those rows and files a check; the panel reads the check through the ordinary evidence tools.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

TOP_LEVEL = ("Epic", "Feature")
CLOSED = ("closed", "done", "removed")
VERDICTS = ("done", "in_flight", "pull_forward", "related", "unrelated")
STALE_DAYS = 14

# Words that appear in nearly every idea and every ticket, so they match everything and mean nothing.
GENERIC = set("""report reports customer customers existing run running without within across between through whole every
repeat end real only model package module unit units site sites public history time rate team request requests partner
partners partnership partnerships study baseline sample score data new old live based using build built make made help
helps let lets give gives plus bid rfp rfps contract contracts lease prime""".split())
STOP = set("""the and for with that this from into over under about their there they them then than were been being have has had
are was not but you your our ours its can could would should will shall may might must also more most less such each per
via use used which who whom what when where why how all any some one two within a an of to in on by as at is be or it""".split())

# Company vocabulary, kept out of the code: the person's own file at <home>/backlog_vocabulary.json, for example
#   {"aliases": {"abc": ["alpha", "beta"]},   code or acronym -> the words the board uses for it
#    "specific": ["lidar"],                    one of these alone is enough to surface a ticket
#    "generic": ["widget"],                    extra words that match everything in this business
#    "exclude": ["internal-tooling"]}          tickets whose title, tags or area contain one of these are not product work
ALIASES: dict[str, list[str]] = {}
SPECIFIC: set[str] = set()   # compared as stems; see _SPECIFIC_STEMS
EXCLUDE: tuple[str, ...] = ()
_BASE_GENERIC = frozenset(GENERIC)


def _words(text: str) -> list[str]:
    out: list[str] = []
    for w in re.findall(r"[a-z0-9]+", (text or "").lower()):
        if len(w) < 3 or w in STOP or w in GENERIC:
            continue
        for x in ALIASES.get(w, [w]):
            if x not in out:
                out.append(x)
    return out


def _stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


_SPECIFIC_STEMS: set[str] = set()


def apply_vocabulary(home) -> None:
    """Load the person's own vocabulary (see above) over the generic defaults. Called before every load and search."""
    global ALIASES, SPECIFIC, EXCLUDE, GENERIC, _SPECIFIC_STEMS
    v: dict = {}
    f = Path(home) / "backlog_vocabulary.json"
    if f.is_file():
        try:
            v = json.loads(f.read_text()) or {}
        except (OSError, ValueError):
            v = {}
    ALIASES = {str(k).lower(): [str(x).lower() for x in w] for k, w in (v.get("aliases") or {}).items()}
    SPECIFIC = {str(x).lower() for x in v.get("specific") or []}
    EXCLUDE = tuple(str(x).lower() for x in v.get("exclude") or [])
    GENERIC = set(_BASE_GENERIC) | {str(x).lower() for x in v.get("generic") or []}
    _SPECIFIC_STEMS = {_stem(w) for w in SPECIFIC}


def _iso(ts: str | None) -> str | None:
    return ts[:10] if ts else None


def _days_since(ts: str | None) -> int | None:
    if not ts:
        return None
    try:
        d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - d).days)


class BacklogMixin:
    """Mixed into Gatekeeper. Needs q, q1, tx, _event, _idea, _need, _text, _check_claims, _insert_claims."""

    # -- loading ----------------------------------------------------------------------------------------

    def _backlog_source(self, source: str | None) -> Path:
        from .core import Rejected
        raw = source or os.environ.get("GATEKEEPER_ADO_DB")
        if not raw:
            raise Rejected("No engineering backlog is connected. Pass the path of your ADO snapshot as source, or set GATEKEEPER_ADO_DB.")
        path = Path(os.path.expanduser(raw))
        if not path.is_file():
            raise Rejected(f"No ADO snapshot at {path}. Run the ADO sync first, or pass source or set GATEKEEPER_ADO_DB.")
        return path

    def sync_backlog(self, source: str | None = None) -> dict:
        """Load Epics and Features, with a rollup of their children, from the ADO snapshot. Replaces the previous load."""
        from .core import Rejected, now_iso
        apply_vocabulary(self.home)
        path = self._backlog_source(source)
        src = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        src.row_factory = sqlite3.Row
        try:
            cols = {r[1] for r in src.execute("PRAGMA table_info(work_items)")}
            need = {"id", "title", "work_item_type", "state", "parent_id"}
            if not need <= cols:
                raise Rejected(f"{path.name} has no usable work_items table (missing {sorted(need - cols)}).")
            pick = lambda c: c if c in cols else f"NULL AS {c}"  # noqa: E731  snapshots differ in which columns they carry
            orphan = "WHERE COALESCE(is_orphaned,0)=0" if "is_orphaned" in cols else ""
            rows = [dict(r) for r in src.execute(
                f"SELECT id, title, work_item_type, state, parent_id, {pick('tags')}, {pick('area_path')}, "
                f"{pick('changed_date')}, {pick('closed_date')}, {pick('started_at')} FROM work_items {orphan}")]
        finally:
            src.close()
        items = {r["id"]: r for r in rows}

        def excluded(r) -> bool:
            blob = f"{r['title']} {r.get('tags') or ''} {r.get('area_path') or ''}".lower()
            return any(x in blob for x in EXCLUDE)

        def top_of(i):
            for _ in range(8):
                r = items.get(i)
                if not r:
                    return None
                if r["work_item_type"] in TOP_LEVEL:
                    return r["id"]
                i = r["parent_id"]
            return None

        roll: dict[int, dict] = {}
        for r in rows:
            t = top_of(r["parent_id"])
            if t is None:
                continue
            k = roll.setdefault(t, {"total": 0, "done": 0, "active": 0, "open": 0, "last": None})
            k["total"] += 1
            st = (r["state"] or "").lower()
            if st in CLOSED:
                k["done"] += 1 if r.get("started_at") or r["work_item_type"] in TOP_LEVEL else 0
            elif r.get("started_at") or st in ("active", "doing", "resolved"):
                k["active"] += 1
            else:
                k["open"] += 1
            if r.get("changed_date") and (k["last"] is None or r["changed_date"] > k["last"]):
                k["last"] = r["changed_date"]

        out = []
        for r in rows:
            if r["work_item_type"] not in TOP_LEVEL or excluded(r):
                continue
            k = roll.get(r["id"], {"total": 0, "done": 0, "active": 0, "open": 0, "last": None})
            st = (r["state"] or "").lower()
            if st in CLOSED:
                bucket = "done" if (r.get("started_at") or k["done"]) and st != "removed" else "closed_unstarted"
            elif st in ("active", "doing", "resolved") or r.get("started_at") or k["active"]:
                bucket = "in_flight"
            else:
                bucket = "not_started"
            parent = items.get(r["parent_id"]) if r["parent_id"] else None
            out.append((r["id"], r["work_item_type"], r["title"], r["state"], bucket, r.get("tags") or "",
                        r.get("area_path") or "", r["parent_id"], parent["title"] if parent else None,
                        r.get("changed_date"), r.get("closed_date"), k["total"], k["done"], k["active"], k["open"], k["last"]))
        synced = now_iso()
        with self.tx() as c:
            c.execute("DELETE FROM backlog_items")
            c.execute("DELETE FROM backlog_fts")
            c.executemany("INSERT INTO backlog_items(id, kind, title, state, bucket, tags, area_path, parent_id, parent_title, "
                          "changed_at, closed_at, child_total, child_done, child_active, child_open, child_last_change) "
                          "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", out)
            c.executemany("INSERT INTO backlog_fts(ref, body) VALUES (?,?)",
                          [(str(o[0]), f"{o[2]} {o[5]} {o[8] or ''}") for o in out])
            for k_, v in (("synced_at", synced), ("source", str(path)), ("source_modified",
                          datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"))):
                c.execute("INSERT INTO backlog_meta(key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k_, v))
        buckets = {}
        for o in out:
            buckets[o[4]] = buckets.get(o[4], 0) + 1
        return {"loaded": len(out), "buckets": buckets, "source": str(path), "synced_at": synced,
                "source_modified": _iso(datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat())}

    def _backlog_meta(self) -> dict:
        return {r["key"]: r["value"] for r in self.q("SELECT key, value FROM backlog_meta")}

    # -- searching --------------------------------------------------------------------------------------

    def find_backlog_matches(self, idea_id: str, extra_terms: list[str] | None = None, k: int = 6) -> dict:
        """Epics and Features that may overlap one idea. Returns an empty list when nothing matches well."""
        apply_vocabulary(self.home)
        idea = self._idea(idea_id)
        meta = self._backlog_meta()
        if not meta.get("synced_at"):
            return {"synced": False, "matches": [], "note": "The backlog has not been loaded. Ask the person to run sync_backlog."}
        text = " ".join(filter(None, [idea.get("title"), idea["thesis"], idea.get("description")]))
        terms = _words(text)[:16]
        for t in extra_terms or []:
            terms += [w for w in _words(t) if w not in terms]
        terms = terms[:24]
        stems = {_stem(t) for t in terms}
        total = self.q1("SELECT COUNT(*) n FROM backlog_items")["n"]
        matches = []
        if stems:
            fts = " OR ".join(f'"{t}"' for t in terms)
            rows = self.q("SELECT f.ref, b.* FROM backlog_fts f JOIN backlog_items b ON b.id = CAST(f.ref AS INTEGER) "
                          "WHERE backlog_fts MATCH ? ORDER BY bm25(backlog_fts) LIMIT 80", (fts,))
            for r in rows:
                body = {_stem(w) for w in re.findall(r"[a-z0-9]+", f"{r['title']} {r['tags']} {r['parent_title'] or ''}".lower())}
                hit = sorted(stems & body)
                if len(hit) >= 2 or (hit and hit[0] in _SPECIFIC_STEMS):
                    matches.append((len(hit) + 1.5 * len(_SPECIFIC_STEMS & set(hit)), r, hit))
            matches.sort(key=lambda m: -m[0])
        base = os.environ.get("GATEKEEPER_ADO_URL")
        out = []
        for _, r, hit in matches[: max(1, min(k, 10))]:
            out.append({
                "id": r["id"], "kind": r["kind"], "title": r["title"], "bucket": r["bucket"], "state": r["state"],
                "tags": r["tags"] or None, "area": r["area_path"] or None, "parent": r["parent_title"],
                "idle_days": _days_since(r["child_last_change"] or r["changed_at"]),
                "children": {"total": r["child_total"], "done": r["child_done"], "active": r["child_active"], "open": r["child_open"]},
                "matched": hit,
                "url": f"{base.rstrip('/')}/{r['id']}" if base else f"file://{meta.get('source', '')}#workitem-{r['id']}",
            })
        prior = self.q1("SELECT id, synced_at FROM backlog_checks WHERE idea_id=? ORDER BY id DESC LIMIT 1", (idea_id,))
        age = _days_since(meta["synced_at"])
        res = {"synced": True, "synced_at": meta["synced_at"], "source_modified": meta.get("source_modified"),
               "searched": total, "terms": terms, "matches": out,
               "existing_check": prior["id"] if prior and prior["synced_at"] == meta["synced_at"] else None}
        if _days_since(meta.get("source_modified")) is not None and _days_since(meta["source_modified"]) > STALE_DAYS:
            res["stale"] = (f"The ADO snapshot was last written {_days_since(meta['source_modified'])} days ago, so 'in flight' and "
                            "'done' may be out of date. Say so in the headline.")
        elif age is not None and age > STALE_DAYS:
            res["stale"] = f"The backlog was loaded {age} days ago."
        return res

    # -- the Cartographer's filing ----------------------------------------------------------------------

    def submit_backlog_check(self, idea_id: str, headline: str, verdicts: list[dict], terms_used: list[str] | None = None,
                             run_id: int | None = None, actor: str = "cartographer") -> dict:
        """File the backlog check for one idea: a headline and one verdict per backlog item judged. Matches that are not
        'unrelated' are also recorded as sourced claims, so every panelist sees them through get_evidence."""
        from .core import now_iso
        self._idea(idea_id)
        meta = self._backlog_meta()
        self._need(meta.get("synced_at"), "The backlog has not been loaded. Ask the person to run sync_backlog.")
        headline = self._text(headline, "headline", lo=10, hi=240)
        self._need(isinstance(verdicts, list), "verdicts must be a list (empty when nothing matched).")
        base = os.environ.get("GATEKEEPER_ADO_URL")
        claims, seen, clean = [], set(), []
        for i, v in enumerate(verdicts):
            self._need(isinstance(v, dict), f"verdicts[{i}] must be an object.")
            vd = v.get("verdict")
            self._need(vd in VERDICTS, f"verdicts[{i}].verdict must be one of {', '.join(VERDICTS)}.")
            item = self.q1("SELECT * FROM backlog_items WHERE id=?", (v.get("item_id"),))
            self._need(item, f"verdicts[{i}].item_id {v.get('item_id')} is not in the loaded backlog. Use ids from find_backlog_matches.")
            self._need(item["id"] not in seen, f"verdicts[{i}]: item {item['id']} appears twice.")
            seen.add(item["id"])
            reason = self._text(v.get("reason"), f"verdicts[{i}].reason", lo=10, hi=300)
            clean.append({"item_id": item["id"], "verdict": vd, "reason": reason})
            if vd != "unrelated":
                ch = (f"{item['child_done']} of {item['child_total']} child items done, {item['child_active']} active"
                      if item["child_total"] else "no child items")
                claims.append({
                    "kind": "source", "field": "backlog", "value": vd,
                    "statement": f"Backlog {item['kind']} {item['id']} '{item['title']}' is {item['state']} ({vd.replace('_', ' ')}): {reason}",
                    "url": f"{base.rstrip('/')}/{item['id']}" if base else f"file://{meta.get('source', '')}#workitem-{item['id']}",
                    "retrieved_at": meta["synced_at"][:10],
                    "excerpt": f"{item['kind']} {item['id']}: {item['title']} | state {item['state']} | {ch}"})
        claims = self._check_claims(claims)
        with self.tx() as c:
            ids = self._insert_claims(c, claims, idea_id=idea_id, actor=actor)
            cur = c.execute("INSERT INTO backlog_checks(idea_id, run_id, synced_at, headline, terms, verdicts, claim_ids, created_by, created_at) "
                            "VALUES (?,?,?,?,?,?,?,?,?)",
                            (idea_id, run_id, meta["synced_at"], headline, json.dumps(terms_used or []), json.dumps(clean),
                             json.dumps(ids), actor, now_iso()))
            self._event(c, idea_id, run_id, actor, "backlog_checked", {"check_id": cur.lastrowid, "claim_ids": ids,
                                                                      "verdicts": len(clean)})
        return {"check_id": cur.lastrowid, "claim_ids": ids}

    def get_backlog_check(self, idea_id: str) -> dict | None:
        """The latest backlog check for an idea, with each judged item's current state."""
        self._idea(idea_id)
        r = self.q1("SELECT * FROM backlog_checks WHERE idea_id=? ORDER BY id DESC LIMIT 1", (idea_id,))
        if not r:
            return None
        verdicts = json.loads(r["verdicts"])
        for v in verdicts:
            it = self.q1("SELECT kind, title, state, bucket FROM backlog_items WHERE id=?", (v["item_id"],))
            if it:
                v.update(it)
        meta = self._backlog_meta()
        return {"check_id": r["id"], "headline": r["headline"], "terms_used": json.loads(r["terms"]), "verdicts": verdicts,
                "claim_ids": json.loads(r["claim_ids"]), "backlog_as_of": r["synced_at"], "by": r["created_by"],
                "filed_at": r["created_at"], "current": r["synced_at"] == meta.get("synced_at")}
