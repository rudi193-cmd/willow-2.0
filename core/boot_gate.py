# core/boot_gate.py — shared boot-sentinel check. b17: BTGT0  ΔΣ=42
"""
Shared boot-sentinel logic used by both the PreToolUse hook
(willow/fylgja/events/pre_tool.py, IDE built-in tools) and the MCP server
(sap/sap_mcp.py, agent_task_submit / Kart) so the boot gate applies
regardless of which path a caller uses to do real work.

PreToolUse never fires for mcp__willow__* tool calls (Claude Code hook
matchers are scoped to IDE built-in tools), so agent_task_submit() calls
is_booted() directly rather than relying on the hook to catch it.
"""
from __future__ import annotations

import os
from pathlib import Path

from core.agent_identity import require_agent_name


def _session_suffix(session_id: str) -> str:
    return "".join(
        c for c in (session_id or "") if c.isalnum() or c in "_-"
    )[:16]


def boot_done_path(agent: str | None = None, session_id: str = "") -> Path:
    """Sentinel path, keyed per (agent, session).

    The agent name alone is NOT unique across concurrent windows — every
    parallel session runs as the same fleet identity, so a shared flag
    lets one window's SessionStart clear another window's boot state
    mid-session (observed 2026-07-04). With session_id, each session
    gets its own flag; without it, the legacy shared path is returned
    for runtimes that don't supply one.
    """
    agent = agent or require_agent_name()
    sid = _session_suffix(session_id)
    if sid:
        return Path(f"/tmp/willow-boot-done-{agent}-{sid}.flag")
    return Path(f"/tmp/willow-boot-done-{agent}.flag")


def is_booted(agent: str | None = None, session_id: str = "") -> bool:
    """True once the boot sentinel exists, or under pytest.

    With session_id: that session's flag decides. Without it (the MCP
    server can't see the CLI session's id): any live session flag for
    the agent counts, plus the legacy shared flag.
    """
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    if session_id:
        return boot_done_path(agent, session_id).exists()
    if boot_done_path(agent).exists():
        return True
    name = agent or require_agent_name()
    return any(Path("/tmp").glob(f"willow-boot-done-{name}-*.flag"))
