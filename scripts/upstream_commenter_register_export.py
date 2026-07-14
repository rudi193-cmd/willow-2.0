#!/usr/bin/env python3
"""
Companion to upstream_pr_register_export.py — your comments on *others'* threads.

Discovers issues/PRs where you commented but are not the author (GitHub search:
commenter:YOU -author:YOU), on external repos only. Exports every comment you
left: discussion, reviews, and inline.

Usage:
  python3 scripts/upstream_commenter_register_export.py
  python3 scripts/upstream_commenter_register_export.py -o docs/upstream/COMMENTER_REGISTER.md
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
sys.path.insert(0, str(ROOT / "scripts"))

from update_tracker import AUTHOR, run_gh_graphql  # noqa: E402

# Reuse fetch/render helpers from the author-PR exporter.
from upstream_pr_register_export import (  # noqa: E402
    Comment,
    _fetch_pr_register,
    _gh_json,
    _gh_paginate_list,
    _iso,
    _render_comment_block,
    _sort_key,
)

COMMENTER_SEARCH = """
query($q: String!, $cursor: String) {
  search(query: $q, type: ISSUE, first: 100, after: $cursor) {
    issueCount
    pageInfo { hasNextPage endCursor }
    nodes {
      __typename
      ... on PullRequest {
        number
        title
        url
        state
        author { login }
        repository { nameWithOwner }
      }
      ... on Issue {
        number
        title
        url
        state
        author { login }
        repository { nameWithOwner }
      }
    }
  }
}
"""


@dataclass
class ThreadRegister:
    repo: str
    number: int
    title: str
    url: str
    state: str
    thread_author: str
    is_pull_request: bool
    your_comments: list[Comment] = field(default_factory=list)


def _is_external_repo(repo: str, operator: str) -> bool:
    return not repo.lower().startswith(f"{operator.lower()}/")


def _search_commenter_threads(operator: str) -> list[dict]:
    """Threads where operator commented but did not author."""
    q = f"commenter:{operator} -author:{operator}"
    threads: list[dict] = []
    seen: set[tuple[str, int]] = set()
    cursor = None
    while True:
        data = run_gh_graphql(COMMENTER_SEARCH, {"q": q, "cursor": cursor})
        search = data["search"]
        for node in search["nodes"]:
            if not node:
                continue
            repo = node["repository"]["nameWithOwner"]
            number = node["number"]
            if not _is_external_repo(repo, operator):
                continue
            key = (repo, number)
            if key in seen:
                continue
            seen.add(key)
            threads.append(
                {
                    "repo": repo,
                    "number": number,
                    "title": node.get("title", ""),
                    "url": node.get("url", ""),
                    "state": (node.get("state") or "").upper(),
                    "thread_author": (node.get("author") or {}).get("login", ""),
                    "is_pull_request": node.get("__typename") == "PullRequest",
                }
            )
        if not search["pageInfo"]["hasNextPage"]:
            break
        cursor = search["pageInfo"]["endCursor"]
    return threads


def _operator_comments_from_pr(repo: str, number: int, *, operator: str) -> list[Comment]:
    reg = _fetch_pr_register(repo, number, operator=operator)
    yours = [c for c in reg.comments if c.role == "you" and c.kind != "description"]
    return yours


def _operator_comments_from_issue(repo: str, number: int, *, operator: str) -> list[Comment]:
    comments: list[Comment] = []
    for c in _gh_paginate_list(f"repos/{repo}/issues/{number}/comments"):
        login = (c.get("user") or {}).get("login", "")
        if login.lower() != operator.lower():
            continue
        body = (c.get("body") or "").strip()
        if not body:
            continue
        at = c.get("created_at", "")
        comments.append(
            Comment(
                at=_iso(at),
                sort_key=_sort_key(at),
                login=login,
                role="you",
                kind="discussion",
                body=body,
                comment_id=str(c.get("id", "")),
            )
        )
    comments.sort(key=lambda x: (x.sort_key, x.comment_id))
    return comments


def _fetch_thread_register(thread: dict, *, operator: str) -> ThreadRegister:
    repo = thread["repo"]
    number = thread["number"]
    if thread["is_pull_request"]:
        yours = _operator_comments_from_pr(repo, number, operator=operator)
    else:
        yours = _operator_comments_from_issue(repo, number, operator=operator)

    return ThreadRegister(
        repo=repo,
        number=number,
        title=thread["title"],
        url=thread["url"],
        state=thread["state"],
        thread_author=thread["thread_author"],
        is_pull_request=thread["is_pull_request"],
        your_comments=yours,
    )


def _render_markdown(threads: list[ThreadRegister], *, operator: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total_comments = sum(len(t.your_comments) for t in threads)
    with_comments = sum(1 for t in threads if t.your_comments)

    lines = [
        "# Upstream commenter register (your voice on others' threads)",
        "",
        f"*Generated: {now} · operator: `{operator}`*",
        "",
        "Threads on **external** repos where you commented but are **not** the author.",
        "Companion to `PR_HUMAN_REGISTER.md` (your authored PRs).",
        "",
        "Includes discussion comments, review bodies, and inline review comments you left.",
        "",
        f"**Threads found:** {len(threads)} · **threads with your comments:** {with_comments}",
        f" · **your comments captured:** {total_comments}",
        "",
        "---",
        "",
    ]

    for t in threads:
        kind = "PR" if t.is_pull_request else "Issue"
        lines.append(f"## {t.repo} #{t.number}")
        lines.append("")
        lines.append(f"**{t.title}**")
        lines.append("")
        lines.append(f"- URL: {t.url}")
        lines.append(f"- Type: `{kind}` · State: `{t.state}`")
        lines.append(f"- Author: `{t.thread_author}`")
        lines.append("")

        if not t.your_comments:
            lines.append("*No operator comments captured (search hit but empty on fetch).*")
            lines.append("")
            lines.append("---")
            lines.append("")
            continue

        lines.append("### Your comments")
        lines.append("")
        for c in t.your_comments:
            lines.extend(_render_comment_block(c))
        lines.append("---")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export your GitHub comments on others' external threads"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=ROOT / "docs" / "upstream" / "COMMENTER_REGISTER.md",
        help="Output markdown path",
    )
    parser.add_argument(
        "--operator",
        default=AUTHOR,
        help=f"GitHub login (default: {AUTHOR})",
    )
    args = parser.parse_args()

    print(f"Searching commenter threads for {args.operator}...", file=sys.stderr)
    threads_raw = _search_commenter_threads(args.operator)
    print(f"Found {len(threads_raw)} external threads", file=sys.stderr)

    threads: list[ThreadRegister] = []
    errors = 0
    for i, thread in enumerate(threads_raw, 1):
        label = f"{thread['repo']}#{thread['number']}"
        print(f"[{i}/{len(threads_raw)}] {label}", file=sys.stderr)
        try:
            threads.append(_fetch_thread_register(thread, operator=args.operator))
        except Exception as exc:
            errors += 1
            print(f"  WARN: {exc}", file=sys.stderr)
            threads.append(
                ThreadRegister(
                    repo=thread["repo"],
                    number=thread["number"],
                    title=thread["title"],
                    url=thread["url"],
                    state="ERROR",
                    thread_author=thread.get("thread_author", ""),
                    is_pull_request=thread.get("is_pull_request", False),
                )
            )

    md = _render_markdown(threads, operator=args.operator)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(md, encoding="utf-8")
    print(f"Wrote {args.output} ({len(md)} bytes, {errors} errors)", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
