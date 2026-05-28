#!/usr/bin/env python3
"""
sap/unified_mcp.py — Unified MCP server: willow + grove + mai in one process.

Tool visibility: WILLOW_MCP_PROFILE (default standard)
  minimal ~25 | core ~45 | standard ~95 | full = all tools

Entry points:
  stdio (default):  python3 -m sap.unified_mcp
  HTTP:             python3 -m sap.unified_mcp --http [--host 127.0.0.1] [--port 6274]
"""
from __future__ import annotations

import argparse
from typing import Any

from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import Tool as MCPTool

from sap.mcp_enrich import enrich_tools
from sap.mcp_profiles import active_profile, allows_tool

# ── Import willow MCP (registers all willow tools, exports mcp instance) ─────
import sap.sap_mcp as _sap  # noqa: F401 — side-effect: tool registration

mcp = _sap.mcp

# ── Register grove tools on the same mcp instance ────────────────────────────
from sap import grove_tools as _grove
_grove.register(mcp)

# ── Register markdownai tools on the same mcp instance ───────────────────────
from sap.mai import tools as _mai
_mai.register(mcp)

# ── Tool guide (always registered; visible in every profile) ─────────────────
from sap import mcp_guide as _guide
_guide.register(mcp)

def _apply_profile_filter() -> None:
    if getattr(mcp, "_willow_profile_patched", False):
        return
    orig_list = mcp.list_tools
    orig_call = mcp.call_tool

    async def _filtered_list_tools() -> list[MCPTool]:
        tools = await orig_list()
        prof = active_profile()
        if prof != "full":
            tools = [t for t in tools if allows_tool(t.name, prof)]
        return enrich_tools(tools)

    async def _filtered_call_tool(name: str, arguments: dict[str, Any]):
        if not allows_tool(name):
            prof = active_profile()
            raise ToolError(
                f"Tool '{name}' is not in WILLOW_MCP_PROFILE={prof}. "
                f"Call fleet_tool_guide() or set WILLOW_MCP_PROFILE=full."
            )
        return await orig_call(name, arguments)

    mcp.list_tools = _filtered_list_tools  # type: ignore[method-assign]
    mcp.call_tool = _filtered_call_tool  # type: ignore[method-assign]
    mcp._willow_profile_patched = True  # type: ignore[attr-defined]


_apply_profile_filter()


def main() -> None:
    ap = argparse.ArgumentParser(description="Unified Willow MCP (willow + grove + mai)")
    ap.add_argument("--http",  action="store_true", help="Streamable-HTTP instead of stdio")
    ap.add_argument("--port",  type=int, default=6274, help="HTTP port (default: 6274)")
    ap.add_argument("--host",  default="127.0.0.1",   help="HTTP host")
    args = ap.parse_args()

    if args.http:
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
