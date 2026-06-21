"""
venv_cli.py — ./willow venv check|sync

Keep $WILLOW_HOME/venv aligned with willow-2.0/.venv-dev.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from willow.fylgja.fleet_venv import check_fleet_venv, sync_fleet_venv
from willow.fylgja.project_env import repo_root


def cmd_check(root: Path) -> int:
    status = check_fleet_venv(root)
    label = "OK" if status.ok else "FAIL"
    print(f"Fleet venv check — {label}")
    print(f"  fleet: {status.fleet_venv}")
    print(f"  dev:   {status.dev_venv}")
    print(f"  {status.detail}")
    return 0 if status.ok else 1


def cmd_sync(root: Path, *, dry_run: bool) -> int:
    try:
        status = sync_fleet_venv(root, dry_run=dry_run)
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"Fleet venv sync — FAIL\n  {exc}", file=sys.stderr)
        return 1
    print("Fleet venv sync — OK")
    print(f"  fleet: {status.fleet_venv}")
    print(f"  dev:   {status.dev_venv}")
    print(f"  {status.detail}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fleet Python venv under $WILLOW_HOME/venv")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="Verify fleet venv is usable")

    p_sync = sub.add_parser("sync", help="Symlink fleet venv to willow-2.0/.venv-dev")
    p_sync.add_argument("--dry-run", action="store_true")

    args = parser.parse_args(argv)
    root = repo_root()

    if args.command == "check":
        return cmd_check(root)
    if args.command == "sync":
        return cmd_sync(root, dry_run=args.dry_run)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
