"""Resolve fleet home: private willow-config vs repo public fallback pack."""
from __future__ import annotations

import os
from pathlib import Path

from willow.fylgja.project_env import repo_root

PUBLIC_FALLBACK_MARKER = ".public-fallback"


def private_home() -> Path:
    return Path.home() / "github" / ".willow"


def generated_home(package_root: Path | None = None) -> Path:
    return (package_root or repo_root()).resolve() / ".willow" / "generated"


def public_pack_dir(package_root: Path | None = None) -> Path:
    return (package_root or repo_root()).resolve() / "willow" / "fylgja" / "config" / "public"


def private_config_available() -> bool:
    home = private_home()
    contract = home / "willow.md"
    marker = home / PUBLIC_FALLBACK_MARKER
    return contract.is_file() and not marker.is_file()


def fleet_home(package_root: Path | None = None) -> Path:
    if os.environ.get("WILLOW_HOME"):
        return Path(os.environ["WILLOW_HOME"]).expanduser().resolve()
    forced = os.environ.get("WILLOW_CONFIG_MODE", "").strip().lower()
    if forced == "public-fallback":
        return generated_home(package_root)
    if private_config_available():
        return private_home()
    return generated_home(package_root)


def config_mode(package_root: Path | None = None) -> str:
    forced = os.environ.get("WILLOW_CONFIG_MODE", "").strip().lower()
    if forced in ("private-config", "public-fallback", "degraded"):
        return forced
    if private_config_available():
        return "private-config"
    return "public-fallback"


def _expand_text(text: str, *, repo: Path, home: Path) -> str:
    user = os.environ.get("USER", Path.home().name)
    return (
        text.replace("{{HOME}}", str(Path.home()))
        .replace("{{USER}}", user)
        .replace("{{REPO_ROOT}}", str(repo))
        .replace("{{WILLOW_HOME}}", str(home))
    )


def materialize_public_pack(
    *, package_root: Path | None = None, dry_run: bool = False, force: bool = False
) -> Path:
    root = (package_root or repo_root()).resolve()
    pack = public_pack_dir(root)
    contract = pack / "willow.md"
    if not contract.is_file():
        raise FileNotFoundError(f"public pack missing: {contract}")

    home = generated_home(root)
    if dry_run:
        print(f"[willow_home] Would materialize public pack → {home}")
        return home

    home.mkdir(parents=True, exist_ok=True)
    for name in ("willow.md", "settings.global.json"):
        src = pack / name
        dst = home / name
        if src.is_file() and (force or not dst.is_file()):
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    env_src = pack / "env.example"
    env_dst = home / "env"
    if env_src.is_file() and (force or not env_dst.is_file()):
        env_dst.write_text(
            _expand_text(env_src.read_text(encoding="utf-8"), repo=root, home=home),
            encoding="utf-8",
        )

    (home / PUBLIC_FALLBACK_MARKER).write_text("public-fallback\n", encoding="utf-8")
    print(f"[willow_home] Materialized public fallback → {home}")
    return home


def settings_template_path(package_root: Path | None = None) -> Path:
    root = (package_root or repo_root()).resolve()
    public_tpl = public_pack_dir(root) / "settings.local.json"
    default_tpl = root / "willow" / "fylgja" / "config" / "settings.local.json"
    if config_mode(root) == "public-fallback" and public_tpl.is_file():
        return public_tpl
    return default_tpl
