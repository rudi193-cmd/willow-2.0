#!/usr/bin/env python3
"""Verify public-fallback pack: no secrets, no operator paths, link + install dry-run."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from willow.fylgja.install_project import install_project  # noqa: E402
from willow.fylgja.link_fleet_home import link_fleet_home  # noqa: E402
from willow.fylgja.willow_home import (  # noqa: E402
    PUBLIC_FALLBACK_MARKER,
    config_mode,
    fleet_home,
    materialize_public_pack,
    public_pack_dir,
)


FORBIDDEN_SUBSTRINGS = (
    "gsk_",
    "sk-ant-",
    "/home/sean-campbell",
)
FORBIDDEN_ASSIGNMENTS = ("GROQ_API_KEY=", "GEMINI_API_KEY=", "DISCORD_TOKEN=")


def _scan_pack(pack: Path) -> list[str]:
    errors: list[str] = []
    for path in pack.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for bad in FORBIDDEN_SUBSTRINGS:
            if bad in text:
                errors.append(f"{path.relative_to(ROOT)}: contains forbidden {bad!r}")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for bad in FORBIDDEN_ASSIGNMENTS:
                if bad in line:
                    errors.append(f"{path.relative_to(ROOT)}: assignment {bad!r}")
    return errors


def main() -> int:
    pack = public_pack_dir(ROOT)
    errors = _scan_pack(pack)
    required = ("willow.md", "env.example", "settings.global.json", "settings.local.json", "README.md")
    for name in required:
        if not (pack / name).is_file():
            errors.append(f"missing public pack file: {name}")
    root_contract = ROOT / "willow.md"
    if not root_contract.is_file() or root_contract.is_symlink():
        errors.append("root willow.md must be a tracked public file, not a symlink")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        fake_private = tmp_path / "private"
        fake_private.mkdir()
        fake_repo = tmp_path / "repo"
        fake_repo.mkdir()

        # Copy minimal repo tree for install/link
        for rel in (
            "willow.md",
            "willow/fylgja/config/mcp.template.json",
            "willow/fylgja/config/public",
            "willow/fylgja/link_fleet_home.py",
            "willow/fylgja/willow_home.py",
            "willow/fylgja/project_env.py",
            "willow/fylgja/install_project.py",
            "willow/fylgja/global_settings.py",
        ):
            src = ROOT / rel
            dst = fake_repo / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                import shutil

                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                dst.write_bytes(src.read_bytes())

        os.environ["WILLOW_CONFIG_MODE"] = "public-fallback"
        os.environ.pop("WILLOW_HOME", None)
        os.chdir(fake_repo)

        home = materialize_public_pack(package_root=fake_repo)
        if not (home / "willow.md").is_file():
            errors.append("materialize_public_pack did not create willow.md")
        if not (home / PUBLIC_FALLBACK_MARKER).is_file():
            errors.append("materialize_public_pack missing .public-fallback marker")

        mode = link_fleet_home(package_root=fake_repo, dry_run=False)
        if mode != "public-fallback":
            errors.append(f"link_fleet_home mode={mode}, expected public-fallback")
        if not (fake_repo / "willow.md").is_file() or (fake_repo / "willow.md").is_symlink():
            errors.append("root willow.md must remain a regular public file")

        install_project(
            agent_name="willow",
            ides=["cursor"],
            package_root=fake_repo,
            dry_run=True,
            claude_global=False,
        )

        if config_mode(fake_repo) != "public-fallback":
            errors.append("config_mode not public-fallback after link")
        if fleet_home(fake_repo) != fake_repo / ".willow" / "generated":
            errors.append(f"unexpected fleet_home: {fleet_home(fake_repo)}")

        generated_env = home / "env"
        if generated_env.is_file():
            env_text = generated_env.read_text(encoding="utf-8")
            assert str(fake_repo) in env_text or "WILLOW_ROOT=" in env_text
            for line in env_text.splitlines():
                if line.strip().startswith("#"):
                    continue
                for bad in FORBIDDEN_ASSIGNMENTS:
                    if bad in line:
                        errors.append(f"generated env assignment {bad!r}")

        settings = json.loads((pack / "settings.local.json").read_text(encoding="utf-8"))
        if "GROQ" in json.dumps(settings).upper():
            errors.append("public settings.local.json mentions GROQ")

    if errors:
        print("verify_public_fallback: FAIL")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("verify_public_fallback: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
