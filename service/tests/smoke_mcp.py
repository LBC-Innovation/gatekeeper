"""Talk to the real server over stdio, the way Claude does.

Run:  python tests/smoke_mcp.py
Uses a throwaway GATEKEEPER_HOME so your ledger is untouched.
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


def is_error(result) -> bool:
    return bool(getattr(result, "is_error", getattr(result, "isError", False)))


def text_of(result) -> str:
    return "".join(getattr(c, "text", "") for c in result.content)


async def main():
    with tempfile.TemporaryDirectory() as home:
        params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "gatekeeper_server.py")],
                                       env={**os.environ, "GATEKEEPER_HOME": home})
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                tools = (await s.list_tools()).tools
                print(f"tools: {len(tools)}")
                st = await s.call_tool("get_setup_status", {})
                print("setup next step:", json.loads(text_of(st))["next_step"])
                bad = await s.call_tool("set_config", {"section": "weights", "body": {"analyst": 2}, "reason": "smoke test bad value"})
                print("rejected as expected:", is_error(bad), "|", text_of(bad)[:120])
                ok = await s.call_tool("set_config", {"section": "weights", "body": {"analyst": 0.4}, "reason": "smoke test good value"})
                print("accepted:", not is_error(ok), "|", text_of(ok)[:120])
                ps = await s.call_tool("get_pipeline_status", {})
                rej = json.loads(text_of(ps))["recent_rejections"]
                print("rejections logged:", len(rej), rej[0]["tool"] if rej else None)
                assert len(tools) >= 50 and is_error(bad) and not is_error(ok) and rej


if __name__ == "__main__":
    asyncio.run(main())
    print("smoke test passed")
