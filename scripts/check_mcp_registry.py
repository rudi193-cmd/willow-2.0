#!/usr/bin/env python3
"""
Verify Willow MCP tools against mcp_registry.json and MCP 2025-11-25 name rules.

Exit 0 = OK, 1 = drift or spec violations.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

# Full tool surface for registry drift check
import os

os.environ.setdefault("WILLOW_MCP_PROFILE", "full")

_NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _load_registry() -> dict:
    return json.loads((REPO / "sap" / "mcp_registry.json").read_text(encoding="utf-8"))


async def _live_tool_names() -> set[str]:
    import sap.unified_mcp as u

    tools = await u.mcp.list_tools()
    return {t.name for t in tools}


def main() -> int:
    strict = "--strict" in sys.argv
    reg = _load_registry()
    registered = set(reg.get("tools", {}).keys())
    live = asyncio.run(_live_tool_names())

    errors: list[str] = []
    warnings: list[str] = []

    for name in sorted(live):
        if not _NAME_RE.match(name):
            errors.append(f"invalid tool name (MCP 2025-11-25): {name!r}")
        if " " in name or "," in name:
            errors.append(f"tool name contains illegal chars: {name!r}")

    missing_reg = sorted(live - registered)
    orphan_reg = sorted(registered - live)

    if missing_reg:
        warnings.append(f"{len(missing_reg)} live tools missing from mcp_registry.json (first 10): {missing_reg[:10]}")
    if orphan_reg:
        warnings.append(f"{len(orphan_reg)} registry entries not live (first 10): {orphan_reg[:10]}")

    lock = json.loads((REPO / "sap" / "MCP_SPEC.lock.json").read_text(encoding="utf-8"))
    print(f"MCP spec pin: {lock['spec_version']}  live_tools={len(live)}  registry={len(registered)}")

    for w in warnings:
        print(f"WARN: {w}")
    for e in errors:
        print(f"ERROR: {e}")

    if errors:
        return 1
    if strict and missing_reg:
        print("ERROR: --strict: register all live tools in sap/mcp_registry.json")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
