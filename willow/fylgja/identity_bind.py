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
    path = Path.home() / ".willow" / "willow-2.0-active-persona"
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
    mcp_env = expected_agent_id()
    cursor_mcp = _cursor_mcp_agent(root)
    persona = _read_persona_overlay()

    try:
        hook_agent = resolve_agent_name(root)
    except EnvironmentError:
        hook_agent = ""

    signals = {
        "active_agent": active,
        "mcp_env_WILLOW_AGENT_NAME": mcp_env,
        "cursor_mcp_WILLOW_AGENT_NAME": cursor_mcp,
        "hook_resolve_agent_name": hook_agent,
        "persona_overlay": persona,
        "GROVE_SENDER": os.environ.get("GROVE_SENDER", "").strip(),
        "identity_bind_mode": identity_bind_mode(),
    }

    canonical = active or mcp_env or hook_agent
    drift: list[str] = []
    if active and mcp_env and active != mcp_env:
        drift.append(f"active-agent ({active}) != MCP env ({mcp_env})")
    if active and cursor_mcp and active != cursor_mcp:
        drift.append(f"active-agent ({active}) != .cursor/mcp.json ({cursor_mcp})")
    if mcp_env and cursor_mcp and mcp_env != cursor_mcp:
        drift.append(f"MCP process env ({mcp_env}) != .cursor/mcp.json ({cursor_mcp})")
    if hook_agent and active and hook_agent != active:
        drift.append(f"hook resolution ({hook_agent}) != active-agent ({active})")
    grove_sender = signals["GROVE_SENDER"]
    if mcp_env and grove_sender and grove_sender != mcp_env:
        drift.append(f"GROVE_SENDER ({grove_sender}) != WILLOW_AGENT_NAME ({mcp_env})")

    signals["coherent"] = len(drift) == 0
    signals["drift"] = drift
    signals["canonical_agent"] = canonical
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
