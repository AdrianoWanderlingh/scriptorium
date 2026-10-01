"""End-to-end check of the MCP server over stdio, as an agent would use it."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

CLI = Path(sys.executable).parent / "scriptorium"


async def main() -> None:
    params = StdioServerParameters(command=str(CLI), args=["--library", "classici-inglesi", "serve"])
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        print("tools:", ", ".join(t.name for t in tools.tools))
        calls = [
            ("list_libraries", {}),
            (
                "search",
                {
                    "query": "la caccia come ossessione e vendetta",
                    "also": ["obsession and revenge in the hunt"],
                    "k": 3,
                },
            ),
            ("search", {"query": "the priest explains how he solved the crime", "k": 2, "author": "Chesterton"}),
            ("related", {"entity": "Flambeau", "top": 3}),
        ]
        for name, args in calls:
            t = time.time()
            result = await session.call_tool(name, args)
            text = result.content[0].text
            print(f"\n=== {name} {args} ({time.time() - t:.1f}s, {len(text)} chars)\n{text[:900]}")


if __name__ == "__main__":
    asyncio.run(main())
