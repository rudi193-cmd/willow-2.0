#!/usr/bin/env python3
"""Symlink fleet contract/config from ~/github/.willow (willow-config) into willow-2.0."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from willow.fylgja.project_env import repo_root


def _expand_example(text: str) -> str:
    home = Path.home()
    return (
        text.replace("{{HOME}}", str(home))
        .replace("{{USER}}", os.environ.get("USER", home.name))
    )


def bootstrap_canonical(*, package_root: Path | None = None) -> None:
    """Create ~/.willow contract files from repo templates when missing."""
    root = (package_root or repo_root()).resolve()
    home = fleet_home()
    home.mkdir(parents=True, exist_ok=True)
    cfg = root / "willow" / "fylgja" / "config"

    env_dst = home / "env"
    if not env_dst.is_file():
        for src in (home / "env.example", cfg / "fleet.env.example"):
            if src.is_file():
                env_dst.write_text(_expand_example(src.read_text(encoding="utf-8")), encoding="utf-8")
                print(f"[link_fleet_home] Created {env_dst} from {src.name}")
                break

    settings_dst = home / "settings.global.json"
    if not settings_dst.is_file():
        from willow.fylgja.global_settings import init_global_settings

        init_global_settings()
        print(f"[link_fleet_home] Created {settings_dst} via init_global_settings")


def fleet_home() -> Path:
    return Path(os.environ.get("WILLOW_HOME", Path.home() / "github" / ".willow"))


def link_map(package_root: Path | None = None) -> list[tuple[Path, Path]]:
    """(canonical in ~/github/.willow, consumer path in willow-2.0)"""
    root = (package_root or repo_root()).resolve()
    home = fleet_home()
    cfg = root / "willow" / "fylgja" / "config"
    return [
        (home / "willow.md", root / "willow.md"),
        (home / "env", cfg / "fleet.env"),
        (home / "settings.global.json", cfg / "settings.global.json"),
    ]


def link_fleet_home(*, package_root: Path | None = None, dry_run: bool = False) -> None:
    if not dry_run:
        bootstrap_canonical(package_root=package_root)
    home = fleet_home()
    home.mkdir(parents=True, exist_ok=True)
    for src, dst in link_map(package_root):
        if not src.is_file():
            raise FileNotFoundError(
                f"canonical missing in willow-config home: {src} "
                f"(clone/pull rudi193-cmd/willow-config → ~/.willow)"
            )
        if dry_run:
            print(f"[link_fleet_home] Would symlink {dst} → {src}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.is_symlink() and dst.resolve() == src.resolve():
            continue
        if dst.exists() and not dst.is_symlink():
            backup = dst.with_suffix(dst.suffix + ".bak")
            dst.rename(backup)
            print(f"[link_fleet_home] Backed up {dst} → {backup}")
        if dst.is_symlink() or dst.exists():
            dst.unlink()
        dst.symlink_to(src)
        print(f"[link_fleet_home] {dst} → {src}")


def _cli() -> int:
    p = argparse.ArgumentParser(
        description="Link willow-2.0 contract paths → private ~/.willow (willow-config)"
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    link_fleet_home(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
