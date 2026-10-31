"""MCP adapter: registers every command on one surface as a tool. No rules live here."""

from __future__ import annotations

import inspect
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations

from .core import Gatekeeper, Rejected
from .registry import Command, build_registry, invoke

INSTRUCTIONS = (
    "Gatekeeper is an innovation pipeline ledger. Agents write signals, candidates, reviews and objections "
    "through these tools; the person reviews the board, decides, ranks and edits configuration. Every write is "
    "validated: figures need claims (sourced or estimated), decisions need reasons, Red Team reads ideas blind. "
    "When a call is rejected, read the message: it says exactly what to fix."
)


def _tool_for(gk: Gatekeeper, cmd: Command, via: str | None):
    def tool(**kwargs):
        try:
            return invoke(gk, cmd, kwargs, via=via)
        except Rejected as e:
            raise ToolError(f"Rejected: {e}") from None

    tool.__name__ = cmd.name
    tool.__doc__ = cmd.description
    tool.__signature__ = cmd.signature.replace(return_annotation=cmd.returns)  # type: ignore[attr-defined]
    tool.__annotations__ = {**{n: p.annotation for n, p in cmd.signature.parameters.items()}, "return": cmd.returns}
    return tool


def build_mcp(gk: Gatekeeper, surface: str = "person", *, name: str = "gatekeeper") -> MCPServer:
    """surface: "person" (everything, for you and the web app) or "pipeline" (what agents may call)."""
    server = MCPServer(name, instructions=INSTRUCTIONS)
    via = "claude" if surface == "person" else None
    for cmd in build_registry(gk).values():
        if not cmd.on(surface):
            continue
        server.add_tool(_tool_for(gk, cmd, via), name=cmd.name, description=cmd.description,
                        annotations=ToolAnnotations(readOnlyHint=cmd.read_only, destructiveHint=False,
                                                    idempotentHint=cmd.read_only, openWorldHint=False))
    return server
