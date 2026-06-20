"""
project_cli.py — ./willow project list|sync|check

Fleet workspace registry: MCP + hooks + identity + IDE env for out-of-tree repos.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from willow.fylgja.mcp_projects import (
    audit_all,
    ensure_registry,
    list_projects,
    registry_path,
    sync_all,
)
from willow.fylgja.project_env import repo_root


def cmd_list(root: Path) -> int:
    reg_path = registry_path(root)
    print(f"Registry: {reg_path}")
    for row in list_projects(package_root=root):
        servers = ", ".join(row["servers"])
        ides = ", ".join(row["ides"])
        wiring = row.get("wiring") or {}
        wiring_on = [k for k, v in wiring.items() if v]
        wiring_s = ", ".join(wiring_on) if wiring_on else "mcp-only"
        print(
            f"  {row['id']}: agent={row['agent']} profile={row['profile']} "
            f"servers=[{servers}] ides=[{ides}] wiring=[{wiring_s}]"
        )
        if row.get("note"):
            print(f"    {row['note']}")
        print(f"    path: {row['path']}")
    return 0


def cmd_sync(
    root: Path,
    *,
    project_ids: list[str] | None,
    dry_run: bool,
) -> int:
    ensure_registry(package_root=root, dry_run=dry_run)
    written = sync_all(package_root=root, project_ids=project_ids, dry_run=dry_run)
    print(f"[project] Synced {len(written)} project(s): {', '.join(written)}")
    return 0


def cmd_check(root: Path, *, project_ids: list[str] | None) -> int:
    ensure_registry(package_root=root, dry_run=False)
    issues = audit_all(package_root=root, project_ids=project_ids)
    if issues:
        print("Project registry check — DRIFT:")
        for item in issues:
            print(f"  · {item}")
        return 1
    print("Project registry check — OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="./willow.sh project",
        description="Fleet project registry — MCP + IDE wiring for out-of-tree workspaces",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List registered fleet workspaces")

    p_sync = sub.add_parser("sync", help="Materialize MCP + wiring for registry projects")
    p_sync.add_argument("projects", nargs="*", help="Project id(s); default all")
    p_sync.add_argument("--dry-run", action="store_true")

    p_check = sub.add_parser("check", help="Verify on-disk MCP + wiring match registry")
    p_check.add_argument("projects", nargs="*", help="Project id(s); default all")

    args = parser.parse_args(argv)
    root = repo_root()

    if args.command == "list":
        return cmd_list(root)
    if args.command == "sync":
        ids = list(args.projects) or None
        return cmd_sync(root, project_ids=ids, dry_run=args.dry_run)
    if args.command == "check":
        ids = list(args.projects) or None
        return cmd_check(root, project_ids=ids)
    return 1


if __name__ == "__main__":
    sys.exit(main())
