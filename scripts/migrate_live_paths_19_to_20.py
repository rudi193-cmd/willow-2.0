#!/usr/bin/env python3
"""One-shot: rewrite live willow-2.0 / willow_20 wiring to willow-2.0 / willow_20."""
from __future__ import annotations

import re
from pathlib import Path

HOME = Path.home()
REPLACEMENTS = [
    ("/home/sean-campbell/github/willow-2.0", "/home/sean-campbell/github/willow-2.0"),
    ("~/github/willow-2.0", "~/github/willow-2.0"),
    ("$HOME/github/willow-2.0", "$HOME/github/willow-2.0"),
    ("/home/sean-campbell/github/willow-2.0", "/home/sean-campbell/github/willow-2.0"),
    ("~/github/willow-2.0", "~/github/willow-2.0"),
    ("github/willow-2.0", "github/willow-2.0"),
    ('Path.home() / "github" / "willow-2.0"', 'Path.home() / "github" / "willow-2.0"'),
    ("Path.home() / 'github' / 'willow-2.0'", "Path.home() / 'github' / 'willow-2.0'"),
    ("/home/sean-campbell/github/willow-2.0", "/home/sean-campbell/github/willow-2.0"),
    ("~/github/willow-2.0", "~/github/willow-2.0"),
    ('"willow_20_test"', '"willow_20_test"'),
    ("willow_20_test", "willow_20_test"),
    ('"willow_20"', '"willow_20"'),
    ("willow_20", "willow_20"),
    ("willow-2.0", "willow-2.0"),
]

SKIP_PARTS = {
    "worktrees",
    "archive",
    "node_modules",
    ".git",
    "agent-transcripts",
    "file-history",
    ".cache",
    "mcp-memory-service",
}

TARGET_DIRS = [
    HOME / "github" / "safe-app-willow-grove",
    HOME / "github" / "willow-2.0" / "willow" / "fylgja",
    HOME / "github" / "willow-2.0" / "scripts",
    HOME / ".claude" / "commands",
    HOME / "github" / "SAFE" / "Applications" / "ratatosk",
]


def should_skip(path: Path, *, include_worktrees: bool = False) -> bool:
    parts = set(path.parts)
    if not include_worktrees and any(p in SKIP_PARTS for p in parts):
        return True
    if path.suffix not in {
        ".py", ".json", ".sh", ".md", ".mdc", ".service", ".socket", ".toml", ".yaml", ".yml",
    }:
        return False
    if "docs/superpowers" in str(path) and path.suffix == ".md":
        return True
    if path.name.startswith("session_handoff") or "HANDOFF" in path.name:
        return True
    return False


def migrate_file(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return False
    orig = text
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    if text == orig:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-worktrees", action="store_true",
                    help="Also migrate safe-app-willow-grove/worktrees/*")
    args = ap.parse_args()
    changed: list[str] = []
    for base in TARGET_DIRS:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or should_skip(path, include_worktrees=args.include_worktrees):
                continue
            if migrate_file(path):
                changed.append(str(path))
    print(f"updated {len(changed)} files")
    for p in sorted(changed)[:80]:
        print(f"  {p}")
    if len(changed) > 80:
        print(f"  ... and {len(changed) - 80} more")


if __name__ == "__main__":
    main()
