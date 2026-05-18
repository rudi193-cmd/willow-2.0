#!/usr/bin/env python3
# b17: RNOV1  ΔΣ=42
"""
run_overseer.py — conductor for bounded initiatives (fylgja power: overseer).

What this script does WITHOUT Cursor hooks or skills:
  1) Phase 0 (local): optional ripgrep scan + optional public GitHub search
  2) Writes a run directory under <repo>/.overseer/runs/<id>/ (digest + MCP checklist)
  3) Human gate: you must APPROVE in the terminal before git changes
  4) Creates sibling git worktree: ../<basename>-wt-<slug> on branch wt/<slug>

What it does NOT do (must stay in-session with an AI + Willow MCP / Jeles):
  - willow_knowledge_search / willow_knowledge_ingest
  - jeles_fetch
  Those steps are written into MCP_CHECKLIST.md for copy-paste follow-up.

Usage:
  python3 scripts/run_overseer.py --goal "One sentence outcome" --slug my-initiative
  python3 scripts/run_overseer.py ... --dry-run
  python3 scripts/run_overseer.py ... --no-human-gate   # automation only; dangerous

Run from inside the target repo (or pass --repo).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path


def _run(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )


def git_toplevel(start: Path | None = None) -> Path:
    cp = _run(["git", "rev-parse", "--show-toplevel"], cwd=start or Path.cwd())
    if cp.returncode != 0:
        sys.stderr.write(cp.stderr or "git rev-parse failed\n")
        sys.exit(2)
    return Path(cp.stdout.strip()).resolve()


def default_branch(repo: Path) -> str:
    cp = _run(["git", "symbolic-ref", "--short", "HEAD"], cwd=repo)
    if cp.returncode == 0 and cp.stdout.strip():
        return cp.stdout.strip()
    cp = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)
    return cp.stdout.strip() or "master"


def sanitize_slug(raw: str) -> str:
    s = raw.lower().strip()
    s = re.sub(r"[^a-z0-9-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    if not s or not re.fullmatch(r"[a-z0-9-]+", s):
        sys.stderr.write("error: slug must match [a-z0-9-]+ after sanitize\n")
        sys.exit(2)
    return s


def have_rg() -> bool:
    return shutil.which("rg") is not None


def local_ripgrep_hits(repo: Path, patterns: list[str], max_hits: int) -> list[dict]:
    if not have_rg():
        return [{"note": "ripgrep (rg) not on PATH — skipped local multi-pattern scan"}]
    hits: list[dict] = []
    for pat in patterns:
        cp = _run(
            [
                "rg",
                "--line-number",
                "--max-count",
                str(max_hits),
                "--glob",
                "*.py",
                "--glob",
                "*.md",
                pat,
                str(repo),
            ],
            cwd=repo,
        )
        if cp.returncode not in (0, 1):
            hits.append({"pattern": pat, "error": (cp.stderr or cp.stdout or "").strip()[:500]})
            continue
        lines = [ln for ln in cp.stdout.splitlines() if ln.strip()][:max_hits]
        for ln in lines:
            hits.append({"pattern": pat, "line": ln[:400]})
    return hits[: max_hits * len(patterns)]


def github_repo_search(query: str, per_page: int = 5) -> dict | None:
    """Public GitHub API search (no token). Rate-limited; may fail."""
    q = urllib.parse.quote(query)
    url = f"https://api.github.com/search/repositories?q={q}&sort=stars&per_page={per_page}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        return {"error": str(e)}


@dataclass
class OverseerRun:
    run_id: str
    repo: str
    slug: str
    goal: str
    default_branch: str
    dry_run: bool
    created_at: str


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _store_overseer_record(
    *, slug: str, goal: str, branch: str, wt_path: Path, run_id: str, repo: Path
) -> None:
    agent = os.environ.get("WILLOW_AGENT_NAME")
    if not agent:
        print("[overseer] WILLOW_AGENT_NAME not set — skipping store write")
        return
    try:
        sys.path.insert(0, str(repo))
        from core.willow_store import WillowStore  # type: ignore
        store = WillowStore()
        store.put(f"{agent}/overseer", slug, {
            "slug": slug,
            "goal": goal,
            "branch": branch,
            "worktree": str(wt_path),
            "run_id": run_id,
            "status": "open",
        })
        print(f"[overseer] Store record written → {agent}/overseer/{slug}")
    except Exception as exc:
        print(f"[overseer] Store write skipped ({exc}) — add manually via store_put")


def main() -> None:
    p = argparse.ArgumentParser(description="Overseer conductor — Phase 0 + worktree gate")
    p.add_argument("--repo", type=Path, default=None, help="Git repo root (default: cwd toplevel)")
    p.add_argument("--slug", required=True, help="Initiative slug [a-z0-9-]+")
    p.add_argument("--goal", required=True, help="One-sentence outcome / measurable done")
    p.add_argument("--dry-run", action="store_true", help="Print actions only; no git writes")
    p.add_argument(
        "--no-human-gate",
        action="store_true",
        help="Skip APPROVE prompt (for CI); do not use for real initiatives",
    )
    p.add_argument(
        "--skip-local-scan",
        action="store_true",
        help="Skip ripgrep prior-art scan",
    )
    p.add_argument(
        "--github-query",
        default="",
        help="Optional public GitHub repo search query (e.g. 'magic-wormhole')",
    )
    args = p.parse_args()

    repo = (args.repo or git_toplevel()).resolve()
    slug = sanitize_slug(args.slug)
    branch = f"wt/{slug}"
    base = repo.name
    parent = repo.parent
    wt_path = parent / f"{base}-wt-{slug}"

    dbranch = default_branch(repo)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{ts}_{slug}"
    run_root = repo / ".overseer" / "runs" / run_id
    meta = OverseerRun(
        run_id=run_id,
        repo=str(repo),
        slug=slug,
        goal=args.goal,
        default_branch=dbranch,
        dry_run=bool(args.dry_run),
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    # --- Phase 0 local ---
    patterns = [
        r"u2u",
        r"GROVE_MCP_URL",
        r"ngrok-free",
        r"overseer",
        r"wt/",
    ]
    local_hits: list = []
    if not args.skip_local_scan:
        local_hits = local_ripgrep_hits(repo, patterns, max_hits=15)

    gh: dict | None = None
    if args.github_query.strip():
        gh = github_repo_search(args.github_query.strip())

    digest = textwrap.dedent(
        f"""\
        # Phase 0 digest (machine + local disk) — paste to Sean in chat

        **Run:** `{run_id}`
        **Repo:** `{repo}`
        **Goal:** {args.goal}
        **Default branch:** `{dbranch}` (do not commit initiative work here until ratified)

        ## Local ripgrep (subset)
        {json.dumps(local_hits[:40], indent=2)}

        ## Public GitHub search (optional, unauthenticated)
        {json.dumps(gh, indent=2) if gh is not None else "(no query)"}

        ## Fork question (fill in by hand after reading hits)
        - What on disk overlaps this initiative, and do we extend or replace it?

        ## MCP / Jeles (human or Cursor agent — same session)
        - `jeles_sources` then `jeles_fetch` for GitHub + HN as needed
        - `willow_knowledge_search` semantic on initiative keywords
        - Private org: use authenticated `gh search` if Jeles returns 404

        **Rule:** Sean sees this digest in **chat** before plan/spec hardens.
        """
    )

    mcp_checklist = textwrap.dedent(
        """\
        # MCP_CHECKLIST.md — run in Cursor / Claude with Willow connected

        1. `willow_health` (or `willow_status` if boot allowed)
        2. `willow_knowledge_search` — initiative + u2u + discovery + ngrok + Cloudflare
        3. `jeles_sources` / `jeles_fetch` — narrow questions, one hypothesis per call
        4. After Sean reacts: optional `willow_memory_check` → `willow_knowledge_ingest`

        Paste findings back to Sean in chat (do not file only in spec).
        """
    )

    if args.dry_run:
        print("[dry-run] Would create:", run_root)
        print("[dry-run] Would write digest + MCP checklist")
        print("[dry-run] Would prompt human gate unless --no-human-gate")
        print("[dry-run] Would: git worktree add", wt_path, branch)
        print("\n--- digest preview ---\n")
        print(digest)
        return

    run_root.mkdir(parents=True, exist_ok=True)
    write_text(run_root / "meta.json", json.dumps(asdict(meta), indent=2))
    write_text(run_root / "PHASE0_DIGEST.md", digest)
    write_text(run_root / "MCP_CHECKLIST.md", mcp_checklist)
    write_text(run_root / "local_hits.json", json.dumps(local_hits, indent=2))

    print(digest)
    print(f"\n[overseer] Wrote run artifacts under: {run_root}\n")

    if not args.no_human_gate:
        ans = input(
            "Type APPROVE (exactly) to create worktree, or anything else to abort: "
        ).strip()
        if ans != "APPROVE":
            print("[overseer] Aborted by operator — run dir kept for inspection.")
            sys.exit(1)

    # Refuse if paths exist
    if wt_path.exists():
        sys.stderr.write(f"error: worktree path already exists: {wt_path}\n")
        sys.exit(3)
    ref_check = _run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=repo)
    if ref_check.returncode == 0:
        sys.stderr.write(f"error: local branch already exists: {branch}\n")
        sys.exit(3)

    cmd = ["git", "worktree", "add", "-b", branch, str(wt_path), "HEAD"]
    print("[overseer] Running:", " ".join(cmd))
    cp = _run(cmd, cwd=repo)
    if cp.returncode != 0:
        sys.stderr.write(cp.stderr or cp.stdout or "git worktree add failed\n")
        sys.exit(4)

    head = _run(["git", "-C", str(wt_path), "rev-parse", "--short", "HEAD"])
    short = head.stdout.strip() if head.returncode == 0 else "?"

    _store_overseer_record(slug=slug, goal=args.goal, branch=branch,
                           wt_path=wt_path, run_id=run_id, repo=repo)

    closeout = textwrap.dedent(
        f"""\
        # CLOSEOUT.md

        - **Worktree path:** `{wt_path}`
        - **Branch:** `{branch}`
        - **HEAD:** `{short}`
        - **Not on `{dbranch}`:** initiative work happens only in this worktree until Sean ratifies merge.
        - **Run dir:** `{run_root}`
        - **Next bite:** (fill) first verifiable plan step inside the worktree

        Copy the bullet list above to Sean in chat.
        """
    )
    write_text(run_root / "CLOSEOUT.md", closeout)
    print(closeout)
    print(f"[overseer] Done. Open worktree: cd {wt_path}")


if __name__ == "__main__":
    main()
