"""
sap/mcp_profiles.py — Tool visibility profiles for unified Willow MCP.

Reduces IDE tool-picker noise. Set WILLOW_MCP_PROFILE (default: standard).

  minimal  ~20   facade + boot primitives
  core     ~55   facade + daily data lane + kart + grove basics
  standard ~95   registry core+standard tiers (default)
  full     all   every registered tool (+ unlisted live tools)
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Iterable

_REGISTRY_PATH = Path(__file__).resolve().parent / "mcp_registry.json"

VALID_PROFILES = frozenset({"minimal", "core", "standard", "full"})

# Always visible (every profile except nothing)
_FACADE_MINIMAL = frozenset({
    "willow_status",
    "willow_attention",
    "willow_find",
    "willow_remember",
    "willow_run",
})
_FACADE_CORE = frozenset({
    "willow_delegate",
    "willow_work",
    "willow_message",
    "willow_app",
    "willow_external",
    "willow_web_search",
    "willow_code",
})
_ALWAYS = frozenset({"fleet_tool_guide"}) | _FACADE_MINIMAL

# minimal — session boot
_MINIMAL = _ALWAYS | {
    "fleet_status",
    "fleet_health",
    "handoff_latest",
    "mai_read_file",
    "kb_search",
    "kb_startup_continuity",
    "kb_get",
    "grove_inbox",
    "agent_task_submit",
    "kart_task_run",
}

# core — daily work (+ minimal)
_CORE_EXTRA = {
    *_FACADE_CORE,
    "fleet_agents",
    "fleet_system_status",
    "handoff_search",
    "handoff_rebuild",
    "kb_ingest",
    "kb_query",
    "kb_journal",
    "soil_get",
    "soil_search",
    "soil_list",
    "soil_put",
    "soil_update",
    "ledger_read",
    "ledger_write",
    "mai_write_file",
    "grove_get_history",
    "grove_send_message",
    "grove_list_channels",
    "grove_reply",
    "infer_chat",
    "skill_list",
    "skill_load",
    "agent_task_list",
    "agent_task_status",
    "app_list",
    "app_status",
    "session_review",
    "diagnostic_summary",
}

_CORE = _MINIMAL | _CORE_EXTRA

# standard — adds common extended groups (prefix allow)
_STANDARD_PREFIXES = (
    "grove_",
    "fork_",
    "nest_",
    "infer_",
    "mem_check",
    "mem_ratify",
    "mem_binder_",
    "index_search",
    "index_feedback",
    "code_graph_",
    "policy_",
    "agent_dispatch",
    "agent_route",
    "agent_create",
    "intake_",
    "journal_read",
    "pg_edge_",
    "ledger_verify",
    "env_check",
    "voice_",
)

# Never in standard — full profile only
_FULL_ONLY_PREFIXES = (
    "workflow_",
    "routine_",
    "cmb_",
    "context_",
    "outcome_",
    "hook_",
    "routing_",
    "session_query",
)
_FULL_ONLY_NAMES = frozenset({
    "tension_scan",
    "dream_check",
    "dream_run",
    "kb_backup",
    "kb_promote",
    "kb_extract_from_session",
    "kb_intelligence_run",
    "mem_jeles_register",
    "mem_jeles_extract",
    "mem_jeles_ask",
    "mem_jeles_build_centroids",
    "mem_jeles_get",
    "mem_jeles_invalidate",
    "mem_jeles_search",
    "mem_jeles_web_search",
    "mem_ratify_list",
    "fleet_blast",
    "fleet_restart",
    "fleet_reload",
    "fleet_governance",
    "fleet_base17",
    "fleet_persona",
    "soil_delete",
    "soil_search_all",
    "soil_stats",
    "soil_audit",
    "soil_add_edge",
    "soil_edges_for",
    "fork_delete",
    "fork_join",
    "fork_log",
    "fork_merge",
    "mai_call_macro",
    "mai_execute_directive",
    "mai_get_constraints",
    "mai_get_env",
    "mai_invalidate_cache",
    "mai_list_phases",
    "mai_next_phase",
    "mai_resolve_phase",
    "grove_watch",
    "grove_watch_all",
    "grove_bus_send",
    "grove_bus_receive",
    "grove_flag",
    "grove_unflag",
    "grove_flagged",
    "grove_heartbeat",
    "grove_search",
    "grove_get_thread",
    "grove_get_identity",
    "grove_ack",
    "index_feedback_write",
    "index_ingest",
    "index_journal",
    "infer_7b",
    "infer_speak",
    "infer_imagine",
    "app_install",
    "app_uninstall",
    "policy_put",
    "policy_delete",
    "skill_put",
    "agent_dispatch_result",
    "kb_at",
})


@lru_cache(maxsize=1)
def _load_registry() -> dict:
    try:
        data = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def active_profile() -> str:
    raw = (os.environ.get("WILLOW_MCP_PROFILE") or "standard").strip().lower()
    return raw if raw in VALID_PROFILES else "standard"


def _tier_for_name(name: str) -> str:
    reg = _load_registry()
    tools = reg.get("tools") if isinstance(reg.get("tools"), dict) else {}
    meta = tools.get(name)
    if isinstance(meta, dict) and meta.get("tier"):
        return str(meta["tier"])
    if name in _MINIMAL:
        return "minimal"
    if name in _CORE:
        return "core"
    for p in _FULL_ONLY_PREFIXES:
        if name.startswith(p):
            return "extended"
    if name in _FULL_ONLY_NAMES:
        return "extended"
    for p in _STANDARD_PREFIXES:
        if name.startswith(p) or name == p:
            return "standard"
    # mai phase tools, agent extras, etc.
    if name.startswith("mai_") and name not in _CORE:
        return "extended"
    if name.startswith(("agent_", "fork_", "skill_", "index_", "mem_")):
        return "standard"
    return "extended"


_PROFILE_ORDER = ("minimal", "core", "standard", "full")


def _profile_rank(profile: str) -> int:
    try:
        return _PROFILE_ORDER.index(profile)
    except ValueError:
        return 2  # standard


def allows_tool(name: str, profile: str | None = None) -> bool:
    prof = profile or active_profile()
    if prof == "full":
        return True
    tier = _tier_for_name(name)
    need = {"minimal": "minimal", "core": "core", "standard": "standard", "extended": "full"}.get(
        tier, "full"
    )
    return _profile_rank(prof) >= _profile_rank(need)


def filter_tool_names(names: Iterable[str], profile: str | None = None) -> list[str]:
    prof = profile or active_profile()
    if prof == "full":
        return sorted(names)
    return sorted(n for n in names if allows_tool(n, prof))


def format_tool_guide(*, profile: str | None = None, group: str | None = None) -> str:
    """Grouped catalog for agents — call via fleet_tool_guide MCP tool."""
    prof = profile or active_profile()
    reg = _load_registry()
    groups = reg.get("groups") if isinstance(reg.get("groups"), dict) else {}
    tools = reg.get("tools") if isinstance(reg.get("tools"), dict) else {}

    by_group: dict[str, list[str]] = {}
    for name in filter_tool_names(tools.keys(), prof):
        meta = tools.get(name)
        g = str(meta.get("group", "other")) if isinstance(meta, dict) else "other"
        if group and g != group:
            continue
        by_group.setdefault(g, []).append(name)

    lines = [
        f"[WILLOW-TOOLS] profile={prof}  (set WILLOW_MCP_PROFILE: minimal|core|standard|full)",
        "Start here: willow_status · willow_find · willow_remember · willow_run",
        "Backend lanes: data=kb/soil · exec=Kart · messages=Grove · docs=mai",
        "",
    ]
    for g, desc in groups.items():
        names = by_group.get(g, [])
        if not names:
            continue
        lines.append(f"## {g} — {desc}")
        for n in names:
            d = tools.get(n, {})
            hint = d.get("description", "") if isinstance(d, dict) else ""
            short = (hint[:72] + "…") if len(hint) > 72 else hint
            lines.append(f"  - `{n}`" + (f" — {short}" if short else ""))
        lines.append("")
    lines.append("Unlisted live tools (mem_*, workflow_*, …) → WILLOW_MCP_PROFILE=full")
    return "\n".join(lines).strip()
