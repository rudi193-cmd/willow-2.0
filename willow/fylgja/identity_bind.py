"""
identity_bind.py — MCP caller identity vs runtime env coherence.

Used by sap middleware (warn/strict), fleet_identity_status, and ./willow agents check.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from willow.fylgja.project_env import (
    load_mcp_env,
    read_active_agent,
    repo_root,
    resolve_agent_name,
)
from willow.fylgja.willow_home import willow_home


def identity_bind_mode() -> str:
    """off | warn | strict (default warn)."""
    raw = os.environ.get("WILLOW_IDENTITY_BIND", "warn").strip().lower()
    if raw in ("off", "0", "false", "no"):
        return "off"
    if raw in ("strict", "enforce", "block"):
        return "strict"
    return "warn"


def expected_agent_id() -> str:
    return os.environ.get("WILLOW_AGENT_NAME", "").strip()


def check_app_id(app_id: str) -> tuple[str, str | None]:
    """
    Returns (action, message) where action is ok | warn | block.
    """
    mode = identity_bind_mode()
    if mode == "off":
        return "ok", None

    expected = expected_agent_id()
    if not expected:
        return "ok", None

    caller = (app_id or "").strip()
    if caller == expected:
        return "ok", None

    msg = (
        f"app_id={caller!r} does not match WILLOW_AGENT_NAME={expected!r} "
        f"— run: ./willow agents install {expected} --ide all"
    )
    if mode == "strict":
        return "block", msg
    return "warn", msg


def _read_persona_overlay() -> str:
    path = willow_home() / "willow-2.0-active-persona"
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return ""


def _cursor_mcp_agent(root: Path) -> str:
    link = root / ".cursor" / "mcp.json"
    try:
        if link.is_symlink():
            target = (link.parent / os.readlink(link)).resolve()
            if target.is_file():
                data = json.loads(target.read_text(encoding="utf-8"))
                env_block = data.get("mcpServers", {}).get("willow", {}).get("env", {})
                if isinstance(env_block, dict):
                    name = str(env_block.get("WILLOW_AGENT_NAME", "")).strip()
                    if name:
                        return name
        if link.is_file():
            data = json.loads(link.read_text(encoding="utf-8"))
            env_block = data.get("mcpServers", {}).get("willow", {}).get("env", {})
            if isinstance(env_block, dict):
                return str(env_block.get("WILLOW_AGENT_NAME", "")).strip()
    except Exception:
        pass
    return ""


def collect_identity_matrix(repo: Path | None = None) -> dict:
    """Snapshot of identity signals for fleet_identity_status / agents check."""
    root = repo or repo_root()
    active = read_active_agent(root)
    process_agent = expected_agent_id()
    cursor_mcp = _cursor_mcp_agent(root)
    persona = _read_persona_overlay()
    disk_mcp = load_mcp_env(root, active) if active else load_mcp_env(root)
    disk_agent = disk_mcp.get("WILLOW_AGENT_NAME", "").strip()
    disk_grove = disk_mcp.get("GROVE_SENDER", "").strip()
    shell_grove = os.environ.get("GROVE_SENDER", "").strip()

    try:
        hook_agent = resolve_agent_name(root)
    except EnvironmentError:
        hook_agent = ""

    signals = {
        "active_agent": active,
        "mcp_env_WILLOW_AGENT_NAME": process_agent,
        "mcp_disk_WILLOW_AGENT_NAME": disk_agent,
        "mcp_disk_GROVE_SENDER": disk_grove,
        "cursor_mcp_WILLOW_AGENT_NAME": cursor_mcp,
        "hook_resolve_agent_name": hook_agent,
        "persona_overlay": persona,
        "GROVE_SENDER": shell_grove,
        "identity_bind_mode": identity_bind_mode(),
    }

    canonical = active or disk_agent or cursor_mcp or process_agent or hook_agent
    drift: list[str] = []
    if active and disk_agent and active != disk_agent:
        drift.append(f"active-agent ({active}) != agents/.../mcp.json ({disk_agent})")
    if active and cursor_mcp and active != cursor_mcp:
        drift.append(f"active-agent ({active}) != .cursor/mcp.json ({cursor_mcp})")
    if disk_agent and cursor_mcp and disk_agent != cursor_mcp:
        drift.append(f"agents/.../mcp.json ({disk_agent}) != .cursor/mcp.json ({cursor_mcp})")
    if hook_agent and active and hook_agent != active:
        drift.append(f"hook resolution ({hook_agent}) != active-agent ({active})")
    if disk_agent and disk_grove and disk_grove != disk_agent:
        drift.append(
            f"MCP config GROVE_SENDER ({disk_grove}) != WILLOW_AGENT_NAME ({disk_agent})"
        )
    if (
        process_agent
        and disk_agent
        and process_agent != disk_agent
        and os.environ.get("WILLOW_AGENT_NAME", "").strip()
    ):
        if active and active == disk_agent:
            signals["shell_agent_stale"] = (
                f"shell WILLOW_AGENT_NAME ({process_agent}) != active-agent ({active}) "
                f"— update $WILLOW_HOME/env or run: "
                f"./willow.sh agents active {active} --install"
            )
        else:
            drift.append(
                f"shell WILLOW_AGENT_NAME ({process_agent}) != MCP on disk ({disk_agent})"
            )

    signals["coherent"] = len(drift) == 0
    signals["drift"] = drift
    signals["canonical_agent"] = canonical
    if shell_grove and disk_grove and shell_grove != disk_grove:
        signals["shell_grove_stale"] = (
            f"shell GROVE_SENDER ({shell_grove}) != MCP on disk ({disk_grove}) "
            f"— run ./willow.sh agents install {disk_grove or active} --ide all "
            f"or unset GROVE_SENDER in your profile"
        )
    return signals


def drift_lines(repo: Path | None = None, intended_agent: str = "") -> list[str]:
    """Human-readable drift for CLI warnings."""
    matrix = collect_identity_matrix(repo)
    lines = list(matrix.get("drift") or [])
    agent = intended_agent.strip() or matrix.get("canonical_agent") or ""
    if agent and matrix.get("active_agent") == agent and lines:
        return lines
    if agent and matrix.get("active_agent") != agent:
        lines.insert(0, f"active-agent is {matrix.get('active_agent')!r}, expected {agent!r}")
    return lines
