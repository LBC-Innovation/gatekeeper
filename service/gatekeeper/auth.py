"""Local, single-person auth. No passwords.

- A per-install API token (bearer) for MCP and scripts, kept in `<home>/.gatekeeper/auth.json` with owner-only permissions.
- A one-time launch link (`/auth/launch?t=...`) that the service prints at start-up. Redeeming it sets an HttpOnly,
  SameSite=Strict session cookie. Only a hash of the session id is stored.
- The service binds to loopback only, and checks the Host header (this blocks DNS rebinding) and the Origin on writes.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

LAUNCH_TTL = 15 * 60
LAUNCH_GRACE = 2 * 60   # a link opened a second time within this window still works: terminals and browsers often open a link twice
SESSION_DAYS = 30


def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


class Auth:
    def __init__(self, home: str | Path):
        d = Path(home) / ".gatekeeper"
        d.mkdir(parents=True, exist_ok=True)
        os.chmod(d, 0o700)
        self.path = d / "auth.json"
        self.data: dict = {}
        self._mtime = 0
        self._refresh(force=True)
        if "api_token" not in self.data:
            self.data = {"api_token": secrets.token_urlsafe(32), "sessions": {}, "launch": {}}
            self._save()
        self.data.setdefault("sessions", {})
        self.data.setdefault("launch", {})

    def _refresh(self, force: bool = False):
        """The file is the source of truth, so `serve.py open` in another process can mint a link the running service accepts."""
        try:
            m = self.path.stat().st_mtime_ns
        except FileNotFoundError:
            return
        if force or m != self._mtime:
            self.data = json.loads(self.path.read_text())
            self._mtime = m

    def _save(self):
        self.path.write_text(json.dumps(self.data, indent=1))
        os.chmod(self.path, 0o600)
        self._mtime = self.path.stat().st_mtime_ns

    @property
    def api_token(self) -> str:
        self._refresh()
        return self.data["api_token"]

    def rotate_token(self) -> str:
        self.data["api_token"] = secrets.token_urlsafe(32)
        self.data["sessions"] = {}
        self.data["launch"] = {}
        self._save()
        return self.api_token

    def verify_bearer(self, header: str | None) -> bool:
        if not header or not header.lower().startswith("bearer "):
            return False
        return hmac.compare_digest(header[7:].strip(), self.api_token)

    def new_launch_token(self) -> str:
        self._refresh()
        t = secrets.token_urlsafe(24)
        now = time.time()
        self._forget_old_links(now)
        self.data["launch"][_h(t)] = {"exp": now + LAUNCH_TTL, "used": None}
        self._save()
        return t

    def _forget_old_links(self, now: float):
        keep = {}
        for k, rec in self.data["launch"].items():
            exp, used = (rec, None) if isinstance(rec, (int, float)) else (rec["exp"], rec.get("used"))
            if exp > now and not (used and now - used > LAUNCH_GRACE):
                keep[k] = {"exp": exp, "used": used}
        self.data["launch"] = keep

    def redeem_launch(self, token: str) -> str | None:
        """A link works until it expires, and for a short grace window after its first use. Each redemption makes its own session."""
        self._refresh()
        now = time.time()
        self._forget_old_links(now)
        rec = self.data["launch"].get(_h(token))
        if not rec:
            self._save()
            return None
        rec["used"] = rec["used"] or now
        sid = secrets.token_urlsafe(32)
        self.data["sessions"][_h(sid)] = now
        self._save()
        return sid

    def verify_session(self, sid: str | None) -> bool:
        self._refresh()
        if not sid:
            return False
        made = self.data["sessions"].get(_h(sid))
        return bool(made) and time.time() - made < SESSION_DAYS * 86400
