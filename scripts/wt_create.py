"""scripts/wt_create.py — Worktree + subagent lifecycle automator.
b17: WTCRT  ΔΣ=42

Matches the Grove Fleet Manager 3-test pattern at the worktree level:
  Test 1: state saves automatically (wt_project.db created, no manual step)
  Test 2: resume picks up where it left off (existing DB left intact)
  Test 3: circuit breaker (stub — seed atom + Grove post creates the audit trail)

Usage:
  python3 scripts/wt_create.py <slug> <repo-path> [--task "description"]
  python3 scripts/wt_create.py <slug> <repo-path> --issue "id:area:description" [...]

The worktree is created at ../<repo-basename>-wt-<slug>.
wt_project.db is auto-created inside it (Test 1).
If it already exists, it is left intact (Test 2 — resume).
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Generic wt_project.db schema — same contract as wt_db.py but parameterized
# ---------------------------------------------------------------------------

_WT_DB_NAME = "wt_project.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS issues (
    id          TEXT PRIMARY KEY,
    area        TEXT NOT NULL,
    description TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'open',
    notes       TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _init_wt_db(wt_path: Path, slug: str, task: str, issues: list[tuple]) -> Path:
    db_path = wt_path / _WT_DB_NAME
    existed = db_path.exists()
    conn = sqlite3.connect(db_path)
    conn.executescript(_SCHEMA)
    # Meta: write slug + task on first create only
    if not existed:
        conn.execute(
            "INSERT OR IGNORE INTO meta VALUES (?, ?)", ("slug", slug)
        )
        conn.execute(
            "INSERT OR IGNORE INTO meta VALUES (?, ?)", ("task", task)
        )
        conn.execute(
            "INSERT OR IGNORE INTO meta VALUES (?, ?)",
            ("created_at", datetime.now().isoformat()),
        )
        for issue_id, area, description in issues:
            conn.execute(
                "INSERT OR IGNORE INTO issues (id, area, description) VALUES (?, ?, ?)",
                (issue_id, area, description),
            )
    conn.commit()
    conn.close()
    return db_path


def _status(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, area, status, description FROM issues ORDER BY area, id"
    ).fetchall()
    conn.close()
    if not rows:
        print("  (no issues seeded — add with --issue id:area:description)")
        return
    print(f"  {'ID':<20} {'AREA':<10} {'STATUS':<8} DESCRIPTION")
    print("  " + "-" * 72)
    for r in rows:
        print(f"  {r['id']:<20} {r['area']:<10} {r['status']:<8} {r['description'][:46]}")


# ---------------------------------------------------------------------------
# Worktree creation
# ---------------------------------------------------------------------------

def _git_root(repo_path: Path) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=repo_path, capture_output=True, text=True, check=True
    )
    return Path(result.stdout.strip())


def _short_head(repo_path: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=repo_path, capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else "?"


def create_worktree(
    slug: str,
    repo_path: Path,
    task: str = "",
    issues: list[tuple] | None = None,
) -> dict:
    """Create a worktree and seed wt_project.db. Return state dict."""
    issues = issues or []
    git_root = _git_root(repo_path)
    branch    = f"wt/{slug}"
    wt_name   = f"{git_root.name}-wt-{slug}"
    wt_path   = git_root.parent / wt_name
    head      = _short_head(git_root)

    # --- Test 2: resume if worktree already exists ---
    resumed = wt_path.exists()
    if not resumed:
        print(f"  creating worktree: {wt_path}")
        subprocess.run(
            ["git", "worktree", "add", "-b", branch, str(wt_path), "HEAD"],
            cwd=git_root, check=True
        )
    else:
        print(f"  worktree exists — resuming: {wt_path}")

    # --- Test 1: auto-init wt_project.db ---
    db_path = _init_wt_db(wt_path, slug, task, issues)
    action  = "resumed" if resumed else "created"
    print(f"  wt_project.db {action}: {db_path}")
    _status(db_path)

    return {
        "slug":     slug,
        "branch":   branch,
        "wt_path":  str(wt_path),
        "head":     head,
        "db_path":  str(db_path),
        "resumed":  resumed,
        "task":     task,
    }


# ---------------------------------------------------------------------------
# Subagent init (fractal — same pattern at agent level)
# ---------------------------------------------------------------------------

def _willow_cmd(*args) -> dict | None:
    """Call a Willow MCP tool via willow.sh CLI if available."""
    willow_sh = Path.home() / "github" / "willow-2.0" / "willow.sh"
    if not willow_sh.exists():
        return None
    try:
        result = subprocess.run(
            [str(willow_sh)] + list(args),
            capture_output=True, text=True, timeout=15
        )
        return json.loads(result.stdout) if result.stdout.strip() else None
    except Exception:
        return None


def print_grove_post(state: dict) -> str:
    """Print the Grove post to make — always manual so the agent owns the atom ID."""
    task_line = f" — {state['task']}" if state["task"] else ""
    action    = "resumed" if state["resumed"] else "open"
    lines = [
        "",
        "  ── Grove post (copy to #hanuman) ──────────────────────────────",
        f"  wt-{state['slug']} {action} on {state['branch']} ({state['head']}).{task_line}",
        f"  wt_project.db {'resumed' if state['resumed'] else 'seeded'} at {Path(state['db_path']).name}.",
        "  Seed atom: <ingest willow_knowledge_ingest with the wire contract, paste ID here>",
        "  Starting: <first file or step>",
        "  ───────────────────────────────────────────────────────────────",
        "",
    ]
    text = "\n".join(lines)
    print(text)
    return text


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_issue(raw: str) -> tuple:
    parts = raw.split(":", 2)
    if len(parts) < 3:
        raise ValueError(f"--issue must be id:area:description, got: {raw!r}")
    return parts[0].strip(), parts[1].strip(), parts[2].strip()


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Create a worktree with auto-seeded wt_project.db (fractal lifecycle)."
    )
    ap.add_argument("slug",      help="Short slug, e.g. grove-fixes")
    ap.add_argument("repo",      help="Path to the git repo", nargs="?", default=".")
    ap.add_argument("--task",    help="One-line task description", default="")
    ap.add_argument(
        "--issue", metavar="id:area:desc",
        action="append", dest="issues", default=[],
        help="Seed an issue into wt_project.db (repeatable)"
    )
    args = ap.parse_args()

    repo_path = Path(args.repo).resolve()
    issues    = [_parse_issue(i) for i in args.issues]

    print(f"\nwt-create: slug={args.slug} repo={repo_path.name}")
    state = create_worktree(args.slug, repo_path, task=args.task, issues=issues)
    print_grove_post(state)
    print(f"  Done. Worktree at: {state['wt_path']}\n")


if __name__ == "__main__":
    main()
