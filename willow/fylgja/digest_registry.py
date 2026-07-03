"""Boot digest section registry — loads digest_sections.json and runs providers."""
from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any

_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "digest_sections.json"


@dataclass(frozen=True)
class DigestContext:
    agent: str
    project: str = ""
    workspace: str | Path = ""
    repo_root: str | Path = ""
    include_attention: bool = True
    extra: dict | None = None


def load_registry_config() -> dict[str, Any]:
    try:
        data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def pluggable_sections() -> list[dict[str, Any]]:
    """Enabled sections that declare a provider module (excludes builtin-only)."""
    cfg = load_registry_config()
    rows = cfg.get("sections") if isinstance(cfg.get("sections"), list) else []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if not row.get("enabled", True):
            continue
        provider = str(row.get("provider") or "").strip()
        if not provider:
            continue
        out.append(row)
    return sorted(out, key=lambda r: int(r.get("order") or 0))


def apply_pluggable_sections(digest: dict, ctx: DigestContext) -> None:
    """Mutate digest: set digest['sections'][id] from each provider."""
    digest.setdefault("sections", {})
    for entry in pluggable_sections():
        section_id = str(entry.get("id") or "")
        provider = str(entry.get("provider") or "")
        if not section_id or not provider:
            continue
        try:
            mod = import_module(provider)
            fetch = getattr(mod, "fetch", None)
            if not callable(fetch):
                digest.setdefault("degraded", []).append(f"{section_id}: no fetch()")
                continue
            result = fetch(ctx)
            if result is not None:
                digest["sections"][section_id] = result
        except Exception as exc:
            digest.setdefault("degraded", []).append(f"{section_id}: {exc}")


def render_pluggable_lines(digest: dict) -> list[str]:
    """Model-facing lines for registered pluggable sections (by config order)."""
    lines: list[str] = []
    sections_data = digest.get("sections") or {}
    for entry in pluggable_sections():
        section_id = str(entry.get("id") or "")
        if section_id == "mcp_inventory":
            lines.extend(_render_mcp_inventory(sections_data.get("mcp_inventory") or {}))
    return lines


def _render_mcp_inventory(inv: dict) -> list[str]:
    if not inv or inv.get("error"):
        degraded = inv.get("degraded") or []
        if degraded:
            return [f"tools: degraded — {str(degraded[0])[:120]}"]
        return []
    servers = inv.get("mcp_servers") or []
    verbs = inv.get("willow_verbs") or []
    reg = inv.get("registry_tool_count")
    reg_s = str(reg) if reg is not None else "?"
    server_s = ",".join(servers) if servers else "none"
    lines = [
        f"tools: servers={server_s} · verbs=willow_* ({len(verbs)}) · registry={reg_s}",
        f"reuse: {inv.get('reuse_rule', '')} — no new MCP without inventory",
        f"code: {inv.get('cbm_lane', '')} first",
    ]
    return [ln for ln in lines if ln.strip()]
