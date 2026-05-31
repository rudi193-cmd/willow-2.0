#!/usr/bin/env python3
"""Bootstrap ~/.openclaw/skills for skill_steward and OpenClaw MCP.

Creates the managed skills tree without requiring a full Gateway onboarding.
Two paths:
  --seed-git (default): sparse clone openclaw/openclaw skills/ → ~/.openclaw/skills
  --with-cli: npm global openclaw + optional `openclaw skills install --global`

b17: OCSET · ΔΣ=42
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

OPENCLAW_HOME = Path.home() / ".openclaw"
SKILLS_DIR = OPENCLAW_HOME / "skills"
VENDOR = Path.home() / ".willow" / "vendor" / "openclaw"
OPENCLAW_REPO = "https://github.com/openclaw/openclaw.git"

# OpenClaw rejects unknown keys and malformed shapes (strict JSON schema).
# Do not add _willow_note or other undocumented fields to openclaw.json.
VALID_MIN_CONFIG: dict = {
    "agents": {"defaults": {"workspace": "~/.openclaw/workspace"}},
    "gateway": {"mode": "local"},
}

# Starter set for Willow fleet (ClawHub browser + common ops)
STARTER_SLUGS = (
    "clawhub",
    "github",
    "session-logs",  # upstream dropped standalone "memory" skill
    "summarize",
    "weather",
    "skill-creator",
    "tmux",
)


def _run(cmd: list[str], *, cwd: Path | None = None, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def ensure_dirs() -> None:
    OPENCLAW_HOME.mkdir(parents=True, exist_ok=True)
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)


def _load_config(cfg: Path) -> dict | None:
    try:
        return json.loads(cfg.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def is_willow_invalid_stub(data: dict | None) -> bool:
    """Detect legacy Willow stub that fails openclaw config validate."""
    if not data:
        return False
    if "_willow_note" in data:
        return True
    skills = data.get("skills")
    if isinstance(skills, dict):
        load = skills.get("load")
        if isinstance(load, dict) and "watch" in load and "extraDirs" not in load:
            return True
    # Root with only invalid/partial keys and no agents/gateway
    allowed = {"$schema"}
    keys = set(data.keys()) - allowed
    if keys <= {"skills", "_willow_note"}:
        return True
    return False


def ensure_valid_config(*, force_repair: bool = False) -> Path:
    """Ensure ~/.openclaw/openclaw.json passes OpenClaw strict validation."""
    ensure_dirs()
    cfg = OPENCLAW_HOME / "openclaw.json"
    existing = _load_config(cfg) if cfg.is_file() else None
    if existing is not None and not force_repair and not is_willow_invalid_stub(existing):
        return cfg
    if cfg.is_file():
        backup = cfg.with_suffix(".json.willow-backup")
        if not backup.is_file():
            backup.write_text(cfg.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"  backed up invalid config → {backup}", file=sys.stderr)
    cfg.write_text(json.dumps(VALID_MIN_CONFIG, indent=2) + "\n", encoding="utf-8")
    oc = find_openclaw_cli()
    if oc:
        r = _run([oc, "doctor", "--fix", "--yes"], timeout=120)
        if r.returncode != 0:
            print(f"  openclaw doctor --fix: {r.stderr or r.stdout}", file=sys.stderr)
    return cfg


def write_min_config() -> Path:
    """Alias for ensure_valid_config (legacy callers)."""
    return ensure_valid_config()


def sparse_clone_skills() -> Path:
    """Clone only openclaw/skills into ~/.willow/vendor/openclaw."""
    VENDOR.parent.mkdir(parents=True, exist_ok=True)
    if (VENDOR / ".git").is_dir():
        _run(["git", "-C", str(VENDOR), "fetch", "--depth", "1", "origin", "main"], timeout=180)
        _run(["git", "-C", str(VENDOR), "checkout", "main"], timeout=60)
        _run(["git", "-C", str(VENDOR), "pull", "--ff-only"], timeout=180)
    else:
        if VENDOR.exists():
            shutil.rmtree(VENDOR)
        r = _run(
            [
                "git", "clone", "--depth", "1", "--filter=blob:none", "--sparse",
                OPENCLAW_REPO, str(VENDOR),
            ],
            timeout=300,
        )
        if r.returncode != 0:
            raise RuntimeError(f"git clone failed: {r.stderr or r.stdout}")
        r = _run(["git", "-C", str(VENDOR), "sparse-checkout", "set", "skills"], timeout=60)
        if r.returncode != 0:
            raise RuntimeError(f"sparse-checkout failed: {r.stderr or r.stdout}")
    skills_src = VENDOR / "skills"
    if not skills_src.is_dir():
        raise RuntimeError(f"no skills/ in {VENDOR}")
    return skills_src


def seed_from_git(*, only: tuple[str, ...] = STARTER_SLUGS, link: bool = False) -> list[str]:
    """Copy or symlink starter skills into ~/.openclaw/skills."""
    ensure_dirs()
    write_min_config()
    src_root = sparse_clone_skills()
    installed: list[str] = []
    for slug in only:
        src = src_root / slug
        if not (src / "SKILL.md").is_file():
            # try case-insensitive
            found = None
            for child in src_root.iterdir():
                if child.is_dir() and child.name.lower() == slug.lower():
                    found = child
                    break
            if found and (found / "SKILL.md").is_file():
                src = found
            else:
                print(f"  skip missing: {slug}", file=sys.stderr)
                continue
        dest = SKILLS_DIR / src.name
        if dest.exists():
            if dest.is_symlink():
                dest.unlink()
            elif dest.is_dir():
                shutil.rmtree(dest)
        if link:
            dest.symlink_to(src.resolve())
        else:
            shutil.copytree(src, dest, symlinks=False)
        installed.append(dest.name)
    return installed


def find_openclaw_cli() -> str | None:
    for candidate in (
        shutil.which("openclaw"),
        str(Path.home() / ".local" / "bin" / "openclaw"),
        str(Path.home() / ".openclaw" / "bin" / "openclaw"),
    ):
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def install_cli() -> str:
    """Install openclaw global CLI (npm). Returns path to binary."""
    npm = shutil.which("npm")
    if not npm:
        raise RuntimeError("npm not found — install Node 22+ or use --seed-git only")
    r = _run([npm, "install", "-g", "openclaw@latest"], timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"npm install -g openclaw failed: {r.stderr or r.stdout}")
    path = find_openclaw_cli()
    if not path:
        prefix = _run([npm, "prefix", "-g"], timeout=30)
        if prefix.returncode == 0:
            guess = Path(prefix.stdout.strip()) / "bin" / "openclaw"
            if guess.is_file():
                return str(guess)
        raise RuntimeError("openclaw installed but binary not found on PATH")
    return path


def install_via_cli(slugs: tuple[str, ...] = STARTER_SLUGS) -> list[str]:
    ensure_dirs()
    ensure_valid_config(force_repair=is_willow_invalid_stub(_load_config(OPENCLAW_HOME / "openclaw.json")))
    oc = find_openclaw_cli() or install_cli()
    installed: list[str] = []
    for slug in slugs:
        r = _run([oc, "skills", "install", slug, "--global"], timeout=120)
        if r.returncode == 0:
            installed.append(slug)
            print(f"  installed: {slug}", flush=True)
        else:
            print(f"  cli install failed {slug}: {r.stderr or r.stdout}", file=sys.stderr)
    return installed


def count_skills() -> int:
    if not SKILLS_DIR.is_dir():
        return 0
    return sum(1 for _ in SKILLS_DIR.rglob("SKILL.md"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--with-cli",
        action="store_true",
        help="Install openclaw global CLI and use openclaw skills install --global",
    )
    parser.add_argument(
        "--link",
        action="store_true",
        help="Symlink vendor skills instead of copy (dev)",
    )
    parser.add_argument(
        "--all-bundled",
        action="store_true",
        help="Copy every skill from upstream skills/ (not just starters)",
    )
    parser.add_argument(
        "--repair-config",
        action="store_true",
        help="Replace legacy invalid Willow openclaw.json stub with schema-valid minimum",
    )
    args = parser.parse_args()

    if args.repair_config:
        ensure_valid_config(force_repair=True)
        print(json.dumps({"repaired": str(OPENCLAW_HOME / "openclaw.json")}, indent=2))
        return 0

    if args.with_cli:
        try:
            installed = install_via_cli()
        except RuntimeError as exc:
            print(f"CLI path failed: {exc}", file=sys.stderr)
            print("Falling back to --seed-git", file=sys.stderr)
            installed = seed_from_git(link=args.link)
    else:
        slugs = ()
        if args.all_bundled:
            src = sparse_clone_skills()
            slugs = tuple(
                p.name for p in sorted(src.iterdir())
                if p.is_dir() and (p / "SKILL.md").is_file()
            )
        else:
            slugs = STARTER_SLUGS
        installed = seed_from_git(only=slugs, link=args.link)

    n = count_skills()
    print(json.dumps({
        "openclaw_home": str(OPENCLAW_HOME),
        "skills_dir": str(SKILLS_DIR),
        "installed": installed,
        "skill_md_count": n,
        "openclaw_cli": find_openclaw_cli(),
    }, indent=2))
    return 0 if n > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
