"""The service: web API, live stream and both MCP surfaces in one process, over one ledger.

Reads come from views.py. Writes go through the same command registry the MCP tools use, so the web app
and Claude enforce identical rules. Nothing here decides anything: it authenticates, shapes and relays.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from . import team as T
from . import views as V
from .auth import SESSION_DAYS, Auth
from .core import Gatekeeper, Rejected
from .mcp_adapter import build_mcp
from .registry import build_registry, invoke

COOKIE = "gk_session"


# ----------------------------------------------------------------------------- request bodies

class DecisionIn(BaseModel):
    action: Literal["promote", "kill", "park", "need_evidence", "keep"]
    reason: str = Field(min_length=1)
    seen_snapshot_id: int | None = None   # the advice the person was looking at; a stale view gets a 409


class AnswerIn(BaseModel):
    answer: str
    status: Literal["answered", "accepted"]


class EvidenceRequestIn(BaseModel):
    question: str
    role: Literal["registrar", "analyst"] = "registrar"


class RankIn(BaseModel):
    idea_ids: list[str]
    note: str | None = None


class WeightsIn(BaseModel):
    weights: dict[str, float]
    reason: str


class TasteIn(BaseModel):
    taste: dict
    reason: str


class WatchlistIn(BaseModel):
    watchlist: dict[str, list[str]]
    reason: str


class PortfolioItemIn(BaseModel):
    ambition_cell: Literal["core", "adjacent", "transformational"] | None = None
    four_p: Literal["product", "process", "position", "paradigm"] | None = None
    reason: str = Field(min_length=1)


class NewPortfolioItemIn(BaseModel):
    kind: Literal["line", "in_flight", "future_goal"]
    name: str = Field(min_length=3)
    ambition_cell: Literal["core", "adjacent", "transformational"]
    four_p: Literal["product", "process", "position", "paradigm"] | None = None
    description: str | None = None


class RetireIn(BaseModel):
    reason: str = Field(min_length=1)


class ProposalIn(BaseModel):
    accept: bool
    reason: str


# ----------------------------------------------------------------------------- guard: host, origin, auth

class Guard:
    """Pure ASGI middleware, so streaming responses (SSE, MCP) are never buffered."""

    def __init__(self, app, auth: Auth, hosts: set[str]):
        self.app, self.auth, self.hosts = app, auth, hosts

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        path, method = scope["path"], scope["method"]
        host = headers.get("host", "")
        if host not in self.hosts:
            return await self._deny(scope, receive, send, 421, "Unexpected Host header.")
        protected = path.startswith("/api/") and path != "/api/health" or path.startswith("/mcp")
        if protected:
            cookie = _cookie(headers.get("cookie", ""), COOKIE)
            bearer = self.auth.verify_bearer(headers.get("authorization"))
            session = self.auth.verify_session(cookie)
            if not (bearer or session):
                return await self._deny(scope, receive, send, 401, "Not signed in. Open the launch link printed by the service.")
            if session and not bearer and method not in ("GET", "HEAD", "OPTIONS"):
                origin = headers.get("origin")
                if origin and origin.split("://", 1)[-1] != host:
                    return await self._deny(scope, receive, send, 403, "Cross-origin write refused.")
        await self.app(scope, receive, send)

    async def _deny(self, scope, receive, send, status, detail):
        r = JSONResponse({"type": "about:blank", "title": "Refused", "status": status, "detail": detail}, status_code=status,
                         media_type="application/problem+json")
        await r(scope, receive, send)


def _cookie(header: str, name: str) -> str | None:
    for part in header.split(";"):
        k, _, v = part.strip().partition("=")
        if k == name:
            return v
    return None


# ----------------------------------------------------------------------------- app

def create_app(gk: Gatekeeper, auth: Auth, *, port: int = 8787, static_dir: Path | None = None, extra_hosts: tuple[str, ...] = ()) -> FastAPI:
    person_mcp, pipe_mcp = build_mcp(gk, "person"), build_mcp(gk, "pipeline")
    person_app = person_mcp.streamable_http_app(streamable_http_path="/")
    pipe_app = pipe_mcp.streamable_http_app(streamable_http_path="/")
    registry = build_registry(gk)

    @contextlib.asynccontextmanager
    async def lifespan(_app):
        async with contextlib.AsyncExitStack() as stack:
            for sub in (person_app, pipe_app):
                await stack.enter_async_context(sub.router.lifespan_context(sub))
            yield

    app = FastAPI(title="Gatekeeper", version="2", lifespan=lifespan, openapi_url="/api/openapi.json", docs_url="/api/docs", redoc_url=None)
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}", *extra_hosts}
    app.add_middleware(Guard, auth=auth, hosts=hosts)
    idem: dict[str, tuple[float, dict]] = {}

    @app.exception_handler(Rejected)
    async def _rejected(_req, exc: Rejected):
        return JSONResponse({"type": "about:blank", "title": "Rejected", "status": 422, "detail": str(exc)}, status_code=422,
                            media_type="application/problem+json")

    def run(name: str, args: dict):
        return invoke(gk, registry[name], args, via="web")

    # -- auth ------------------------------------------------------------------------------------------------
    @app.get("/auth/launch", include_in_schema=False)
    def launch(t: str):
        sid = auth.redeem_launch(t)
        if not sid:
            return HTMLResponse(
                "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Sign in</title>"
                "<body style='font:16px/1.5 system-ui;max-width:34rem;margin:12vh auto;padding:0 1.25rem;color:#1a1a18'>"
                "<h1 style='font-weight:600;font-size:1.6rem'>That sign-in link has expired</h1>"
                "<p>Links last 15 minutes. In a terminal, in the project folder, run:</p>"
                "<pre style='background:#f3f2ee;padding:.9rem;border-radius:6px'>service/dev.sh open</pre>"
                "<p>and open the new link it prints.</p></body>", status_code=401)
        r = RedirectResponse("/", status_code=303)
        r.set_cookie(COOKIE, sid, httponly=True, samesite="strict", max_age=SESSION_DAYS * 86400, path="/")
        return r

    @app.get("/api/health")
    def health():
        return {"ok": True, "version": 2}

    @app.get("/api/session")
    def session():
        return {"authenticated": True, "user": "you", "events_after": V.last_event_id(gk)}

    # -- reads -----------------------------------------------------------------------------------------------
    @app.get("/api/inbox")
    def inbox():
        return V.inbox(gk)

    @app.get("/api/board")
    def board():
        return V.board(gk)

    @app.get("/api/ideas/{idea_id}")
    def idea(idea_id: str):
        r = V.idea_record(gk, idea_id)
        if r is None:
            raise HTTPException(404, f"No idea {idea_id}.")
        return r

    @app.get("/api/refs/{code}")
    def ref(code: str):
        r = V.ref_card(gk, code)
        if r is None:
            raise HTTPException(404, f"Nothing is filed under {code}.")
        return r

    @app.get("/api/portfolio")
    def portfolio():
        return V.portfolio(gk)

    @app.get("/api/runs")
    def runs():
        return V.runs(gk)

    @app.get("/api/runs/{run_id}")
    def run_detail(run_id: int):
        r = V.run_detail(gk, run_id)
        if r is None:
            raise HTTPException(404, f"No run {run_id}.")
        return r

    @app.get("/api/signals")
    def signals():
        return V.signals(gk)

    @app.get("/api/log")
    def log():
        return V.log(gk)

    @app.get("/api/config")
    def config():
        return V.config(gk)

    @app.get("/api/proposals")
    def proposals():
        return V.proposals(gk)

    @app.get("/api/agents")
    def agents():
        return {"agents": T.team()}

    @app.get("/api/agents/{agent_id}")
    def agent(agent_id: str):
        a = T.agent(agent_id)
        if a is None:
            raise HTTPException(404, f"No agent {agent_id}.")
        return a

    # -- commands --------------------------------------------------------------------------------------------
    def once(key: str | None, make):
        """An Idempotency-Key makes a double click or a retry return the first result instead of writing twice."""
        if not key:
            return make()
        now = time.time()
        for k in [k for k, (t, _) in idem.items() if now - t > 600]:
            idem.pop(k)
        if key in idem:
            return idem[key][1]
        out = make()
        idem[key] = (now, out)
        return out

    @app.post("/api/ideas/{idea_id}/decisions", status_code=201)
    def decide(idea_id: str, body: DecisionIn, idempotency_key: str | None = Header(default=None)):
        def make():
            latest = gk.q1("SELECT id FROM board_snapshots WHERE idea_id=? ORDER BY id DESC LIMIT 1", (idea_id,))
            if body.seen_snapshot_id is not None and latest and latest["id"] != body.seen_snapshot_id:
                return JSONResponse({"type": "about:blank", "title": "The advice changed", "status": 409,
                                     "detail": "The recommendation changed since you opened this. Review it again before deciding.",
                                     "current": V.idea_record(gk, idea_id)["summary"]}, status_code=409, media_type="application/problem+json")
            run("decide", {"idea_id": idea_id, "action": body.action, "reason": body.reason})
            return {"ok": True, "idea": V.idea_record(gk, idea_id)["summary"]}
        return once(idempotency_key, make)

    @app.post("/api/objections/{objection_id}/answers", status_code=201)
    def answer(objection_id: int, body: AnswerIn):
        run("answer_objection", {"objection_id": objection_id, "answer": body.answer, "status": body.status})
        return {"ok": True}

    @app.post("/api/ideas/{idea_id}/evidence-requests", status_code=201)
    def evidence(idea_id: str, body: EvidenceRequestIn):
        run("request_evidence", {"idea_id": idea_id, "question": body.question, "role": body.role})
        return {"ok": True}

    @app.put("/api/my-rank")
    def my_rank(body: RankIn):
        return run("set_my_rank", {"idea_ids": body.idea_ids, "note": body.note})

    @app.post("/api/what-if/weights")
    def what_if(body: dict):
        return gk.what_if_weights(body.get("weights", body))

    @app.put("/api/config/weights")
    def set_weights(body: WeightsIn):
        return run("set_config", {"section": "weights", "body": {**gk.weights(), **body.weights}, "reason": body.reason})

    @app.put("/api/config/taste")
    def set_taste(body: TasteIn):
        return run("set_config", {"section": "taste", "body": body.taste, "reason": body.reason})

    @app.put("/api/config/watchlist")
    def set_watchlist(body: WatchlistIn):
        strategy = json.loads(json.dumps(gk.strategy()))
        strategy["watchlist"] = body.watchlist
        return run("set_config", {"section": "strategy", "body": strategy, "reason": body.reason})

    @app.post("/api/portfolio", status_code=201)
    def add_portfolio_item(body: NewPortfolioItemIn):
        return run("add_portfolio_item", {"kind": body.kind, "name": body.name, "ambition_cell": body.ambition_cell,
                                          "source": "added by the person in the web app", "description": body.description,
                                          "four_p": body.four_p})

    @app.post("/api/portfolio/{item_id}/retirement")
    def retire_portfolio_item(item_id: str, body: RetireIn):
        return run("retire_portfolio_item", {"item_id": item_id, "reason": body.reason})

    @app.patch("/api/portfolio/{item_id}")
    def retag_portfolio_item(item_id: str, body: PortfolioItemIn):
        return run("update_portfolio_item", {"item_id": item_id, "reason": body.reason,
                                             "ambition_cell": body.ambition_cell, "four_p": body.four_p})

    @app.post("/api/proposals/{proposal_id}/decision")
    def proposal(proposal_id: int, body: ProposalIn):
        return run("decide_proposal", {"proposal_id": proposal_id, "accept": body.accept, "reason": body.reason})

    # -- live stream -----------------------------------------------------------------------------------------
    @app.get("/api/stream")
    async def stream(request: Request, after: int | None = None):
        last = after
        if last is None:
            hdr = request.headers.get("last-event-id")
            last = int(hdr) if hdr and hdr.isdigit() else V.last_event_id(gk)

        async def gen():
            nonlocal last
            yield {"event": "hello", "id": str(last), "data": json.dumps({"after": last})}
            while not await request.is_disconnected():
                rows = await asyncio.to_thread(V.events_after, gk, last)
                for r in rows:
                    last = r["id"]
                    yield {"event": "ledger", "id": str(r["id"]), "data": json.dumps(r)}
                await asyncio.sleep(1.0)
        return EventSourceResponse(gen(), ping=15)

    # -- MCP: two surfaces ------------------------------------------------------------------------------------
    app.mount("/mcp/pipeline", pipe_app)
    app.mount("/mcp/person", person_app)

    # -- the web app (static build), last so it never shadows an API route -----------------------------------
    if static_dir and (static_dir / "index.html").exists():
        if (static_dir / "assets").exists():
            app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            f = (static_dir / path).resolve()
            if path and f.is_file() and static_dir.resolve() in f.parents:
                return FileResponse(f)
            return FileResponse(static_dir / "index.html")

    app.state.auth, app.state.gk = auth, gk
    return app
