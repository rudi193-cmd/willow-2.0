"""
install_cursor.py — Wire Fylgja into Cursor hooks.json.
Run: python3 -m willow.fylgja.install_cursor [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).parent.parent.parent
_DEFAULT_HOOKS = _PACKAGE_ROOT / ".cursor" / "hooks.json"


def _hook_command(package_root: Path, module: str) -> str:
    runner = package_root / "tools" / "run_cursor_hook.py"
    venv_python = package_root / ".venv-dev" / "bin" / "python3"
    python = venv_python if venv_python.is_file() else Path(sys.executable)
    return (
        f"{shlex.quote(str(python))} "
        f"{shlex.quote(str(runner))} "
        f"willow.fylgja.events.{module}"
    )


def _is_fylgja_entry(entry: dict) -> bool:
    command = str(entry.get("command", ""))
    return "run_cursor_hook.py" in command or "willow.fylgja.events." in command


def build_cursor_hooks_block(package_root: Path) -> dict:
    cmd = lambda m: _hook_command(package_root, m)
    return {
        "version": 1,
        "hooks": {
            "sessionStart": [
                {"command": cmd("session_start"), "timeout": 15},
            ],
            "beforeSubmitPrompt": [
                {"command": cmd("prompt_submit"), "timeout": 10},
            ],
            "beforeShellExecution": [
                {"command": cmd("pre_tool"), "timeout": 5},
            ],
            "beforeMCPExecution": [
                {"command": cmd("pre_tool"), "timeout": 5},
            ],
            "stop": [
                {"command": cmd("stop"), "timeout": 30},
            ],
        },
    }


def apply_cursor_hooks(
    hooks_path: Path = _DEFAULT_HOOKS,
    package_root: Path = _PACKAGE_ROOT,
    dry_run: bool = False,
) -> None:
    existing: dict = {}
    if hooks_path.exists():
        existing = json.loads(hooks_path.read_text(encoding="utf-8"))

    managed = build_cursor_hooks_block(package_root)
    merged_hooks: dict = dict(existing.get("hooks", {}))

    for event_name, entries in managed["hooks"].items():
        preserved = [e for e in merged_hooks.get(event_name, []) if not _is_fylgja_entry(e)]
        merged_hooks[event_name] = managed["hooks"][event_name] + preserved

    result = {"version": managed["version"], "hooks": merged_hooks}

    if dry_run:
        print("[install_cursor] Dry run — would write:")
        print(json.dumps(result, indent=2))
        return

    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = hooks_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, indent=2) + "\n")
    tmp.replace(hooks_path)
    print(f"[install_cursor] Hooks written to {hooks_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Wire Fylgja into Cursor hooks.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--hooks", type=Path, default=_DEFAULT_HOOKS)
    parser.add_argument("--package-root", type=Path, default=_PACKAGE_ROOT)
    args = parser.parse_args()
    apply_cursor_hooks(
        hooks_path=args.hooks,
        package_root=args.package_root,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
