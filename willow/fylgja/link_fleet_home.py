#!/usr/bin/env python3
"""Link runtime config from fleet home into willow-2.0."""
from __future__ import annotations

import argparse
from pathlib import Path

from willow.fylgja.project_env import repo_root
from willow.fylgja.willow_home import (
    config_mode,
    fleet_home,
    materialize_public_pack,
)


def _expand_example(text: str) -> str:
    import os

    home = Path.home()
    return (
        text.replace("{{HOME}}", str(home))
        .replace("{{USER}}", os.environ.get("USER", home.name))
    )


def bootstrap_private(*, package_root: Path | None = None) -> None:
    """Create ~/.willow contract files from repo templates when missing (private mode)."""
    root = (package_root or repo_root()).resolve()
    home = fleet_home(package_root)
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


def link_map(package_root: Path | None = None) -> list[tuple[Path, Path]]:
    """(canonical in fleet home, consumer path in willow-2.0)."""
    root = (package_root or repo_root()).resolve()
    home = fleet_home(package_root)
    cfg = root / "willow" / "fylgja" / "config"
    return [
        (home / "env", cfg / "fleet.env"),
        (home / "settings.global.json", cfg / "settings.global.json"),
    ]


def ensure_fleet_home(*, package_root: Path | None = None, dry_run: bool = False) -> str:
    root = (package_root or repo_root()).resolve()
    mode = config_mode(root)
    if mode == "public-fallback":
        if not dry_run:
            materialize_public_pack(package_root=root)
        else:
            materialize_public_pack(package_root=root, dry_run=True)
    elif not dry_run:
        bootstrap_private(package_root=root)
    return config_mode(root)


def link_fleet_home(*, package_root: Path | None = None, dry_run: bool = False) -> str:
    root = (package_root or repo_root()).resolve()
    mode = ensure_fleet_home(package_root=root, dry_run=dry_run)
    home = fleet_home(package_root)
    home.mkdir(parents=True, exist_ok=True)

    print(f"[link_fleet_home] config-mode: {mode} (home={home})")

    for src, dst in link_map(package_root):
        if not src.is_file():
            hint = (
                "public pack missing — check willow/fylgja/config/public/"
                if mode == "public-fallback"
                else "clone/pull rudi193-cmd/willow-config → ~/github/.willow"
            )
            raise FileNotFoundError(f"canonical missing: {src} ({hint})")
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

    return mode


def _cli() -> int:
    p = argparse.ArgumentParser(
        description="Link willow-2.0 runtime config paths → fleet home (private or public fallback)"
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--public",
        action="store_true",
        help="Force public-fallback (skip private willow-config home)",
    )
    args = p.parse_args()
    if args.public:
        import os

        os.environ["WILLOW_CONFIG_MODE"] = "public-fallback"
    link_fleet_home(dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
