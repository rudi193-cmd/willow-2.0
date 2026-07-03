#!/usr/bin/env python3
"""Project-scoped MCP inventory — wired servers, Willow facade verbs, reuse rails.

Default: scan the workspace repo only (fast, boot-safe).
Optional --fleet: sweep ~/github (slow; operator/Kart only).
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from sap.mcp_profiles import willow_facade_names

_REUSE_RULE = "willow_find → willow_run → willow_remember"
_CBM_LANE = "cbm_status → cbm_search | cbm_trace | cbm_verify_callers"
_MCP_JSON_PATHS = (".cursor/mcp.json", ".willow/mcp.json", ".claude/mcp.json")
_SKIP_PARTS = {".git", "node_modules", "__pycache__", ".venv", "worktrees", "site-packages"}


def _parse_mcp_json(path: Path) -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return {}
    servers = data.get("mcpServers") or data.get("servers") or {}
    if not isinstance(servers, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for name, cfg in servers.items():
        if not isinstance(cfg, dict):
            continue
        out[name] = {
            "source": str(path.name),
            "command": cfg.get("command") or cfg.get("url") or "",
            "type": cfg.get("type", "stdio"),
        }
    return out


def _count_registry(path: Path) -> int | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return None
    tools = data.get("tools")
    if not isinstance(tools, dict):
        return None
    return sum(1 for k in tools if not str(k).startswith("_"))


def scan_workspace(workspace: str | Path) -> dict[str, Any]:
    """Inventory MCP surfaces for one repo root. Never raises."""
    root = Path(workspace).expanduser().resolve()
    merged_servers: dict[str, dict[str, Any]] = {}
    degraded: list[str] = []

    if not root.is_dir():
        return {
            "workspace": str(root),
            "error": "not_a_directory",
            "degraded": [f"workspace missing: {root}"],
        }

    for rel in _MCP_JSON_PATHS:
        fp = root / rel
        if fp.is_file():
            merged_servers.update(_parse_mcp_json(fp))

    reg_path = root / "sap" / "mcp_registry.json"
    registry_count = _count_registry(reg_path)

    return {
        "workspace": str(root),
        "mcp_servers": sorted(merged_servers.keys()),
        "mcp_server_detail": merged_servers,
        "willow_verbs": willow_facade_names(),
        "willow_profile_hint": "minimal=13 facades; fleet_tool_guide expands",
        "registry_tool_count": registry_count,
        "registry_path": str(reg_path.relative_to(root)) if reg_path.is_file() else "",
        "cbm_lane": _CBM_LANE,
        "reuse_rule": _REUSE_RULE,
        "degraded": degraded,
    }


def _skip(path: Path) -> bool:
    return any(p in _SKIP_PARTS for p in path.parts)


def scan_fleet(github_root: str | Path | None = None) -> dict[str, Any]:
    """Sweep sibling repos under ~/github for MCP configs (not for boot)."""
    root = Path(github_root or os.environ.get("GITHUB_ROOT", Path.home() / "github")).expanduser()
    repos: list[dict[str, Any]] = []
    if not root.is_dir():
        return {"github_root": str(root), "error": "not_a_directory", "repos": []}

    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        inv = scan_workspace(child)
        if inv.get("mcp_servers") or inv.get("registry_tool_count"):
            repos.append(
                {
                    "repo": child.name,
                    "mcp_servers": inv.get("mcp_servers") or [],
                    "registry_tool_count": inv.get("registry_tool_count"),
                }
            )

    return {
        "github_root": str(root),
        "repos_with_mcp": len(repos),
        "repos": repos,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="MCP inventory for workspace or fleet")
    parser.add_argument("--workspace", default=".", help="Repo root to scan (default: cwd)")
    parser.add_argument("--fleet", action="store_true", help="Sweep ~/github (slow)")
    parser.add_argument("--json", action="store_true", dest="as_json", help="JSON output")
    args = parser.parse_args()

    if args.fleet:
        payload = scan_fleet()
    else:
        payload = scan_workspace(args.workspace)

    if args.as_json:
        print(json.dumps(payload, indent=2))
    else:
        if args.fleet:
            print(json.dumps({k: payload[k] for k in payload if k != "repos"}, indent=2))
            for row in payload.get("repos") or []:
                print(f"  {row['repo']}: servers={row.get('mcp_servers')} registry={row.get('registry_tool_count')}")
        else:
            print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
