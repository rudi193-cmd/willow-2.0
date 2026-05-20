#!/usr/bin/env python3
"""
sap/unified_mcp.py — Unified MCP server: willow + grove + mai in one process.

Replaces three separate MCP servers (willow, grove, markdownai) with a single
FastMCP instance. Tool namespaces:

  kb_ soil_ fleet_ agent_ fork_ skill_ mem_ index_ ledger_ handoff_
  soul_ nest_ infer_ task_  — willow (from sap_mcp)

  grove_                    — grove messaging (from grove_tools)

  mai_                      — markdownai rendering (from mai/tools)

Entry points:
  stdio (default):  python3 -m sap.unified_mcp
  HTTP:             python3 -m sap.unified_mcp --http [--host 127.0.0.1] [--port 6274]
"""
from __future__ import annotations

import argparse

# ── Import willow MCP (registers all willow tools, exports mcp instance) ─────
import sap.sap_mcp as _sap  # noqa: F401 — side-effect: tool registration

mcp = _sap.mcp

# ── Register grove tools on the same mcp instance ────────────────────────────
from sap import grove_tools as _grove
_grove.register(mcp)

# ── Register markdownai tools on the same mcp instance ───────────────────────
from sap.mai import tools as _mai
_mai.register(mcp)


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
