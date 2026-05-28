"""
sap/mcp_enrich.py — Apply MCP 2025-11-25 metadata from mcp_registry.json to listed tools.

Adds title, annotations (readOnly/destructive/idempotent hints), and _meta (group, tier, lane).
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from mcp.types import ToolAnnotations

from sap.mcp_profiles import _tier_for_name

if TYPE_CHECKING:
    from mcp.types import Tool as MCPTool

_REGISTRY_PATH = Path(__file__).resolve().parent / "mcp_registry.json"

_LANE_BY_GROUP = {
    "kb": "data",
    "soil": "data",
    "fleet": "data",
    "handoff": "data",
    "ledger": "data",
    "index": "data",
    "mem": "data",
    "agent": "exec",
    "fork": "dev",
    "skill": "dev",
    "grove": "comms",
    "mai": "docs",
    "infer": "infer",
    "code_graph": "dev",
    "app": "ops",
    "policy": "ops",
    "nest": "ops",
    "soul": "soul",
    "voice": "infer",
    "diag": "diag",
    "kart": "exec",
    "intake": "data",
    "journal": "data",
    "workflow": "ops",
    "routine": "ops",
    "cmb": "data",
    "context": "data",
    "hook": "diag",
    "routing": "diag",
    "session": "diag",
    "pg": "data",
    "outcome": "ops",
}

_READ_RE = re.compile(
    r"(^|_)(get|list|search|read|latest|status|query|inbox|history|resolve|explain|walk)(_|$)",
    re.I,
)
_WRITE_RE = re.compile(r"(^|_)(put|write|ingest|send|post|update|delete|uninstall|install|promote|register|rebuild|run|fire|cancel|blast|restart|reload)($|_)", re.I)
_DESTRUCT_RE = re.compile(r"(delete|uninstall|cancel|blast|restart|nuke)", re.I)


@lru_cache(maxsize=1)
def _load_registry() -> dict:
    try:
        return json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _human_title(name: str, group: str) -> str:
    parts = name.split("_", 1)
    suffix = parts[1] if len(parts) > 1 else name
    label = suffix.replace("_", " ").title()
    group_label = group.replace("_", " ").title() if group else "Tool"
    return f"{group_label}: {label}"


def _infer_annotations(name: str, meta: dict) -> ToolAnnotations | None:
    if meta.get("readOnly") is True or _READ_RE.search(name) and not _WRITE_RE.search(name):
        return ToolAnnotations(readOnlyHint=True, idempotentHint=True)
    if meta.get("destructive") is True or _DESTRUCT_RE.search(name):
        return ToolAnnotations(destructiveHint=True, readOnlyHint=False)
    if name in ("fleet_status", "fleet_health", "fleet_tool_guide", "env_check", "diagnostic_summary"):
        return ToolAnnotations(readOnlyHint=True, idempotentHint=True)
    if _WRITE_RE.search(name):
        return ToolAnnotations(readOnlyHint=False, destructiveHint=bool(_DESTRUCT_RE.search(name)))
    return None


def enrich_tool(tool: "MCPTool") -> "MCPTool":
    """Return tool with registry-backed MCP metadata (mutates copy via model_copy)."""
    reg = _load_registry()
    tools = reg.get("tools") if isinstance(reg.get("tools"), dict) else {}
    meta = tools.get(tool.name) if isinstance(tools.get(tool.name), dict) else {}
    group = str(meta.get("group", tool.name.split("_")[0] if "_" in tool.name else "other"))
    tier = str(meta.get("tier") or _tier_for_name(tool.name))
    lane = str(meta.get("lane") or _LANE_BY_GROUP.get(group, "data"))

    desc = meta.get("description") if isinstance(meta, dict) else None
    description = str(desc) if desc else tool.description
    if description and not description.startswith(f"[{group}]"):
        description = f"[{group}] {description}"

    title = meta.get("title") if isinstance(meta, dict) else None
    if not title:
        title = _human_title(tool.name, group)

    ann = _infer_annotations(tool.name, meta) or tool.annotations

    meta_out = dict(tool.meta or {})
    meta_out.update(
        {
            "willow.group": group,
            "willow.tier": tier,
            "willow.lane": lane,
            "willow.profile_min": tier if tier in ("minimal", "core", "standard") else "full",
        }
    )

    return tool.model_copy(
        update={
            "title": title,
            "description": description,
            "annotations": ann,
            "meta": meta_out,
        }
    )


def enrich_tools(tools: list["MCPTool"]) -> list["MCPTool"]:
    return [enrich_tool(t) for t in tools]
