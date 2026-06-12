"""
Thin shim to call Willow MCP tools from the harness.

Calls the willow CLI (`python -m willow.cli`) rather than importing internals,
so the harness stays decoupled from the fleet internals and works whether the
agent is running inside Claude Code or headless via kart.

Each function returns the Willow atom_id on success, None on failure.
"""
from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

WILLOW_CLI = [sys.executable, "-m", "willow.cli"]
APP_ID = "hanuman"


def _call(tool: str, **kwargs: Any) -> dict | None:
    payload = {"tool": tool, "app_id": APP_ID, **kwargs}
    try:
        result = subprocess.run(
            WILLOW_CLI + ["mcp-call", json.dumps(payload)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            print(f"[shim] {tool} error: {result.stderr.strip()}", file=sys.stderr)
            return None
        return json.loads(result.stdout)
    except Exception as e:
        print(f"[shim] {tool} exception: {e}", file=sys.stderr)
        return None


def ingest_atom(atom: dict) -> str | None:
    """Call kb_ingest for one chunk. Returns atom_id or None."""
    resp = _call(
        "kb_ingest",
        title=atom["title"],
        content=atom["text"],
        tags=atom["tags"],
        source_type="external",
        category="research",
        project=f"rh-{atom['run_id']}",
    )
    if resp and resp.get("atom_id"):
        return resp["atom_id"]
    return None


def search_kb(query: str, run_id: str, limit: int = 10) -> list[dict]:
    """kb_search scoped to a run_id tag."""
    resp = _call("kb_search", query=query, tags=[run_id, "apo"], limit=limit)
    if resp and isinstance(resp.get("results"), list):
        return resp["results"]
    return []


def invalidate_atom(atom_id: str, reason: str) -> bool:
    resp = _call("mem_jeles_invalidate", atom_id=atom_id, reason=reason)
    return bool(resp and resp.get("ok"))


def ratify_atom(atom_id: str) -> bool:
    resp = _call("mem_ratify", atom_id=atom_id)
    return bool(resp and resp.get("ok"))
