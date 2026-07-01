#!/usr/bin/env python3
"""repo_fleet_sweep.py — hygiene sweep across every git repo under a root.

Audit PR 8 (SYSTEM_AUDIT_2026-06-10, ecosystem sweep rev 6/7). Productizes the
read-only sweep that found the five fleet-wide patterns:

1. diverged repos (ahead AND behind upstream)
2. untracked deliverables (source-looking files outside git)
3. tracked-but-dirty runtime state (permanent dirt)
4. branch litter / stash↔atom parity
5. upstream clones with no upstream tracking
6. merged-but-present linked worktrees (clean + fully in default branch → reapable)

Read-only by design: reports and (optionally) raises SOIL flags. It never
fetches, pulls, deletes branches, or drops stashes (Tier 3: no autonomous
deletes; cleanup is offered as a report).

Usage:
    python3 scripts/repo_fleet_sweep.py                  # report to stdout
    python3 scripts/repo_fleet_sweep.py --root ~/github --branch-limit 10
    python3 scripts/repo_fleet_sweep.py --emit-flags     # also raise SOIL flags
    python3 scripts/repo_fleet_sweep.py --stash-parity   # check stash↔KB-atom parity
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

SOURCE_SUFFIXES = {".py", ".sh", ".js", ".ts", ".rs", ".go", ".md", ".sql", ".toml", ".json"}


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, timeout=30,
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _git_ok(repo: Path, *args: str) -> bool:
    """Run a git command for its exit status only (no stdout captured)."""
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, timeout=30,
    ).returncode == 0


def _default_branch(repo: Path) -> str | None:
    """The repo's integration branch — 'master' or 'main', whichever exists."""
    for b in ("master", "main"):
        if _git_ok(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{b}"):
            return b
    return None


def worktree_findings(repo: Path) -> list[str]:
    """Merged-but-present linked worktrees: clean AND fully contained in the
    default branch → safe to reap.

    A worktree is flagged only when all of these hold, so the operator can act
    on the report without re-verifying:
      - it is a linked worktree, not the primary checkout,
      - it tracks a real branch (detached HEADs are left for a human),
      - its working tree is clean (any uncommitted work → never flagged),
      - its HEAD is an ancestor of the default branch (fully merged).

    Read-only (Tier 3: report, never delete). Local refs only — the sweep does
    not fetch, so 'merged' means merged into the *local* default branch, which
    is safe against false positives (a not-yet-merged tip is never an ancestor).
    """
    porcelain = _git(repo, "worktree", "list", "--porcelain")
    if not porcelain:
        return []
    default = _default_branch(repo)
    if not default:
        return []

    blocks: list[dict[str, str]] = []
    cur: dict[str, str] = {}
    for line in porcelain.splitlines():
        if not line.strip():
            if cur:
                blocks.append(cur)
                cur = {}
            continue
        key, _, val = line.partition(" ")
        cur[key] = val
    if cur:
        blocks.append(cur)

    findings: list[str] = []
    for blk in blocks:
        wt = blk.get("worktree", "")
        if not wt or "bare" in blk or "detached" in blk:
            continue
        wt_path = Path(wt)
        if wt_path.resolve() == repo.resolve():
            continue  # the primary checkout is never a leftover
        head = blk.get("HEAD", "")
        branch = blk.get("branch", "").replace("refs/heads/", "")
        if not head or not branch or branch == default:
            continue
        if _git(wt_path, "status", "--porcelain"):
            continue  # uncommitted work — never flag
        if _git_ok(repo, "merge-base", "--is-ancestor", head, default):
            findings.append(
                f"merged worktree {wt_path.name!r} (branch {branch!r}) is clean and "
                f"fully in {default} — reap: git worktree remove {wt} "
                f"&& git branch -d {branch}"
            )
    return findings


def find_repos(root: Path) -> list[Path]:
    return sorted(
        p.parent for p in root.glob("*/.git")
        if p.is_dir() or p.is_file()  # plain repos and worktree/submodule pointers
    )


def survey_repo(repo: Path, branch_limit: int) -> dict:
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    status = _git(repo, "status", "--porcelain")
    lines = [ln for ln in status.splitlines() if ln.strip()]
    untracked = [ln[3:] for ln in lines if ln.startswith("??")]
    dirty_tracked = [ln for ln in lines if not ln.startswith("??")]

    ahead = behind = None
    upstream = _git(repo, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    if upstream:
        counts = _git(repo, "rev-list", "--left-right", "--count", f"{upstream}...HEAD")
        if counts:
            b, a = counts.split()
            ahead, behind = int(a), int(b)

    branches = _git(repo, "branch", "--format=%(refname:short)").splitlines()
    stashes = _git(repo, "stash", "list").splitlines()
    untracked_source = [f for f in untracked if Path(f).suffix in SOURCE_SUFFIXES]

    findings = []
    if ahead and behind:
        findings.append(f"diverged: ahead {ahead} / behind {behind} of {upstream}")
    elif ahead:
        findings.append(f"unpushed: ahead {ahead} of {upstream}")
    if branch != "master" and branch != "main" and not upstream:
        findings.append(f"on branch {branch!r} with no upstream tracking")
    if untracked_source:
        findings.append(f"{len(untracked_source)} untracked source files: "
                        + ", ".join(untracked_source[:5])
                        + (" …" if len(untracked_source) > 5 else ""))
    if len(dirty_tracked) >= 5:
        findings.append(f"{len(dirty_tracked)} tracked files dirty (runtime state in git?)")
    if len(branches) > branch_limit:
        findings.append(f"branch litter: {len(branches)} local branches")
    findings.extend(worktree_findings(repo))

    return {
        "repo": repo.name,
        "branch": branch,
        "upstream": upstream or None,
        "ahead": ahead,
        "behind": behind,
        "untracked": len(untracked),
        "untracked_source": untracked_source,
        "dirty_tracked": len(dirty_tracked),
        "branches": len(branches),
        "stashes": stashes,
        "findings": findings,
    }


def check_stash_parity(surveys: list[dict]) -> list[str]:
    """Fleet convention: every stash has a KB atom (verified: atom AAED75E5).

    Best-effort: search the knowledge table for 'stash' atoms and compare
    against live stashes. Degrades gracefully when Postgres is unreachable.
    """
    try:
        from core.pg_bridge import get_connection, release_connection
    except Exception as exc:  # pragma: no cover - import environment
        return [f"parity check skipped: pg_bridge unavailable ({exc})"]

    issues: list[str] = []
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT title, summary FROM knowledge "
                "WHERE (title ILIKE '%stash%' OR summary ILIKE '%stash%') "
                "AND invalid_at IS NULL"
            )
            atoms = cur.fetchall()
    except Exception as exc:
        return [f"parity check skipped: Postgres unreachable ({exc})"]
    finally:
        if conn is not None:
            release_connection(conn)

    atom_text = "\n".join(f"{t or ''} {s or ''}" for t, s in atoms).lower()
    for s in surveys:
        for stash in s["stashes"]:
            # stash line: "stash@{0}: On branch: message"
            msg = stash.split(":", 2)[-1].strip().lower()
            if msg and msg not in atom_text and s["repo"].lower() not in atom_text:
                issues.append(f"{s['repo']}: stash with no matching KB atom — {stash[:90]}")
    if not issues and any(s["stashes"] for s in surveys):
        issues.append("parity OK: every live stash matches KB atom text")
    return issues


def emit_flags(surveys: list[dict], agent: str) -> int:
    from core.soil import put

    count = 0
    for s in surveys:
        if not s["findings"]:
            continue
        flag_id = f"repo-sweep-{s['repo']}"
        put(f"{agent}/flags", flag_id, {
            "kind": "repo_hygiene",
            "repo": s["repo"],
            "findings": s["findings"],
            "fix_path": "operator review: push/reconcile, adopt or discard untracked, prune branches",
            "source": "scripts/repo_fleet_sweep.py",
            "status": "open",
        })
        count += 1
    return count


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=str(Path.home() / "github"))
    ap.add_argument("--branch-limit", type=int, default=15,
                    help="local branch count above this is litter (default 15)")
    ap.add_argument("--emit-flags", action="store_true",
                    help="raise a SOIL flag per repo with findings")
    ap.add_argument("--agent", default="willow", help="SOIL namespace for flags")
    ap.add_argument("--stash-parity", action="store_true",
                    help="check stash↔KB-atom parity (needs Postgres)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = ap.parse_args()

    root = Path(args.root).expanduser()
    repos = find_repos(root)
    surveys = [survey_repo(r, args.branch_limit) for r in repos]
    flagged = [s for s in surveys if s["findings"]]

    if args.json:
        print(json.dumps({"root": str(root), "repos": len(surveys),
                          "flagged": flagged}, indent=2))
    else:
        print(f"[repo-sweep] {len(surveys)} repos under {root}, "
              f"{len(flagged)} with findings, "
              f"{len(surveys) - len(flagged)} clean")
        for s in flagged:
            print(f"\n  {s['repo']} ({s['branch']})")
            for f in s["findings"]:
                print(f"    - {f}")

    if args.stash_parity:
        print("\n[repo-sweep] stash↔atom parity:")
        for line in check_stash_parity(surveys):
            print(f"  {line}")

    if args.emit_flags:
        n = emit_flags(surveys, args.agent)
        print(f"\n[repo-sweep] raised {n} SOIL flags in {args.agent}/flags")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
