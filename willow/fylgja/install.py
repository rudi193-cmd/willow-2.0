"""
install.py — Wire Fylgja into Claude Code settings.json.
Run: python3 -m willow.fylgja.install [--dry-run] [--settings PATH]

Project wiring: python3 -m willow.fylgja.install_project <agent> --ide all
"""
import argparse
import json
from pathlib import Path

from willow.fylgja.install_project import build_claude_hooks_block, install_project as unified_install_project

_DEFAULT_SETTINGS = Path.home() / ".claude" / "settings.json"
_PACKAGE_ROOT = Path(__file__).parent.parent.parent


def _is_fylgja_entry(entry: dict) -> bool:
    for hook in entry.get("hooks", []):
        command = str(hook.get("command", ""))
        if any(x in command for x in (
            "run_fylgja_hook.py",
            "hook_runner",
            "fylgja-hook",
            "status_strip.py",
            "willow.fylgja.events.",
        )):
            return True
    return False


def _merge_event_hooks(existing: list[dict], managed: list[dict]) -> list[dict]:
    preserved = [entry for entry in (existing or []) if not _is_fylgja_entry(entry)]
    return managed + preserved


def build_hooks_block(package_root: Path) -> dict:
    return build_claude_hooks_block(package_root)


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


def main():
    parser = argparse.ArgumentParser(description="Wire Fylgja into Claude Code settings.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--settings", type=Path, default=_DEFAULT_SETTINGS)
    parser.add_argument("--package-root", type=Path, default=_PACKAGE_ROOT)
    parser.add_argument("--plugin", action="store_true", help="Also register fylgja@local plugin")
    parser.add_argument("--project", metavar="AGENT_NAME",
                        help="Wire all IDE project settings (alias for install_project --ide all)")
    args = parser.parse_args()
    apply_hooks(settings_path=args.settings, package_root=args.package_root, dry_run=args.dry_run)
    if args.plugin:
        apply_plugin(settings_path=args.settings, dry_run=args.dry_run)
    if args.project:
        unified_install_project(
            agent_name=args.project,
            ides=["all"],
            package_root=args.package_root,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
