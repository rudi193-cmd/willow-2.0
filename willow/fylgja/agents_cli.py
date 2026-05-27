"""
agents_cli.py — ./willow agents list|install|check|active

Operator surface for repo agent identity, IDE wiring, and MCP enforcement health.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from willow.fylgja.claude_plugin import check_claude_plugin_layout
from willow.fylgja.install_project import install_project
from willow.fylgja.project_env import (
    list_agent_identities,
    read_active_agent,
    repo_root,
    write_active_agent,
)


def _global_claude_has_fylgja_pre_tool() -> bool:
    settings = Path.home() / ".claude" / "settings.json"
    if not settings.is_file():
        return False
    try:
        data = json.loads(settings.read_text(encoding="utf-8"))
    except Exception:
        return False
    for entry in data.get("hooks", {}).get("PreToolUse", []):
        for hook in entry.get("hooks", []):
            cmd = str(hook.get("command", ""))
            if "pre_tool" in cmd and ("fylgja" in cmd or "hook_runner" in cmd):
                return True
    return False


def _project_claude_stale_hooks(root: Path) -> list[str]:
    """Return stale hook commands still present in project claude settings."""
    path = root / ".claude" / "settings.json"
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except Exception:
        return []
    stale: list[str] = []
    for event, entries in (data.get("hooks") or {}).items():
        for entry in entries:
            for hook in entry.get("hooks", []):
                cmd = str(hook.get("command", ""))
                if any(x in cmd for x in ("orchestrator.py", "session_close.py", "persona.py")):
                    stale.append(f"{event}: {cmd}")
    return stale


def cmd_list(root: Path) -> int:
    active = read_active_agent(root)
    agents = list_agent_identities(root)
    if not agents:
        print("No agents with agents/{id}/config/identity.json found.")
        return 1
    print(f"Active: {active or '(unset)'}")
    print("Repo agents:")
    for name in agents:
        mark = " *" if name == active else ""
        print(f"  {name}{mark}")
    return 0


def cmd_active(root: Path, agent: str) -> int:
    if agent not in list_agent_identities(root):
        print(f"Unknown agent {agent!r} — no agents/{agent}/config/identity.json")
        return 1
    write_active_agent(root, agent)
    print(f"Active agent → {agent}")
    print(f"Run: ./willow agents install {agent} --ide all")
    return 0


def cmd_install(agent: str, ides: list[str], dry_run: bool) -> int:
    install_project(agent_name=agent, ides=ides, dry_run=dry_run)
    return 0


def cmd_check(root: Path) -> int:
    issues: list[str] = []
    active = read_active_agent(root)
    agents = list_agent_identities(root)

    if not agents:
        issues.append("No repo agents — create agents/<id>/config/identity.json")
    if not active:
        issues.append("No active agent — run: ./willow agents active <id>")

    if active:
        mcp = root / "agents" / active / "config" / "mcp.json"
        if not mcp.is_file():
            issues.append(f"Missing {mcp.relative_to(root)}")

    cursor_hooks = root / ".cursor" / "hooks.json"
    if not cursor_hooks.is_symlink():
        issues.append(".cursor/hooks.json not symlinked — run install --ide cursor")

    stale = _project_claude_stale_hooks(root)
    if stale:
        issues.append("Project .claude/settings.json has stale hooks (blocks Fylgja):")
        issues.extend(f"  · {s}" for s in stale)

    if not _global_claude_has_fylgja_pre_tool():
        issues.append(
            "~/.claude/settings.json missing Fylgja PreToolUse — "
            "run: ./willow agents install <agent> --ide claude"
        )

    issues.extend(check_claude_plugin_layout(root))

    hook = root / "willow" / "fylgja" / "bin" / "fylgja-hook"
    if not hook.is_file():
        issues.append(f"Missing hook runner: {hook.relative_to(root)}")

    sandbox_cfg = root / "willow" / "fylgja" / "config" / "kart-sandbox.json"
    if not sandbox_cfg.is_file():
        issues.append(f"Missing Kart sandbox policy: {sandbox_cfg.relative_to(root)}")

    try:
        from core.kart_sandbox import bwrap_available

        if not bwrap_available():
            issues.append("bubblewrap (bwrap) not installed — Kart sandbox disabled")
    except Exception as e:
        issues.append(f"Kart sandbox import failed: {e}")

    if issues:
        print("MCP enforcement check — ISSUES:")
        for item in issues:
            print(f"  · {item}")
        return 1

    print("MCP enforcement check — OK")
    print(f"  active agent: {active}")
    print("  pre_tool blocks: PYTHONPATH=, python -m willow/sap/core, inline core imports")
    print("  session anchor injects [MCP-FIRST] each SessionStart")
    print("  Kart sandbox: willow/fylgja/config/kart-sandbox.json (worktrees auto-bound)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="./willow agents",
        description="Repo agent identity, IDE wiring, MCP enforcement health",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List repo agents and active agent")

    p_active = sub.add_parser("active", help="Set .willow/active-agent")
    p_active.add_argument("agent", help="Agent id (e.g. hanuman)")

    p_install = sub.add_parser("install", help="Wire IDE + MCP for an agent")
    p_install.add_argument("agent", help="Agent id")
    p_install.add_argument(
        "--ide",
        default="all",
        help="cursor,claude,codex or all (default: all)",
    )
    p_install.add_argument("--dry-run", action="store_true")

    sub.add_parser("check", help="Verify hooks, MCP config, enforcement rails")

    args = parser.parse_args(argv)
    root = repo_root()

    if args.command == "list":
        return cmd_list(root)
    if args.command == "active":
        return cmd_active(root, args.agent.strip())
    if args.command == "install":
        ides = ["all"] if args.ide.strip().lower() == "all" else [
            x.strip() for x in args.ide.split(",") if x.strip()
        ]
        return cmd_install(args.agent.strip(), ides, args.dry_run)
    if args.command == "check":
        return cmd_check(root)
    return 1


if __name__ == "__main__":
    sys.exit(main())
