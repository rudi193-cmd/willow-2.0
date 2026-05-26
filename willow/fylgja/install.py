"""
install.py — Wire Fylgja into Claude Code settings.json.
Run: python3 -m willow.fylgja.install [--dry-run] [--settings PATH]
"""
import argparse
import json
import shlex
import sys
from pathlib import Path

_DEFAULT_SETTINGS = Path.home() / ".claude" / "settings.json"
_PACKAGE_ROOT = Path(__file__).parent.parent.parent  # willow-2.0/


def _event_command(package_root: Path, module: str) -> str:
    runner = package_root / "tools" / "run_fylgja_hook.py"
    venv_python = package_root / ".venv-dev" / "bin" / "python3"
    python = venv_python if venv_python.is_file() else Path(sys.executable)
    return (
        f"{shlex.quote(str(python))} "
        f"{shlex.quote(str(runner))} "
        f"willow.fylgja.events.{module}"
    )


def _is_fylgja_entry(entry: dict) -> bool:
    for hook in entry.get("hooks", []):
        command = str(hook.get("command", ""))
        if "run_fylgja_hook.py" in command or "willow.fylgja.events." in command:
            return True
    return False


def _merge_event_hooks(existing: list[dict], managed: list[dict]) -> list[dict]:
    preserved = [entry for entry in (existing or []) if not _is_fylgja_entry(entry)]
    return managed + preserved


def build_hooks_block(package_root: Path) -> dict:
    cmd = lambda m: _event_command(package_root, m)
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
             "hooks": [{"type": "command", "command": cmd("post_tool"), "timeout": 5}]}
        ],
        "Stop": [
            {"hooks": [{"type": "command", "command": cmd("stop"), "timeout": 30,
                        "statusMessage": "Composting session..."}]}
        ],
    }


def apply_hooks(settings_path: Path = _DEFAULT_SETTINGS,
                package_root: Path = _PACKAGE_ROOT,
                dry_run: bool = False) -> None:
    settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    managed_hooks = build_hooks_block(package_root)
    hooks = dict(settings.get("hooks", {}))
    for event_name, entries in managed_hooks.items():
        hooks[event_name] = _merge_event_hooks(hooks.get(event_name, []), entries)
    if dry_run:
        print("[install] Dry run — would write hooks block:")
        print(json.dumps(hooks, indent=2))
        return
    settings["hooks"] = hooks
    tmp = settings_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(settings, indent=2))
    tmp.replace(settings_path)
    print(f"[install] Hooks written to {settings_path}")


def apply_plugin(settings_path: Path = _DEFAULT_SETTINGS,
                 skills_path: Path = None,
                 dry_run: bool = False) -> None:
    if skills_path is None:
        skills_path = _PACKAGE_ROOT / "willow" / "fylgja" / "skills"
    plugin_key = f"fylgja@{skills_path}"
    settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}

    if dry_run:
        print(f"[install] Dry run — would add to enabledPlugins: {plugin_key!r}")
        return

    plugins = {
        key: value
        for key, value in settings.get("enabledPlugins", {}).items()
        if not str(key).startswith("fylgja@")
    }
    plugins[plugin_key] = True
    settings["enabledPlugins"] = plugins
    tmp = settings_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(settings, indent=2))
    tmp.replace(settings_path)
    print(f"[install] Plugin registered: {plugin_key}")


def install_project(
    agent_name: str,
    package_root: Path = _PACKAGE_ROOT,
    dry_run: bool = False,
) -> None:
    """Wire project-level settings: symlink .claude/settings.json and stamp agent identity.

    Creates:
      .claude/settings.json      → symlink to willow/fylgja/config/claude-settings.json
      .claude/settings.local.json → agent-specific env overrides (gitignored)
    """
    dot_claude = package_root / ".claude"
    dot_claude.mkdir(exist_ok=True)

    # Symlink .claude/settings.json → ../willow/fylgja/config/claude-settings.json
    settings_link = dot_claude / "settings.json"
    template = package_root / "willow" / "fylgja" / "config" / "claude-settings.json"
    rel_target = Path("..") / "willow" / "fylgja" / "config" / "claude-settings.json"

    if not template.exists():
        raise FileNotFoundError(f"Template not found: {template}")

    if dry_run:
        print(f"[install] Would symlink {settings_link} → {rel_target}")
    else:
        if settings_link.exists() or settings_link.is_symlink():
            settings_link.unlink()
        settings_link.symlink_to(rel_target)
        print(f"[install] Symlinked {settings_link} → {rel_target}")

    # Write .claude/settings.local.json with agent-specific env vars
    local_path = dot_claude / "settings.local.json"
    local = {"env": {"WILLOW_AGENT_NAME": agent_name, "AGENT_NAME": agent_name}}
    if dry_run:
        print(f"[install] Would write {local_path}: {json.dumps(local)}")
    else:
        tmp = local_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(local, indent=2))
        tmp.replace(local_path)
        print(f"[install] Agent identity written to {local_path}")


def main():
    parser = argparse.ArgumentParser(description="Wire Fylgja into Claude Code settings.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--settings", type=Path, default=_DEFAULT_SETTINGS)
    parser.add_argument("--package-root", type=Path, default=_PACKAGE_ROOT)
    parser.add_argument("--plugin", action="store_true", help="Also register fylgja@local plugin")
    parser.add_argument("--project", metavar="AGENT_NAME",
                        help="Wire project settings: symlink .claude/settings.json and stamp agent identity")
    args = parser.parse_args()
    apply_hooks(settings_path=args.settings, package_root=args.package_root, dry_run=args.dry_run)
    if args.plugin:
        apply_plugin(settings_path=args.settings, dry_run=args.dry_run)
    if args.project:
        install_project(agent_name=args.project, package_root=args.package_root, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
