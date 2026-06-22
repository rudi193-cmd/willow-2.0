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
from willow.fylgja.identity_bind import collect_identity_matrix, drift_lines
from willow.fylgja.project_env import (
    list_agent_identities,
    read_active_agent,
    repo_root,
    sync_fleet_env_agent,
    write_active_agent,
)

_CHECK_IDES = ("cursor", "claude", "codex")


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


def _surface_matches_canonical(link: Path, canonical: Path) -> bool:
    if link.is_symlink():
        return link.resolve() == canonical.resolve()
    if not link.is_file() or not canonical.is_file():
        return False
    try:
        return link.read_text(encoding="utf-8") == canonical.read_text(encoding="utf-8")
    except Exception:
        return False


def _codex_has_willow_mcp(root: Path | None = None) -> bool:
    targets: list[Path] = []
    if root is not None:
        targets.append(root / ".codex" / "config.toml")
    targets.append(Path.home() / ".codex" / "config.toml")
    for target in targets:
        if not target.is_file():
            continue
        text = target.read_text(encoding="utf-8")
        if (
            "mcp_servers.willow" in text
            and "unified_mcp.sh" in text
            and "{{" not in text
        ):
            return True
    return False


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


def cmd_active(root: Path, agent: str, *, install: bool = False) -> int:
    if agent not in list_agent_identities(root):
        print(f"Unknown agent {agent!r} — no agents/{agent}/config/identity.json")
        return 1
    write_active_agent(root, agent)
    if sync_fleet_env_agent(agent, root):
        print(f"Fleet env WILLOW_AGENT_NAME → {agent}")
    print(f"Active agent → {agent}")
    if install:
        install_project(agent_name=agent, ides=["all"], package_root=root, dry_run=False)
        matrix = collect_identity_matrix(root)
        if matrix.get("coherent"):
            print("Identity matrix: coherent")
        else:
            print("Identity matrix — remaining drift:")
            for line in matrix.get("drift") or []:
                print(f"  · {line}")
        return 0

    drift = drift_lines(root, agent)
    if drift:
        print("WARNING — identity drift (MCP env may not match active-agent):")
        for line in drift:
            print(f"  · {line}")
        print(f"Fix: ./willow.sh agents install {agent} --ide all")
        print("     or: ./willow.sh agents active {agent} --install")
    else:
        print(
            f"Identity OK — run install if IDE wiring changed: "
            f"./willow.sh agents install {agent} --ide all"
        )
    return 0


def cmd_install(agent: str, ides: list[str], dry_run: bool, root: Path) -> int:
    active = read_active_agent(root)
    if active and active != agent and not dry_run:
        print(
            f"WARNING: installing {agent!r} but active-agent is {active!r} "
            f"— install updates .cursor/mcp.json and identity for {agent}"
        )
    install_project(agent_name=agent, ides=ides, package_root=root, dry_run=dry_run)
    if not dry_run:
        matrix = collect_identity_matrix(root)
        if not matrix.get("coherent"):
            print("Post-install drift:")
            for line in matrix.get("drift") or []:
                print(f"  · {line}")
    return 0


def cmd_sync_manifests(force: bool, sign: bool, agent: str | None) -> int:
    """Write SAFE agent manifests under ~/SAFE/Agents/."""
    from core.safe_agents import AGENTS_ROOT, FLEET_AGENTS, write_manifest, sync_all

    if agent:
        aid = agent.strip().lower()
        if aid not in FLEET_AGENTS:
            print(f"Unknown agent {aid!r} — add to core/safe_agents.py FLEET_AGENTS first.")
            return 1
        r = write_manifest(aid, force=force, sign=sign)
        print(json.dumps(r, indent=2))
        return 0 if r.get("status") in ("written", "skipped") else 1

    summary = sync_all(force=force, sign=sign)
    print(f"SAFE/Agents root: {AGENTS_ROOT}")
    print(f"Written: {summary['written']}  Skipped: {summary['skipped']}")
    for r in summary["results"]:
        if r.get("status") == "written":
            sig = "signed" if r.get("signed") else f"unsigned ({r.get('sign_detail', '')})"
            print(f"  + {r['agent_id']}: {r['permission_count']} groups — {sig}")
    return 0


def cmd_check(root: Path, ides: list[str] | None = None) -> int:
    selected = (
        list(_CHECK_IDES)
        if not ides or ides == ["all"]
        else [i.strip().lower() for i in ides if i.strip()]
    )
    for ide in selected:
        if ide not in _CHECK_IDES:
            raise ValueError(f"Unknown IDE {ide!r} — choose from {_CHECK_IDES}")

    issues: list[str] = []
    active = read_active_agent(root)
    agents = list_agent_identities(root)

    if not agents:
        issues.append("No repo agents — create agents/<id>/config/identity.json")
    if not active:
        issues.append("No active agent — run: ./willow.sh agents active <id>")

    if active:
        mcp = root / "agents" / active / "config" / "mcp.json"
        if not mcp.is_file():
            issues.append(f"Missing {mcp.relative_to(root)}")
        elif mcp.is_file():
            try:
                env = json.loads(mcp.read_text(encoding="utf-8"))["mcpServers"]["willow"]["env"]
                for key in ("GROVE_SENDER", "GROVE_NAME"):
                    if env.get(key) != active:
                        issues.append(
                            f"{mcp.relative_to(root)} missing {key}={active!r} "
                            f"— run: ./willow.sh agents install {active} --ide all"
                        )
            except Exception:
                issues.append(f"Could not parse Grove fields in {mcp.relative_to(root)}")

    if "cursor" in selected:
        hooks = root / ".cursor" / "hooks.json"
        cli = root / ".cursor" / "cli.json"
        if not _surface_matches_canonical(hooks, root / "willow" / "fylgja" / "config" / "cursor-hooks.json"):
            issues.append(
                ".cursor/hooks.json missing or stale — run: python3 scripts/sync_remote_cursor_surface.py"
            )
        if not _surface_matches_canonical(cli, root / "willow" / "fylgja" / "config" / "cursor-cli.json"):
            issues.append(
                ".cursor/cli.json missing or stale — run: python3 scripts/sync_remote_cursor_surface.py"
            )
        if not (root / ".cursor" / "skills").is_dir():
            issues.append(".cursor/skills missing — run: python3 scripts/sync_remote_cursor_surface.py")

    if "claude" in selected:
        stale = _project_claude_stale_hooks(root)
        if stale:
            issues.append("Project .claude/settings.json has stale hooks (blocks Fylgja):")
            issues.extend(f"  · {s}" for s in stale)

        if not _global_claude_has_fylgja_pre_tool():
            issues.append(
                "~/.claude/settings.json missing Fylgja PreToolUse — "
                "run: ./willow.sh agents install <agent> --ide claude"
            )

        issues.extend(check_claude_plugin_layout(root))

    if "codex" in selected and not _codex_has_willow_mcp(root):
        issues.append(
            "Codex MCP missing Willow fragment — run: ./willow.sh agents install <agent> --ide codex "
            "or: python3 scripts/sync_remote_cursor_surface.py"
        )

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

    matrix = collect_identity_matrix(root)
    for line in matrix.get("drift") or []:
        issues.append(f"identity drift: {line}")

    if issues:
        print("MCP enforcement check — ISSUES:")
        for item in issues:
            print(f"  · {item}")
        return 1

    print("MCP enforcement check — OK")
    print(f"  active agent: {active}")
    print(f"  surfaces: {', '.join(selected)}")
    print("  pre_tool blocks: PYTHONPATH=, python -m willow/sap/core, inline core imports")
    print("  session anchor injects [MCP-FIRST] each SessionStart")
    print("  Kart sandbox: willow/fylgja/config/kart-sandbox.json (worktrees auto-bound)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="./willow.sh agents",
        description="Repo agent identity, IDE wiring, MCP enforcement health",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List repo agents and active agent")

    p_active = sub.add_parser("active", help="Set .willow/active-agent")
    p_active.add_argument("agent", help="Agent id (e.g. hanuman)")
    p_active.add_argument(
        "--install",
        action="store_true",
        help="Run install --ide all immediately after setting active agent",
    )

    p_install = sub.add_parser("install", help="Wire IDE + MCP for an agent")
    p_install.add_argument("agent", help="Agent id")
    p_install.add_argument(
        "--ide",
        default="all",
        help="cursor,claude,codex or all (default: all)",
    )
    p_install.add_argument("--dry-run", action="store_true")

    p_check = sub.add_parser("check", help="Verify hooks, MCP config, enforcement rails")
    p_check.add_argument(
        "--ide",
        default="all",
        help="cursor,claude,codex or all (default: all)",
    )

    p_sync = sub.add_parser(
        "sync-manifests",
        help="Write safe-app-manifest.json under ~/SAFE/Agents/ from trust tiers",
    )
    p_sync.add_argument("agent", nargs="?", help="Single agent id (default: full fleet)")
    p_sync.add_argument("--force", action="store_true", help="Overwrite existing manifests")
    p_sync.add_argument("--no-sign", action="store_true", help="Skip gpg detach-sign")

    args = parser.parse_args(argv)
    root = repo_root()

    if args.command == "list":
        return cmd_list(root)
    if args.command == "active":
        return cmd_active(root, args.agent.strip(), install=args.install)
    if args.command == "install":
        ides = ["all"] if args.ide.strip().lower() == "all" else [
            x.strip() for x in args.ide.split(",") if x.strip()
        ]
        return cmd_install(args.agent.strip(), ides, args.dry_run, root)
    if args.command == "check":
        ides = ["all"] if args.ide.strip().lower() == "all" else [
            x.strip() for x in args.ide.split(",") if x.strip()
        ]
        try:
            return cmd_check(root, ides=ides)
        except ValueError as e:
            print(str(e))
            return 1
    if args.command == "sync-manifests":
        return cmd_sync_manifests(
            force=args.force,
            sign=not args.no_sign,
            agent=getattr(args, "agent", None),
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
