"""
mcp_routing.py — Two-lane tool routing for prompt injection and pre_tool messages.

  Data lane  — Willow MCP (kb, soil, fleet, handoff, app_list, …)
  Exec lane  — Kart via willow_run (ls, git mutations, pytest, shell)

Read-only git/gh may run in agent Bash on the operator desk — models know GitHub;
mutations route through willow_run.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "sap" / "mcp_registry.json"

_WILLOW_RUN = "willow_run(app_id=<agent>, task='…', run_now=True)"
_WILLOW_RUN_NET = "willow_run(app_id=<agent>, task='…', allow_net=True, run_now=True)"
_SCRIPT = "willow_run(app_id=<agent>, script_body='…', run_now=True)"
# Always-available shell fallback when no Willow tool fits. Native Grep/Glob are
# NOT in the Willow MCP profile (this redirect only fires when Willow enforcement
# is active), so pointing at them sends agents to a tool the session lacks — they
# bounce back to Bash and the block counter climbs. Route to lanes that exist.
_RUN = f"{_WILLOW_RUN} or {_SCRIPT}"

_ENUM = f"cbm_search_code (text/pattern) · willow_find(scope=code) · code_graph_search (symbol name) · {_RUN}"

# Read-only git/gh — allowed in agent Bash (operator desk; no Kart round-trip).
_GIT_INSPECT = re.compile(
    r"(?:^|&&\s*)git(?:\s+-C\s+\S+)?\s+"
    r"(status|log|diff|show|branch|rev-parse|describe|shortlog|remote|fetch)\b",
    re.IGNORECASE,
)
_GH_INSPECT = re.compile(
    r"(?:^|&&\s*)gh\s+"
    r"(pr\s+(view|list|checks|status|diff)|issue\s+(view|list)|run\s+list|repo\s+view)\b",
    re.IGNORECASE,
)
_GIT_MUTATION = re.compile(
    r"\bgit(?:\s+-C\s+\S+)?\s+"
    r"(add|commit|push|pull|merge|rebase|checkout|switch|restore|reset|clean|"
    r"clone|cherry-pick|revert|stash|tag|worktree\s+(add|remove)|am)\b",
    re.IGNORECASE,
)
_GH_MUTATION = re.compile(
    r"\bgh\s+"
    r"(pr\s+(create|merge|close|ready|review|edit)|issue\s+create|"
    r"repo\s+create|release\s+create)\b",
    re.IGNORECASE,
)

# shell habit → (decision, redirect message)
BASH_TO_MCP: list[tuple[str, str, str]] = [
    (r"^\s*ls(\s|$)", "block", f"soil_list/app_list for Willow data · filesystem listing → {_RUN}"),
    (r"^\s*(cat|head|tail)\s", "block", f"Read · mai_read_file (repo files) · shell-only → {_WILLOW_RUN}"),
    (r"^\s*psql\s", "block", "kb_query · soil_search — Postgres via MCP, not shell"),
    (r"\bsqlite3\b", "block", "soil_get · soil_list · soil_search"),
    (r"^\s*pwd\s*$", "warn", "cwd is in context; fleet_status for roots"),
    (r"^\s*tree(\s|$)", "block", f"directory tree → {_RUN}"),
    (r"^\s*du(\s|$)", "warn", f"fleet_system_status · {_WILLOW_RUN}"),
    # git/gh mutations — inspect subcommands are allowed via is_git_gh_inspect_allowed().
    (r"\bgit\s+(push|pull)\b", "block", f"git network → {_WILLOW_RUN_NET}"),
    (
        r"\bgit\s+(add|commit|checkout|merge|rebase|worktree|clone|stash|reset|restore|switch|clean|cherry-pick|revert|tag)\b",
        "block",
        f"git mutation → {_WILLOW_RUN}",
    ),
    (r"\bgh\s", "block", f"gh (mutations / net) → {_WILLOW_RUN_NET}"),
    (r"\bgit\s", "block", f"git (unknown subcommand) → inspect in Bash (status/log/diff) or {_WILLOW_RUN}"),
    (r"\bgrep\b", "block", f"cbm_search_code (text/pattern search) · kb_search/soil_search for Willow knowledge · symbol lookup → willow_find(scope=code)/code_graph_search · {_RUN}"),
    (r"\brg\b", "block", f"cbm_search_code (text/pattern search) · symbol lookup → willow_find(scope=code)/code_graph_search · {_RUN}"),
    (r"\bfind\s", "block", f"cbm_search_code(mode='files') for file enumeration by content · code_graph_search/willow_find(scope=code) for symbols · {_RUN}"),
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
    "git status/log/diff + gh pr view/list → agent Bash OK. "
    "git commit/push + gh pr create → willow_run(run_now=True). "
    "Other shell (ls, pytest) → willow_run — not agent Bash. "
    "Never psql/sqlite3 Willow stores from shell."
)


def is_git_gh_inspect_allowed(command: str) -> bool:
    """True when a shell command is read-only git/gh (may run in agent Bash)."""
    c = (command or "").strip()
    if not c:
        return False
    if _GIT_MUTATION.search(c) or _GH_MUTATION.search(c):
        return False
    return bool(_GIT_INSPECT.search(c) or _GH_INSPECT.search(c))


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
    lines.append("  exec: git inspect in Bash · mutations → willow_run(run_now=True)")
    lines.append("  data: willow_find(scope=…) · fleet → willow_status")
    return "\n".join(lines)


def format_brief() -> str:
    return BRIEF_LINE


def redirect_for_command(command: str) -> tuple[str, str] | None:
    """Return (decision, message) for a shell command, or None."""
    import re

    if is_git_gh_inspect_allowed(command):
        return None
    for pattern, decision, hint in BASH_TO_MCP:
        if re.search(pattern, command, re.MULTILINE):
            msg = f"Use willow_run, not agent Bash. → {hint}"
            return decision, msg
    return None
