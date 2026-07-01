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


def boot_done_path(agent: str | None = None) -> Path:
    agent = agent or require_agent_name()
    return Path(f"/tmp/willow-boot-done-{agent}.flag")


def is_booted(agent: str | None = None) -> bool:
    """True once the boot sentinel exists for this agent, or under pytest."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    return boot_done_path(agent).exists()
