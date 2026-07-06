# core/boot_gate.py — shared boot-sentinel check. b17: BTGT0  ΔΣ=42
"""
Shared boot-sentinel logic used by both the PreToolUse hook
(willow/fylgja/events/pre_tool.py, IDE built-in tools) and the MCP server
(sap/sap_mcp.py, agent_task_submit / Kart) so the boot gate applies
regardless of which path a caller uses to do real work.

Boot is two-phase:
  1. persona_done — persona confirmed; file reads for contract/persona boot;
     MCP + Kart unlock.
  2. boot_done — full /boot ritual complete; all IDE tools unlock.

PreToolUse never fires for mcp__willow__* tool calls (Claude Code hook
matchers are scoped to IDE built-in tools), so agent_task_submit() calls
is_persona_ready() / is_booted() directly rather than relying on the hook.
"""
from __future__ import annotations

import os
from pathlib import Path

from core.agent_identity import require_agent_name


def _session_suffix(session_id: str) -> str:
    return "".join(
        c for c in (session_id or "") if c.isalnum() or c in "_-"
    )[:16]


def _flag_path(prefix: str, agent: str | None, session_id: str) -> Path:
    agent = agent or require_agent_name()
    sid = _session_suffix(session_id)
    if sid:
        return Path(f"/tmp/willow-{prefix}-{agent}-{sid}.flag")
    return Path(f"/tmp/willow-{prefix}-{agent}.flag")


def boot_done_path(agent: str | None = None, session_id: str = "") -> Path:
    """Final boot sentinel — all tools unlocked."""
    return _flag_path("boot-done", agent, session_id)


def persona_done_path(agent: str | None = None, session_id: str = "") -> Path:
    """Persona confirmed — MCP/Kart unlock; IDE writes still gated until boot_done."""
    return _flag_path("persona-done", agent, session_id)


def _any_session_flag(prefix: str, agent: str) -> bool:
    legacy = Path(f"/tmp/willow-{prefix}-{agent}.flag")
    if legacy.exists():
        return True
    return any(Path("/tmp").glob(f"willow-{prefix}-{agent}-*.flag"))


def is_booted(agent: str | None = None, session_id: str = "") -> bool:
    """True once the final boot sentinel exists, or under pytest."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    if session_id:
        return boot_done_path(agent, session_id).exists()
    if boot_done_path(agent).exists():
        return True
    name = agent or require_agent_name()
    return _any_session_flag("boot-done", name)


def is_persona_ready(agent: str | None = None, session_id: str = "") -> bool:
    """True once persona is confirmed for this session (MCP/Kart may run)."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    if session_id:
        return persona_done_path(agent, session_id).exists()
    if persona_done_path(agent).exists():
        return True
    name = agent or require_agent_name()
    return _any_session_flag("persona-done", name)


def mark_persona_ready(agent: str | None = None, session_id: str = "") -> bool:
    """Write persona-done sentinel (host hook or agent Write)."""
    p = persona_done_path(agent, session_id)
    try:
        p.write_text("persona-ready\n", encoding="utf-8")
        return True
    except OSError:
        return False


def clear_session_boot_flags(agent: str | None, session_id: str) -> None:
    """Fresh session: clear this session's persona + boot flags and legacy shared flags."""
    import time as _t

    agent = agent or require_agent_name()
    persona_done_path(agent, session_id).unlink(missing_ok=True)
    boot_done_path(agent, session_id).unlink(missing_ok=True)
    Path(f"/tmp/willow-persona-done-{agent}.flag").unlink(missing_ok=True)
    Path(f"/tmp/willow-boot-done-{agent}.flag").unlink(missing_ok=True)
    cutoff = _t.time() - 48 * 3600
    for pattern in (f"willow-persona-done-{agent}-*.flag", f"willow-boot-done-{agent}-*.flag"):
        for p in Path("/tmp").glob(pattern):
            try:
                if p.stat().st_mtime < cutoff:
                    p.unlink()
            except OSError:
                pass


def repo_root() -> Path:
    try:
        from willow.fylgja.project_env import repo_root as _rr

        return _rr()
    except Exception:
        return Path(__file__).resolve().parent.parent


def boot_md_path() -> Path:
    return repo_root() / "willow" / "fylgja" / "skills" / "boot.md"


def is_persona_phase_read(file_path: str) -> bool:
    """Reads allowed before persona_done: boot.md, willow.md, persona + *-boot overlays."""
    if not file_path:
        return False
    try:
        p = Path(file_path).expanduser().resolve()
    except OSError:
        return False
    root = repo_root().resolve()
    try:
        p.relative_to(root)
    except ValueError:
        return p == boot_md_path().resolve()
    if p == boot_md_path().resolve():
        return True
    if p == (root / "willow.md").resolve():
        return True
    skills = root / "willow" / "fylgja" / "skills"
    if p.parent == skills and p.name.endswith("-boot.md"):
        return True
    personas = root / "willow" / "fylgja" / "personas"
    if p.parent == personas and p.suffix == ".md":
        return True
    return False


def norm_flag_target(file_path: str) -> str:
    if not file_path:
        return ""
    return str(Path(file_path).expanduser())


def paths_equal(a: str, b: str) -> bool:
    if not a or not b:
        return False
    try:
        return Path(a).expanduser().resolve() == Path(b).expanduser().resolve()
    except OSError:
        return a == b
