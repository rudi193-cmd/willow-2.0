#!/usr/bin/env python3
"""
Upstream desk intelligence — maintainer heatmap (#1) + promise ledger (#3).

Reads live GitHub threads (authored external PRs + commenter threads), then writes:
  docs/upstream/MAINTAINER_HEATMAP.md
  docs/upstream/PROMISE_LEDGER.md

Usage:
  python3 scripts/upstream_desk_intel.py
  python3 scripts/upstream_desk_intel.py --heatmap-only
  python3 scripts/upstream_desk_intel.py --promises-only
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
sys.path.insert(0, str(ROOT / "scripts"))

from update_tracker import AUTHOR  # noqa: E402
from upstream_register_lib import (  # noqa: E402
    RE_BACKTICK_PATH,
    RE_FILE_LINK,
    RE_REREVIEW,
    RE_SHIPPED,
    RE_TEST_CLAIM,
    ThreadTimeline,
    all_threads,
    build_timeline,
    first_maintainer_reply_hours,
    maintainer_reviewers,
)


@dataclass
class RepoStats:
    repo: str
    threads: int = 0
    authored: int = 0
    commenter: int = 0
    open_count: int = 0
    merged_count: int = 0
    with_maintainer_reply: int = 0
    with_review: int = 0
    merged_no_review: int = 0
    response_hours: list[float] = field(default_factory=list)
    maintainers: set[str] = field(default_factory=set)
    stale_review: int = 0


@dataclass
class Promise:
    thread_label: str
    url: str
    at: str
    kind: str
    claim: str
    verdict: str
    evidence: str


def _lane(stats: RepoStats) -> str:
    if stats.merged_count and stats.merged_count >= stats.authored and stats.authored:
        return "warm"
    if stats.with_review or stats.with_maintainer_reply:
        return "warm"
    if stats.open_count and stats.stale_review:
        return "cold"
    if stats.open_count and not stats.with_maintainer_reply:
        return "cold"
    if stats.open_count:
        return "yellow"
    return "neutral"


def _median(values: list[float]) -> str:
    if not values:
        return "—"
    s = sorted(values)
    mid = len(s) // 2
    if len(s) % 2:
        return f"{s[mid]:.1f}h"
    return f"{(s[mid - 1] + s[mid]) / 2:.1f}h"


def _pr_review_decision(repo: str, number: int) -> str:
    try:
        data = subprocess.run(
            [
                "gh",
                "pr",
                "view",
                str(number),
                "--repo",
                repo,
                "--json",
                "reviewDecision,state,mergedAt",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        import json

        meta = json.loads(data.stdout)
        return meta.get("reviewDecision") or meta.get("state") or ""
    except Exception:
        return ""


WILLOW_PATH_PREFIXES = ("sap/", "core/", "willow/", "agents/", "scripts/", "docs/", "tests/")


def _normalize_willow_path(path: str) -> str:
    rel = path.lstrip("./").strip()
    if "willow-2.0/blob/" in rel:
        rel = rel.split("willow-2.0/blob/", 1)[1]
        if "/" in rel:
            rel = rel.split("/", 1)[1]
    return rel


def _is_willow_repo_path(path: str) -> bool:
    rel = _normalize_willow_path(path)
    return any(rel.startswith(p) for p in WILLOW_PATH_PREFIXES)


def _verify_file_path(path: str) -> tuple[str, str]:
    if not _is_willow_repo_path(path):
        rel = path.lstrip("./")
        return "EXTERNAL", f"target-repo path (not checked in willow-2.0): `{rel}`"
    rel = _normalize_willow_path(path)
    full = ROOT / rel
    if full.is_file():
        return "VERIFIED", f"exists at `{rel}`"
    return "STALE", f"missing at `{rel}` (willow-2.0 HEAD)"


def _extract_promises(tl: ThreadTimeline, *, operator: str) -> list[Promise]:
    label = f"{tl.thread.repo} #{tl.thread.number}"
    promises: list[Promise] = []

    for e in tl.operator_events():
        body = e.body
        at = e.at.strftime("%Y-%m-%d %H:%M UTC") if e.at.year > 1970 else ""

        paths: set[str] = set()
        for pat in (RE_FILE_LINK, RE_BACKTICK_PATH):
            for m in pat.finditer(body):
                p = m.group(1).strip()
                if "/" in p or p.endswith((".py", ".md")):
                    paths.add(p)

        for path in sorted(paths):
            verdict, evidence = _verify_file_path(path)
            promises.append(
                Promise(
                    thread_label=label,
                    url=tl.thread.url,
                    at=at,
                    kind="file_reference",
                    claim=f"Referenced `{path}`",
                    verdict=verdict,
                    evidence=evidence,
                )
            )

        if RE_REREVIEW.search(body) and tl.thread.is_pull_request:
            decision = _pr_review_decision(tl.thread.repo, tl.thread.number)
            state = tl.thread.state
            if state == "MERGED":
                verdict, evidence = "VERIFIED", "PR merged — re-review moot"
            elif decision == "CHANGES_REQUESTED":
                verdict, evidence = "STALE", f"still OPEN with `{decision}`"
            elif state == "OPEN":
                verdict, evidence = "OPEN", f"PR open; reviewDecision=`{decision or 'none'}`"
            else:
                verdict, evidence = "OPEN", f"state=`{state}`"
            promises.append(
                Promise(
                    thread_label=label,
                    url=tl.thread.url,
                    at=at,
                    kind="re_review_ping",
                    claim="Re-review / ready for another look",
                    verdict=verdict,
                    evidence=evidence,
                )
            )

        if RE_SHIPPED.search(body):
            promises.append(
                Promise(
                    thread_label=label,
                    url=tl.thread.url,
                    at=at,
                    kind="shipped_claim",
                    claim="Asserted shipped / stopgap / landed",
                    verdict="ADVISORY",
                    evidence="manual verify — check linked PRs or willow-2.0 master",
                )
            )

        m = RE_TEST_CLAIM.search(body)
        if m:
            promises.append(
                Promise(
                    thread_label=label,
                    url=tl.thread.url,
                    at=at,
                    kind="test_claim",
                    claim=f"Claimed {m.group(0)}",
                    verdict="ADVISORY",
                    evidence="re-run tests to confirm still true",
                )
            )

    return promises


def build_heatmap(threads: list, *, operator: str) -> tuple[list[RepoStats], list[ThreadTimeline]]:
    by_repo: dict[str, RepoStats] = {}
    timelines: list[ThreadTimeline] = []

    for i, thread in enumerate(threads, 1):
        print(f"[heatmap {i}/{len(threads)}] {thread.repo}#{thread.number}", file=sys.stderr)
        tl = build_timeline(thread, operator=operator)
        timelines.append(tl)
        repo = thread.repo
        stats = by_repo.setdefault(repo, RepoStats(repo=repo))
        stats.threads += 1
        if thread.you_author:
            stats.authored += 1
        else:
            stats.commenter += 1
        if thread.state == "OPEN":
            stats.open_count += 1
        elif thread.state == "MERGED":
            stats.merged_count += 1

        reviewers = maintainer_reviewers(tl, operator=operator)
        stats.maintainers |= reviewers
        if reviewers:
            stats.with_review += 1

        hrs = first_maintainer_reply_hours(tl, operator=operator)
        if hrs is not None:
            stats.with_maintainer_reply += 1
            stats.response_hours.append(hrs)

        if thread.you_author and thread.is_pull_request and thread.state == "MERGED":
            if not reviewers:
                stats.merged_no_review += 1

        if thread.is_pull_request and thread.state == "OPEN":
            decision = _pr_review_decision(thread.repo, thread.number)
            if decision == "CHANGES_REQUESTED":
                stats.stale_review += 1

    return sorted(by_repo.values(), key=lambda s: (-s.threads, s.repo)), timelines


def render_heatmap(stats_list: list[RepoStats], *, operator: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Upstream maintainer heatmap",
        "",
        f"*Generated: {now} · operator: `{operator}`*",
        "",
        "Repos where you have upstream threads (authored PRs + commenter threads).",
        "**Lane:** `warm` = human review or merge signal · `yellow` = open, waiting · `cold` = open, no maintainer reply or stale CHANGES_REQUESTED",
        "",
        "| Repo | Threads | Auth | Cmt | Open | Merged | Reply | Review | Median reply | Merged (no review) | Stale CR | Lane | Maintainers |",
        "|------|---------|------|-----|------|--------|-------|--------|--------------|-------------------|----------|------|-------------|",
    ]
    for s in stats_list:
        lane = _lane(s)
        maintainers = ", ".join(sorted(s.maintainers)[:4]) or "—"
        if len(s.maintainers) > 4:
            maintainers += f" +{len(s.maintainers) - 4}"
        lines.append(
            f"| {s.repo} | {s.threads} | {s.authored} | {s.commenter} | {s.open_count} | "
            f"{s.merged_count} | {s.with_maintainer_reply} | {s.with_review} | "
            f"{_median(s.response_hours)} | {s.merged_no_review} | {s.stale_review} | "
            f"**{lane}** | {maintainers} |"
        )

    lines.extend(["", "## Lane notes", ""])
    warm = [s.repo for s in stats_list if _lane(s) == "warm"]
    cold = [s.repo for s in stats_list if _lane(s) == "cold"]
    if warm:
        lines.append(f"- **Warm ({len(warm)}):** " + ", ".join(warm[:12]) + ("…" if len(warm) > 12 else ""))
    if cold:
        lines.append(f"- **Cold ({len(cold)}):** " + ", ".join(cold))
    lines.append("")
    return "\n".join(lines) + "\n"


def render_promises(promises: list[Promise], *, operator: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    by_verdict: dict[str, list[Promise]] = defaultdict(list)
    for p in promises:
        by_verdict[p.verdict].append(p)

    lines = [
        "# Upstream promise ledger",
        "",
        f"*Generated: {now} · operator: `{operator}`*",
        "",
        "Claims extracted from **your** comments (authored + commenter registers).",
        "Auto-checks: file paths on disk · re-review pings vs live PR state.",
        "",
        f"**Total claims:** {len(promises)} · "
        f"VERIFIED: {len(by_verdict.get('VERIFIED', []))} · "
        f"STALE: {len(by_verdict.get('STALE', []))} · "
        f"OPEN: {len(by_verdict.get('OPEN', []))} · "
        f"EXTERNAL: {len(by_verdict.get('EXTERNAL', []))} · "
        f"ADVISORY: {len(by_verdict.get('ADVISORY', []))}",
        "",
        "---",
        "",
    ]

    for verdict in ("STALE", "OPEN", "ADVISORY", "EXTERNAL", "VERIFIED"):
        items = by_verdict.get(verdict, [])
        if not items:
            continue
        lines.append(f"## {verdict} ({len(items)})")
        lines.append("")
        for p in items:
            lines.append(f"### {p.thread_label}")
            lines.append("")
            lines.append(f"- URL: {p.url}")
            lines.append(f"- When: {p.at or '—'}")
            lines.append(f"- Kind: `{p.kind}`")
            lines.append(f"- Claim: {p.claim}")
            lines.append(f"- Evidence: {p.evidence}")
            lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def emit_soil_summary(
    stats_list: list[RepoStats],
    *,
    thread_count: int,
    operator: str,
    error: str = "",
) -> dict:
    """Persist desk intel summary to SOIL for weekly scheduling + digest."""
    from core import soil
    from core.upstream_desk_state import format_upstream_desk_summary_line

    cold = [s for s in stats_list if _lane(s) == "cold"]
    warm = [s for s in stats_list if _lane(s) == "warm"]
    state = {
        "last_run_at": datetime.now(timezone.utc).isoformat(),
        "operator": operator,
        "thread_count": thread_count,
        "repo_count": len(stats_list),
        "cold_count": len(cold),
        "warm_count": len(warm),
        "cold_repos": [s.repo for s in cold],
        "heatmap_path": "docs/upstream/MAINTAINER_HEATMAP.md",
        "promises_path": "docs/upstream/PROMISE_LEDGER.md",
        "locked": False,
    }
    if error:
        state["last_error"] = error
    soil.put("upstream_steward/desk_intel", "state", state)
    line = format_upstream_desk_summary_line(state)
    print(f"SOIL upstream_steward/desk_intel: {line}", file=sys.stderr)
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description="Upstream maintainer heatmap + promise ledger")
    parser.add_argument("--operator", default=AUTHOR)
    parser.add_argument(
        "--heatmap-out",
        type=Path,
        default=ROOT / "docs" / "upstream" / "MAINTAINER_HEATMAP.md",
    )
    parser.add_argument(
        "--promises-out",
        type=Path,
        default=ROOT / "docs" / "upstream" / "PROMISE_LEDGER.md",
    )
    parser.add_argument("--heatmap-only", action="store_true")
    parser.add_argument("--promises-only", action="store_true")
    parser.add_argument(
        "--emit-soil",
        action="store_true",
        help="Write summary to SOIL upstream_steward/desk_intel/state (weekly Kart)",
    )
    args = parser.parse_args()

    do_heatmap = not args.promises_only
    do_promises = not args.heatmap_only

    if args.emit_soil:
        from core import soil

        prior = soil.get("upstream_steward/desk_intel", "state") or {}
        soil.put(
            "upstream_steward/desk_intel",
            "state",
            {
                **prior,
                "locked": True,
                "lock_acquired_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    print("Collecting threads...", file=sys.stderr)
    threads = all_threads(args.operator)
    print(f"Total threads: {len(threads)}", file=sys.stderr)

    stats_list: list[RepoStats] = []
    timelines: list[ThreadTimeline] = []

    try:
        if do_heatmap or do_promises:
            stats_list, timelines = build_heatmap(threads, operator=args.operator)

        args.heatmap_out.parent.mkdir(parents=True, exist_ok=True)

        if do_heatmap:
            md = render_heatmap(stats_list, operator=args.operator)
            args.heatmap_out.write_text(md, encoding="utf-8")
            print(f"Wrote {args.heatmap_out}", file=sys.stderr)

        if do_promises:
            all_promises: list[Promise] = []
            for tl in timelines:
                all_promises.extend(_extract_promises(tl, operator=args.operator))
            md = render_promises(all_promises, operator=args.operator)
            args.promises_out.write_text(md, encoding="utf-8")
            print(f"Wrote {args.promises_out} ({len(all_promises)} claims)", file=sys.stderr)

        if args.emit_soil:
            emit_soil_summary(stats_list, thread_count=len(threads), operator=args.operator)
    except Exception as exc:
        if args.emit_soil:
            from core import soil

            prior = soil.get("upstream_steward/desk_intel", "state") or {}
            soil.put(
                "upstream_steward/desk_intel",
                "state",
                {**prior, "locked": False, "last_error": str(exc)},
            )
        raise

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
