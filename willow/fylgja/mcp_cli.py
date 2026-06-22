"""
mcp_cli.py — ./willow mcp list|init|sync|check|audit

Fleet MCP project registry: one source of truth → per-repo IDE configs.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from willow.fylgja.mcp_projects import (
    audit_all,
    ensure_registry,
    list_projects,
    registry_path,
    sync_all,
    unregistered_mcp_files,
)
from willow.fylgja.project_env import repo_root


def cmd_list(root: Path) -> int:
    reg_path = registry_path(root)
    print(f"Registry: {reg_path}")
    for row in list_projects(package_root=root):
        servers = ", ".join(row["servers"])
        ides = ", ".join(row["ides"])
        print(
            f"  {row['id']}: agent={row['agent']} profile={row['profile']} "
            f"servers=[{servers}] ides=[{ides}]"
        )
        if row.get("note"):
            print(f"    {row['note']}")
        print(f"    path: {row['path']}")
    return 0


def cmd_init(root: Path, *, force: bool, dry_run: bool) -> int:
    dest = registry_path(root)
    if dest.is_file() and not force:
        print(f"Registry already exists: {dest}")
        print("  Use --force to overwrite from seed.")
        return 0
    from willow.fylgja.mcp_projects import load_seed

    seed = load_seed(root)
    if dry_run:
        print(f"[mcp] Would write registry → {dest}")
        return 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(seed, indent=2) + "\n", encoding="utf-8")
    print(f"[mcp] Wrote registry → {dest}")
    return 0


def cmd_sync(
    root: Path,
    *,
    project_ids: list[str] | None,
    dry_run: bool,
) -> int:
    ensure_registry(package_root=root, dry_run=dry_run)
    written = sync_all(package_root=root, project_ids=project_ids, dry_run=dry_run)
    print(f"[mcp] Synced {len(written)} project(s): {', '.join(written)}")
    return 0


def cmd_check(root: Path, *, project_ids: list[str] | None) -> int:
    ensure_registry(package_root=root, dry_run=False)
    issues = audit_all(package_root=root, project_ids=project_ids)
    if issues:
        print("MCP project check — DRIFT:")
        for item in issues:
            print(f"  · {item}")
        return 1
    print("MCP project check — OK")
    return 0


def cmd_audit(root: Path, *, search_root: Path | None) -> int:
    ensure_registry(package_root=root, dry_run=False)
    reg_issues = audit_all(package_root=root)
    extras = unregistered_mcp_files(package_root=root, search_root=search_root)
    if reg_issues:
        print("Registry drift:")
        for item in reg_issues:
            print(f"  · {item}")
    if extras:
        print("Unregistered MCP configs (not in projects.json):")
        for path in extras:
            print(f"  · {path}")
    if not reg_issues and not extras:
        print("MCP audit — OK (registry in sync, no stray configs)")
        return 0
    return 1 if reg_issues else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="./willow.sh mcp",
        description="Fleet MCP project registry — render and sync per-repo IDE configs",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List projects in registry")

    p_init = sub.add_parser("init", help="Bootstrap $WILLOW_HOME/mcp/projects.json from seed")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing registry")
    p_init.add_argument("--dry-run", action="store_true")

    p_sync = sub.add_parser("sync", help="Materialize MCP JSON for registry projects")
    p_sync.add_argument("projects", nargs="*", help="Project id(s); default all")
    p_sync.add_argument("--dry-run", action="store_true")

    p_check = sub.add_parser("check", help="Verify on-disk configs match registry")
    p_check.add_argument("projects", nargs="*", help="Project id(s); default all")

    p_audit = sub.add_parser(
        "audit",
        help="check + list unregistered mcp.json files under github",
    )
    p_audit.add_argument(
        "--search-root",
        default="",
        help="Scan root (default: ~/github)",
    )

    args = parser.parse_args(argv)
    root = repo_root()

    if args.command == "list":
        return cmd_list(root)
    if args.command == "init":
        return cmd_init(root, force=args.force, dry_run=args.dry_run)
    if args.command == "sync":
        ids = list(args.projects) or None
        return cmd_sync(root, project_ids=ids, dry_run=args.dry_run)
    if args.command == "check":
        ids = list(args.projects) or None
        return cmd_check(root, project_ids=ids)
    if args.command == "audit":
        search = Path(args.search_root).expanduser() if args.search_root else None
        return cmd_audit(root, search_root=search)
    return 1


if __name__ == "__main__":
    sys.exit(main())
