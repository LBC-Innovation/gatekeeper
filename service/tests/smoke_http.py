"""Talk to a running service over streamable HTTP, the way Claude Code does.

    python service/serve.py &                      (in another shell)
    python service/tests/smoke_http.py http://127.0.0.1:8787 <api token>

Checks: no token is refused; both surfaces connect; `decide` exists only on the person surface; a read works.
"""

import asyncio
import sys

import httpx2 as httpx  # the SDK's HTTP client in the 2.x line
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def surface(base: str, name: str, token: str):
    url = f"{base}/mcp/{name}/"
    http = httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, follow_redirects=True)
    async with streamable_http_client(url, http_client=http) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = {t.name for t in (await s.list_tools()).tools}
            q = await s.call_tool("get_queue", {})
            return tools, q


async def main(base: str, token: str):
    bad = httpx.get(f"{base}/mcp/person/", headers={"Accept": "application/json, text/event-stream"})
    print("no token ->", bad.status_code)
    assert bad.status_code == 401
    person, q = await surface(base, "person", token)
    pipe, _ = await surface(base, "pipeline", token)
    print(f"person tools {len(person)} | pipeline tools {len(pipe)}")
    assert "decide" in person and "decide" not in pipe, "surface separation"
    print("get_queue ok:", not getattr(q, "is_error", False))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2]))
