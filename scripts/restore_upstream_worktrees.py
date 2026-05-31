#!/usr/bin/env python3
"""Restore upstream steward clones (open PRs) under worktrees/."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WT = ROOT / "worktrees"

CLONES = [
    {
        "dir": "upstream-emerging-rule-community",
        "url": "https://github.com/rudi193-cmd/community.git",
        "branch": "feat/calibration-series",
        "upstream": "https://github.com/Emerging-Rule/community.git",
        "pr": "Emerging-Rule/community#10",
    },
    {
        "dir": "upstream-mengram",
        "url": "https://github.com/rudi193-cmd/mengram.git",
        "branch": "docs/contributing",
        "upstream": "https://github.com/alibaizhanov/mengram.git",
        "pr": "alibaizhanov/mengram#40",
    },
]


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    if r.stdout.strip():
        print(r.stdout, end="")
    if r.stderr.strip():
        print(r.stderr, file=sys.stderr, end="")
    if check and r.returncode != 0:
        raise SystemExit(r.returncode)
    return r


def ensure_clone(spec: dict) -> None:
    WT.mkdir(exist_ok=True)
    dest = WT / spec["dir"]
    if dest.exists() and (dest / ".git").is_dir():
        run(["git", "fetch", "origin", "--prune"], cwd=dest, check=False)
        run(["git", "checkout", spec["branch"]], cwd=dest, check=False)
        run(["git", "pull", "origin", spec["branch"]], cwd=dest, check=False)
        print(f"updated {spec['dir']} ({spec['pr']})")
        return
    run(["git", "clone", "--branch", spec["branch"], spec["url"], str(dest)])
    run(["git", "remote", "add", "upstream", spec["upstream"]], cwd=dest, check=False)
    print(f"cloned {spec['dir']} ({spec['pr']})")


def ensure_mcp_memory() -> None:
    dest = WT / "upstream-mcp-memory-service"
    src = ROOT / "mcp-memory-service"
    if not dest.exists():
        if src.is_dir() and (src / ".git").is_dir():
            print(f"copying {src.name} -> {dest.name} (preserves local branch)")
            shutil.copytree(src, dest, symlinks=True)
        else:
            run(
                [
                    "git",
                    "clone",
                    "https://github.com/rudi193-cmd/mcp-memory-service.git",
                    str(dest),
                ]
            )
        run(
            ["git", "remote", "add", "upstream", "https://github.com/doobidoo/mcp-memory-service.git"],
            cwd=dest,
            check=False,
        )
    else:
        run(["git", "fetch", "origin", "--prune"], cwd=dest, check=False)
    r = subprocess.run(
        ["git", "-C", str(dest), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
    )
    print(f"mcp-memory-service on branch: {r.stdout.strip()}")


def main() -> None:
    for spec in CLONES:
        ensure_clone(spec)
    # mcp-memory-service (doobidoo): inactive — restore only with --include-mcp-memory
    if "--include-mcp-memory" in sys.argv:
        ensure_mcp_memory()

    print("\nworktrees/:")
    for p in sorted(WT.iterdir()):
        if not p.is_dir():
            continue
        br = subprocess.run(
            ["git", "-C", str(p), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
        )
        hd = subprocess.run(
            ["git", "-C", str(p), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
        )
        if br.returncode != 0:
            print(f"  {p.name}: (not a git repo)")
            continue
        print(f"  {p.name}: {br.stdout.strip()} @ {hd.stdout.strip()}")


if __name__ == "__main__":
    main()
