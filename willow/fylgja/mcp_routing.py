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
# Always-available shell fallback when no Willow tool fits. Native Grep/Glob are
# NOT in the Willow MCP profile (this redirect only fires when Willow enforcement
# is active), so pointing at them sends agents to a tool the session lacks — they
# bounce back to Bash and the block counter climbs. Route to lanes that exist.
_RUN = f"{_KART} or willow_run(script_body=...)"

_ENUM = f"willow_find(scope=code) · code_graph_search · cbm_search · {_RUN}"

# shell habit → (decision, redirect message)
BASH_TO_MCP: list[tuple[str, str, str]] = [
    (r"^\s*ls(\s|$)", "block", f"soil_list/app_list for Willow data · filesystem listing → {_RUN}"),
    (r"^\s*(cat|head|tail)\s", "block", f"Read · mai_read_file (repo files) · shell-only → {_KART}"),
    (r"^\s*psql\s", "block", "kb_query · soil_search — Postgres via MCP, not shell"),
    (r"\bsqlite3\b", "block", "soil_get · soil_list · soil_search"),
    (r"^\s*pwd\s*$", "warn", "cwd is in context; fleet_status for roots"),
    (r"^\s*tree(\s|$)", "block", f"directory tree → {_RUN}"),
    (r"^\s*du(\s|$)", "warn", f"fleet_system_status · {_KART}"),
    # Word-boundary git/gh — blocks `cd repo && git status` evasion of ^\s*git anchor.
    (r"\bgit\s", "block", f"{_KART} · allow_net=True for push/fetch — agent Bash has no git creds"),
    (r"\bgh\s", "block", f"{_KART} · allow_net=True — agent Bash has no gh creds"),
    (r"\bgrep\b", "block", f"willow_find(scope=code) · code_graph_search for code · kb_search/soil_search for Willow knowledge · raw text → {_RUN}"),
    (r"\brg\b", "block", f"willow_find(scope=code) · code_graph_search · raw text → {_RUN}"),
    (r"\bfind\s", "block", f"code_graph_search · willow_find(scope=code) for code · file enumeration → {_RUN}"),
    # Python enumeration / heredoc bypasses (Sonnet gremlin session e374e216).
    (r"(?i)python3?\s+.*<<", "block", f"Python heredoc in agent Bash → {_SCRIPT}"),
    (r"(?i)\bos\.walk\s*\(", "block", _ENUM),
    (r"(?i)\.rglob\s*\(", "block", _ENUM),
    (r"(?i)\bglob\.glob\s*\(", "block", _ENUM),
    (r"(?i)\bos\.scandir\s*\(", "block", _ENUM),
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
