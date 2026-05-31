#!/usr/bin/env python3
"""Move ~ clone dirs into ~/github/ and replace with symlinks.

Kart bwrap only mounts github/agents/Desktop — run this in a host terminal:
  python3 ~/github/willow-2.0/scripts/consolidate_home_clones.py
Then:
  bash ~/github/willow-2.0/scripts/consolidate_github_layout.sh
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

HOME = os.path.expanduser("~")
GITHUB = os.path.join(HOME, "github")
SCRIPT = os.path.join(GITHUB, "willow-2.0", "scripts", "consolidate_github_layout.sh")

MOVES: list[tuple[str, str | None]] = [
    ("SAFE", None),
    ("claude-deep-review", None),
    ("litellm", None),
    ("ngrok-python", None),
    ("python-sdk", None),
    ("journal", "sean-data-vault/journal"),
    ("willow-2.0-wt-grove-bidir", "archive/willow-2.0-wt-grove-bidir"),
    ("willow-wt", "archive/willow-wt"),
    ("sean-data-vault", None),
    ("agents", "archive/legacy-agents-home"),
]


def symlink(target: str, link: str) -> None:
    if os.path.islink(link) and os.path.realpath(link) == os.path.realpath(target):
        print(f"OK {link}")
        return
    if os.path.lexists(link):
        if os.path.isdir(link) and not os.path.islink(link):
            shutil.rmtree(link)
        else:
            os.remove(link)
    os.symlink(target, link)
    print(f"+ ln -s {target} <- {link}")


def dedupe(name: str, dest_sub: str | None = None) -> None:
    dest_sub = dest_sub or name
    src = os.path.join(HOME, name)
    dest = os.path.join(GITHUB, dest_sub)
    if not os.path.exists(src):
        print(f"skip missing ~/{name}")
        return
    if os.path.islink(src):
        print(f"OK symlink ~/{name}")
        return
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if not os.path.exists(dest):
        print(f"+ mv {src} -> {dest}")
        shutil.move(src, dest)
        symlink(dest, src)
        return
    print(f"+ dedupe ~/{name} (keep github/{dest_sub})")
    shutil.rmtree(src)
    symlink(dest, src)


def main() -> int:
    for name, dest_sub in MOVES:
        try:
            dedupe(name, dest_sub)
        except OSError as exc:
            print(f"WARN ~/{name}: {exc}", file=sys.stderr)
    if os.path.isfile(SCRIPT):
        print("==> consolidate_github_layout.sh")
        return subprocess.run(["bash", SCRIPT], check=False).returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
