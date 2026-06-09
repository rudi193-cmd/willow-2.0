"""
mcp_routing.py — Two-lane tool routing for prompt injection and pre_tool messages.

  Data lane  — Willow MCP (kb, soil, fleet, handoff, app_list, …)
  Exec lane  — Kart via agent_task_submit + kart_task_run (ls, git, pytest, shell)

Agent Bash is not the execution plane; Kart is.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "sap" / "mcp_registry.json"

_KART = "agent_task_submit → kart_task_run (see /kart)"
_SCRIPT = "agent_task_submit(script_body=...) — avoids MCP JSON quote breakage"

# shell habit → (decision, redirect message)
BASH_TO_MCP: list[tuple[str, str, str]] = [
    (r"^\s*ls(\s|$)", "block", _KART),
    (r"^\s*(cat|head|tail)\s", "block", "Read · mai_read_file (repo files); shell paths → " + _KART),
    (r"^\s*psql\s", "block", "kb_query · soil_search — Postgres via MCP, not shell"),
    (r"\bsqlite3\b", "block", "soil_get · soil_list · soil_search"),
    (r"^\s*pwd\s*$", "warn", "cwd is in context; fleet_status for roots"),
    (r"^\s*tree(\s|$)", "warn", f"Glob · {_KART}"),
    (r"^\s*du(\s|$)", "warn", f"fleet_system_status · {_KART}"),
    (r"\bgrep\b", "warn", f"kb_search/soil_search for Willow data; raw repo grep → {_KART}"),
    (r"\bfind\s", "warn", f"Glob · code_graph_search; raw find → {_KART}"),
    (r"(?i)python3?\s+-m\s+(willow|sap|core)\.", "block", "Matching MCP tool — sap/mcp_registry.json"),
    (r"(?i)python3?\s+(-c|--command)\s", "warn", _SCRIPT),
]

BRIEF_LINE = (
    "[WILLOW-LANES] Start: willow_status · willow_attention · willow_find · willow_remember · willow_run. "
    "Data detail → kb/soil/handoff MCP. "
    "Execution (ls, git, pytest, pipelines) → willow_run / Kart — not agent Bash. "
    "Python or nested quotes → willow_run(script_body=...). "
    "Never psql/sqlite3 Willow stores from shell."
)


@lru_cache(maxsize=1)
def _load_registry() -> dict:
    try:
        data = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def format_cheat_sheet(*, max_groups: int = 8) -> str:
    """Compact group → example tools for first-turn context."""
    reg = _load_registry()
    groups = reg.get("groups") if isinstance(reg.get("groups"), dict) else {}
    tools = reg.get("tools") if isinstance(reg.get("tools"), dict) else {}
    by_group: dict[str, list[str]] = {}
    for name, meta in tools.items():
        if not isinstance(meta, dict):
            continue
        g = str(meta.get("group", "other"))
        by_group.setdefault(g, []).append(name)
    prof = os.environ.get("WILLOW_MCP_PROFILE", "standard")
    lines = [
        f"[WILLOW-LANES] profile={prof} · Start=willow_* facade · catalog=fleet_tool_guide",
    ]
    group_order = list(groups.keys())
    if "willow" in group_order:
        group_order = ["willow"] + [g for g in group_order if g != "willow"]
    for g in group_order[:max_groups]:
        examples = ", ".join(by_group.get(g, [])[:3])
        if examples:
            lines.append(f"  {g}: {examples}")
    lines.append("  start: willow_status · willow_find · willow_remember · willow_run")
    lines.append(f"  exec: ls/git/pytest → willow_run · {_KART}")
    lines.append("  data: willow_find(scope=…) · fleet → willow_status")
    return "\n".join(lines)


def format_brief() -> str:
    return BRIEF_LINE


def redirect_for_command(command: str) -> tuple[str, str] | None:
    """Return (decision, message) for a shell command, or None."""
    import re

    for pattern, decision, hint in BASH_TO_MCP:
        if re.search(pattern, command, re.MULTILINE):
            msg = f"Use Kart, not agent Bash. → {hint}"
            return decision, msg
    return None
