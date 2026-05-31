"""
install_project.py — Unified IDE wiring for Willow Fylgja.

Run:
  python3 -m willow.fylgja.install_project hanuman --ide all
  python3 -m willow.fylgja.install_project hanuman --ide cursor,claude,codex
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from willow.fylgja.project_env import (
    agent_config_dir,
    hook_python_command,
    repo_root,
    write_active_agent,
)

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent
_ALL_IDES = ("cursor", "claude", "codex")


def _default_paths(repo: Path) -> dict[str, str]:
    home = Path.home()
    return {
        "REPO_ROOT": str(repo.resolve()),
        "AGENT_NAME": "",  # filled per call
        "GROVE_ROOT": str(home / "github" / "safe-app-willow-grove"),
        "SAFE_ROOT": str(home / "github" / "SAFE" / "Applications"),
        "AGENTS_ROOT": str(home / "github" / "SAFE" / "Agents"),
        "WILLOW_HOME": str(home / "github" / ".willow"),
    }


def _render_template(text: str, values: dict[str, str]) -> str:
    out = text
    for key, val in values.items():
        out = out.replace(f"{{{{{key}}}}}", val)
    return out


def _write_json(path: Path, data: dict, dry_run: bool) -> None:
    if dry_run:
        print(f"[install_project] Would write {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    print(f"[install_project] Wrote {path}")


def _write_text(path: Path, text: str, dry_run: bool) -> None:
    if dry_run:
        print(f"[install_project] Would write {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    print(f"[install_project] Wrote {path}")


def _merge_existing_mcp_env(existing_path: Path) -> dict:
    if not existing_path.is_file():
        return {}
    try:
        data = json.loads(existing_path.read_text(encoding="utf-8"))
        env = data.get("mcpServers", {}).get("willow", {}).get("env", {})
        return env if isinstance(env, dict) else {}
    except Exception:
        return {}


def render_mcp_config(agent: str, package_root: Path | None = None) -> dict:
    root = package_root or repo_root()
    template_path = root / "willow" / "fylgja" / "config" / "mcp.template.json"
    template = template_path.read_text(encoding="utf-8")
    values = _default_paths(root)
    values["AGENT_NAME"] = agent

    rendered = _render_template(template, values)
    config = json.loads(rendered)

    # Preserve operator secrets and extra env from existing MCP configs
    dest = agent_config_dir(root, agent) / "mcp.json"
    preserve_keys = ("GROQ_API_KEY", "WILLOW_INFERENCE_PROVIDER", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY")
    for path in (dest, root / ".mcp.json", Path.home() / ".willow" / "mcp.json"):
        for k, v in _merge_existing_mcp_env(path).items():
            if not isinstance(v, str):
                continue
            if k in preserve_keys or not k.startswith("WILLOW_"):
                config["mcpServers"]["willow"]["env"][k] = v

    # Merge non-willow servers from an existing root .mcp.json file
    root_mcp = root / ".mcp.json"
    if root_mcp.is_file() and not root_mcp.is_symlink():
        try:
            existing = json.loads(root_mcp.read_text(encoding="utf-8"))
            for name, server in existing.get("mcpServers", {}).items():
                if name != "willow":
                    config["mcpServers"].setdefault(name, server)
        except Exception:
            pass

    return config


def write_agent_identity(agent: str, package_root: Path, dry_run: bool) -> None:
    cfg = agent_config_dir(package_root, agent)
    identity = {
        "WILLOW_AGENT_NAME": agent,
        "AGENT_NAME": agent,
    }
    _write_json(cfg / "identity.json", identity, dry_run)
    if not dry_run:
        write_active_agent(package_root, agent)


def write_agent_mcp(agent: str, package_root: Path, dry_run: bool) -> None:
    cfg = agent_config_dir(package_root, agent)
    _write_json(cfg / "mcp.json", render_mcp_config(agent, package_root), dry_run)


def fleet_home() -> Path:
    return Path(os.environ.get("WILLOW_HOME", str(Path.home() / "github" / ".willow")))


def canonical_local_settings(agent: str) -> Path:
    """Per-agent IDE local settings live under WILLOW_HOME, not in the repo."""
    return fleet_home() / "agents" / agent.strip().lower() / "settings.local.json"


def ensure_canonical_local_settings(agent: str, package_root: Path, dry_run: bool) -> Path:
    """Create or patch WILLOW_HOME/agents/<agent>/settings.local.json from repo template."""
    canon = canonical_local_settings(agent)
    template = package_root / "willow" / "fylgja" / "config" / "settings.local.json"
    if dry_run:
        print(f"[install_project] Would ensure canonical {canon}")
        return canon
    canon.parent.mkdir(parents=True, exist_ok=True)
    if canon.is_file():
        try:
            data = json.loads(canon.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    elif template.is_file():
        data = json.loads(template.read_text(encoding="utf-8"))
    else:
        data = {}
    env = data.setdefault("env", {})
    if not isinstance(env, dict):
        env = {}
        data["env"] = env
    env["WILLOW_AGENT_NAME"] = agent
    env["AGENT_NAME"] = agent
    tmp = canon.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(canon)
    print(f"[install_project] Canonical local settings → {canon}")
    return canon


def _symlink_to(link: Path, target: Path, dry_run: bool) -> None:
    if dry_run:
        print(f"[install_project] Would symlink {link} → {target}")
        return
    link.parent.mkdir(parents=True, exist_ok=True)
    dest = target.resolve() if target.is_absolute() else (link.parent / target).resolve()
    rel = os.path.relpath(dest, start=link.parent.resolve())
    if link.exists() or link.is_symlink():
        if link.is_symlink() and link.resolve() == dest:
            return
        link.unlink()
    link.symlink_to(rel)
    print(f"[install_project] Symlinked {link} → {dest}")


def install_cursor(agent: str, package_root: Path, dry_run: bool) -> None:
    _symlink_to(
        package_root / ".cursor" / "hooks.json",
        Path("..") / "willow" / "fylgja" / "config" / "cursor-hooks.json",
        dry_run,
    )
    _symlink_to(
        package_root / ".cursor" / "cli.json",
        Path("..") / "willow" / "fylgja" / "config" / "cursor-cli.json",
        dry_run,
    )
    _symlink_to(
        package_root / ".cursor" / "mcp.json",
        Path("..") / "agents" / agent / "config" / "mcp.json",
        dry_run,
    )
    canon = ensure_canonical_local_settings(agent, package_root, dry_run)
    _symlink_to(package_root / ".cursor" / "settings.local.json", canon, dry_run)


def install_claude_project(agent: str, package_root: Path, dry_run: bool) -> None:
    _symlink_to(
        package_root / ".claude" / "settings.json",
        Path("..") / "willow" / "fylgja" / "config" / "claude-settings.json",
        dry_run,
    )
    canon = ensure_canonical_local_settings(agent, package_root, dry_run)
    _symlink_to(package_root / ".claude" / "settings.local.json", canon, dry_run)


def install_claude_global(agent: str, package_root: Path, dry_run: bool) -> None:
    from willow.fylgja.claude_plugin import ensure_claude_plugin_layout
    from willow.fylgja.install import apply_hooks, apply_plugin

    settings = Path.home() / ".claude" / "settings.json"
    if dry_run:
        print(f"[install_project] Would wire Fylgja hooks into {settings}")
        for action in ensure_claude_plugin_layout(package_root, dry_run=True):
            print(f"[install_project] {action}")
        return
    settings.parent.mkdir(parents=True, exist_ok=True)
    if not settings.exists():
        settings.write_text("{}\n", encoding="utf-8")
    for action in ensure_claude_plugin_layout(package_root, dry_run=False):
        print(f"[install_project] {action}")
    apply_hooks(settings_path=settings, package_root=package_root, dry_run=False)
    apply_plugin(settings_path=settings, dry_run=False)


def _parse_toml_tables(text: str) -> dict[str, dict[str, str | list[str]]]:
    """Minimal TOML parser for [table] and key = value / key = ['a']."""
    tables: dict[str, dict] = {}
    current: str | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^\[([^\]]+)\]$", line)
        if m:
            current = m.group(1)
            tables.setdefault(current, {})
            continue
        if current is None or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            if inner.startswith('"') and inner.endswith('"'):
                tables[current][key] = [inner[1:-1]]
            else:
                parts = [p.strip().strip('"') for p in inner.split(",") if p.strip()]
                tables[current][key] = parts
        elif val.startswith('"') and val.endswith('"'):
            tables[current][key] = val[1:-1]
        else:
            tables[current][key] = val
    return tables


def _dump_toml_tables(tables: dict[str, dict]) -> str:
    lines: list[str] = []
    for name in sorted(tables.keys()):
        lines.append(f"[{name}]")
        for key, val in tables[name].items():
            if isinstance(val, list):
                quoted = ", ".join(json.dumps(v) for v in val)
                lines.append(f"{key} = [{quoted}]")
            elif isinstance(val, str):
                lines.append(f"{key} = {json.dumps(val)}")
            else:
                lines.append(f"{key} = {val}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def install_codex(agent: str, package_root: Path, dry_run: bool) -> None:
    target = Path.home() / ".codex" / "config.toml"
    template_path = package_root / "willow" / "fylgja" / "config" / "codex-mcp.toml.template"
    values = _default_paths(package_root)
    values["AGENT_NAME"] = agent
    fragment = _render_template(template_path.read_text(encoding="utf-8"), values)

    existing = target.read_text(encoding="utf-8") if target.is_file() else ""
    tables = _parse_toml_tables(existing)
    frag_tables = _parse_toml_tables(fragment)
    tables.update(frag_tables)
    merged = _dump_toml_tables(tables)

    if dry_run:
        print(f"[install_project] Would merge Willow MCP into {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    _write_text(target, merged, dry_run=False)


def install_root_mcp_symlink(agent: str, package_root: Path, dry_run: bool) -> None:
    _symlink_to(
        package_root / ".mcp.json",
        Path("agents") / agent / "config" / "mcp.json",
        dry_run,
    )


def install_project(
    agent_name: str,
    ides: list[str] | None = None,
    package_root: Path | None = None,
    dry_run: bool = False,
    claude_global: bool = True,
    set_fleet_default: bool = False,
) -> None:
    root = package_root or repo_root()
    agent = agent_name.strip()
    if not agent:
        raise ValueError("agent name required")

    selected = list(_ALL_IDES) if not ides or ides == ["all"] else [i.strip().lower() for i in ides]
    for ide in selected:
        if ide not in _ALL_IDES:
            raise ValueError(f"Unknown IDE {ide!r} — choose from {_ALL_IDES}")

    write_agent_identity(agent, root, dry_run)
    write_agent_mcp(agent, root, dry_run)
    install_root_mcp_symlink(agent, root, dry_run)

    if "cursor" in selected:
        install_cursor(agent, root, dry_run)
    if "claude" in selected:
        install_claude_project(agent, root, dry_run)
        if claude_global:
            install_claude_global(agent, root, dry_run)
    if "codex" in selected:
        install_codex(agent, root, dry_run)

    if not dry_run:
        from willow.fylgja.link_fleet_home import link_fleet_home

        link_fleet_home(package_root=root)
        from willow.fylgja.global_settings import init_global_settings, load_global_settings

        if set_fleet_default:
            p = init_global_settings(default_agent=agent, force=True)
            print(f"[install_project] Fleet default_agent → {agent} ({p})")
        else:
            load_global_settings(create=True)
            print(
                f"[install_project] Active IDE agent → {agent} "
                f"(repo .willow/active-agent). fleet.default_agent unchanged."
            )

    # Ensure hook script is executable
    hook = root / "willow" / "fylgja" / "bin" / "fylgja-hook"
    if not dry_run and hook.is_file():
        hook.chmod(hook.stat().st_mode | 0o111)


def build_claude_hooks_block(package_root: Path) -> dict:
    """Claude global hooks using unified hook runner (absolute paths for ~/.claude)."""

    def cmd(m):
        return hook_python_command(package_root, "claude", m)

    return {
        "SessionStart": [
            {"hooks": [{"type": "command", "command": cmd("session_start"),
                        "timeout": 15, "statusMessage": "Building session index..."}]}
        ],
        "PreToolUse": [
            {"matcher": "Bash",
             "hooks": [{"type": "command", "command": cmd("pre_tool"), "timeout": 5}]},
            {"matcher": "Agent",
             "hooks": [{"type": "command", "command": cmd("pre_tool"), "timeout": 5}]},
            {"matcher": "Read",
             "hooks": [{"type": "command", "command": cmd("pre_tool"), "timeout": 5}]},
            {"matcher": "mcp__willow__soil_put|mcp__willow__soil_update|mcp__willow__kb_ingest|mcp__willow__mem_ratify",
             "hooks": [{"type": "command", "command": cmd("pre_tool"), "timeout": 5}]},
        ],
        "UserPromptSubmit": [
            {"hooks": [{"type": "command", "command": cmd("prompt_submit"), "timeout": 10}]}
        ],
        "PostToolUse": [
            {"matcher": "ToolSearch",
             "hooks": [{"type": "command", "command": cmd("post_tool"), "timeout": 5}]},
            {"matcher": "mcp__willow__agent_task_submit",
             "hooks": [{"type": "command", "command": cmd("post_tool"), "timeout": 5}]},
        ],
        "Stop": [
            {"hooks": [{"type": "command", "command": cmd("stop"), "timeout": 30,
                        "statusMessage": "Composting session..."}]}
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified Willow Fylgja IDE install")
    parser.add_argument("agent", help="Agent id (e.g. hanuman)")
    parser.add_argument(
        "--ide",
        default="all",
        help="Comma-separated: cursor,claude,codex or all (default: all)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--package-root", type=Path, default=None)
    parser.add_argument("--no-claude-global", action="store_true",
                        help="Skip wiring ~/.claude/settings.json")
    parser.add_argument(
        "--set-fleet-default",
        action="store_true",
        help="Also set settings.global.json fleet.default_agent (usually leave unset)",
    )
    args = parser.parse_args()

    ides = ["all"] if args.ide.strip().lower() == "all" else [x.strip() for x in args.ide.split(",")]
    install_project(
        agent_name=args.agent,
        ides=ides,
        package_root=args.package_root,
        dry_run=args.dry_run,
        claude_global=not args.no_claude_global,
        set_fleet_default=args.set_fleet_default,
    )


if __name__ == "__main__":
    main()
