"""Boot digest provider #5 — workspace MCP inventory (reuse rails)."""
from __future__ import annotations

from scripts.mcp_inventory import scan_workspace
from willow.fylgja.digest_registry import DigestContext


def fetch(ctx: DigestContext) -> dict | None:
    """Return inventory for ctx.repo_root; never raises."""
    root = ctx.repo_root or ctx.workspace
    if not str(root).strip():
        return None
    data = scan_workspace(root)
    if data.get("error"):
        return {
            "workspace": data.get("workspace", ""),
            "degraded": data.get("degraded") or [str(data.get("error"))],
        }
    return data
