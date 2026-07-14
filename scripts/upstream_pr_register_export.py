#!/usr/bin/env python3
"""
Export comments from upstream PRs (external repos authored by operator).

Pulls PR description, issue discussion, review bodies, and inline review comments.
Classifies human voices as: you, maintainer, or contributor. Bots go in a
separate section so every comment is retained.

Usage:
  python3 scripts/upstream_pr_register_export.py
  python3 scripts/upstream_pr_register_export.py --state open -o docs/upstream/PR_HUMAN_REGISTER_OPEN.md

Companion (your comments on others' threads): upstream_commenter_register_export.py
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

from update_tracker import AUTHOR, run_gh_search  # noqa: E402

_BOT_LOGINS = frozenset(
    {
        "github-actions[bot]",
        "renovate[bot]",
        "dependabot[bot]",
        "dependabot-preview[bot]",
        "gemini-code-assist[bot]",
        "gemini-code-assist",
        "coderabbitai[bot]",
        "deepsource-autofix[bot]",
        "snyk-bot",
        "codecov[bot]",
        "semantic-release-bot",
        "github-advanced-security[bot]",
    }
)

_ALMANAC_PROPAGATE_PREFIX = "Automated propagation of engine files"


@dataclass
class Comment:
    at: str
    sort_key: str
    login: str
    role: str
    kind: str
    body: str
    meta: str = ""
    comment_id: str = ""


@dataclass
class PrRegister:
    repo: str
    number: int
    title: str
    url: str
    state: str
    body: str
    comments: list[Comment] = field(default_factory=list)
    almanac_stub: bool = False


def _gh_raw(endpoint: str) -> str:
    result = subprocess.run(
        ["gh", "api", endpoint],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "gh failed")
    return result.stdout


def _gh_json(endpoint: str) -> object:
    text = _gh_raw(endpoint).strip()
    if not text:
        return []
    return json.loads(text)


def _gh_paginate_list(endpoint: str) -> list:
    """Page through gh REST collections (avoids brittle --paginate JSON concat)."""
    items: list = []
    page = 1
    while True:
        sep = "&" if "?" in endpoint else "?"
        batch = _gh_json(f"{endpoint}{sep}per_page=100&page={page}")
        if not isinstance(batch, list) or not batch:
            break
        items.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return items


def _fetch_pr_meta(repo: str, number: int) -> dict:
    """REST pull — avoids gh pr view --json body parse failures on huge descriptions."""
    pr = _gh_json(f"repos/{repo}/pulls/{number}")
    state = (pr.get("state") or "").upper()
    if pr.get("merged_at"):
        state = "MERGED"
    return {
        "title": pr.get("title", ""),
        "url": pr.get("html_url", ""),
        "state": state,
        "body": (pr.get("body") or "").strip(),
        "author": {"login": (pr.get("user") or {}).get("login", "")},
    }


def _is_bot(login: str) -> bool:
    if not login:
        return True
    low = login.lower()
    return low in _BOT_LOGINS or low.endswith("[bot]")


def _repo_owner(repo: str) -> str:
    data = _gh_json(f"repos/{repo}")
    return data["owner"]["login"]


def _reviewer_logins(repo: str, number: int) -> set[str]:
    reviews = _gh_paginate_list(f"repos/{repo}/pulls/{number}/reviews")
    logins: set[str] = set()
    for r in reviews:
        login = (r.get("user") or {}).get("login", "")
        if login:
            logins.add(login)
    return logins


def _classify_role(login: str, *, owner: str, reviewers: set[str], operator: str) -> str:
    if _is_bot(login):
        return "bot"
    if login.lower() == operator.lower():
        return "you"
    if login.lower() == owner.lower() or login in reviewers:
        return "maintainer"
    return "contributor"


def _iso(ts: str) -> str:
    if not ts:
        return ""
    return ts.replace("T", " ").replace("Z", " UTC")[:19]


def _sort_key(ts: str, *, opened: bool = False) -> str:
    if opened or not ts:
        return "0000-00-00 00:00:00"
    return _iso(ts)


def _append_comment(
    reg: PrRegister,
    *,
    login: str,
    body: str,
    kind: str,
    at: str,
    opened: bool = False,
    meta: str = "",
    comment_id: str = "",
    owner: str,
    reviewers: set[str],
    operator: str,
) -> None:
    text = (body or "").strip()
    if not text:
        return
    role = _classify_role(login, owner=owner, reviewers=reviewers, operator=operator)
    reg.comments.append(
        Comment(
            at="(PR opened)" if opened else _iso(at),
            sort_key=_sort_key(at, opened=opened),
            login=login,
            role=role,
            kind=kind,
            body=text,
            meta=meta,
            comment_id=str(comment_id) if comment_id else "",
        )
    )


def _is_almanac_stub(body: str) -> bool:
    return body.strip().startswith(_ALMANAC_PROPAGATE_PREFIX)


def _fetch_pr_register(repo: str, number: int, *, operator: str) -> PrRegister:
    meta = _fetch_pr_meta(repo, number)
    owner = _repo_owner(repo)
    reviewers = _reviewer_logins(repo, number)

    reg = PrRegister(
        repo=repo,
        number=number,
        title=meta.get("title", ""),
        url=meta.get("url", ""),
        state=meta.get("state", ""),
        body=(meta.get("body") or "").strip(),
    )
    reg.almanac_stub = _is_almanac_stub(reg.body)

    author_login = (meta.get("author") or {}).get("login", "")
    if reg.body and author_login:
        _append_comment(
            reg,
            login=author_login,
            body=reg.body,
            kind="description",
            at="",
            opened=True,
            owner=owner,
            reviewers=reviewers,
            operator=operator,
        )

    for c in _gh_paginate_list(f"repos/{repo}/issues/{number}/comments"):
        login = (c.get("user") or {}).get("login", "")
        _append_comment(
            reg,
            login=login,
            body=c.get("body", ""),
            kind="discussion",
            at=c.get("created_at", ""),
            comment_id=c.get("id", ""),
            owner=owner,
            reviewers=reviewers,
            operator=operator,
        )

    for r in _gh_paginate_list(f"repos/{repo}/pulls/{number}/reviews"):
        login = (r.get("user") or {}).get("login", "")
        state = r.get("state", "")
        _append_comment(
            reg,
            login=login,
            body=r.get("body", ""),
            kind="review",
            at=r.get("submitted_at", ""),
            meta=state,
            comment_id=r.get("id", ""),
            owner=owner,
            reviewers=reviewers,
            operator=operator,
        )

    for c in _gh_paginate_list(f"repos/{repo}/pulls/{number}/comments"):
        login = (c.get("user") or {}).get("login", "")
        path = c.get("path", "")
        line = c.get("line") or c.get("original_line") or ""
        loc = f"{path}:{line}" if path else ""
        reply = c.get("in_reply_to_id")
        if reply:
            loc = f"{loc} reply_to={reply}".strip()
        _append_comment(
            reg,
            login=login,
            body=c.get("body", ""),
            kind="inline",
            at=c.get("created_at", ""),
            meta=loc,
            comment_id=c.get("id", ""),
            owner=owner,
            reviewers=reviewers,
            operator=operator,
        )

    reg.comments.sort(key=lambda x: (x.sort_key, x.kind, x.comment_id, x.login))
    return reg


def _collect_prs(state: str) -> list[dict]:
    if state == "open":
        return run_gh_search(["--state", "open"])
    if state == "merged":
        return run_gh_search(["--merged"])
    if state == "closed":
        merged = run_gh_search(["--merged"])
        merged_urls = {p["url"] for p in merged}
        closed = run_gh_search(["--state", "closed"])
        return [p for p in closed if p["url"] not in merged_urls]
    open_prs = run_gh_search(["--state", "open"])
    merged_prs = run_gh_search(["--merged"])
    closed_prs = run_gh_search(["--state", "closed"])
    merged_urls = {p["url"] for p in merged_prs}
    closed_only = [p for p in closed_prs if p["url"] not in merged_urls]
    return open_prs + merged_prs + closed_only


def _render_comment_block(c: Comment) -> list[str]:
    kind_label = c.kind
    if c.meta:
        kind_label = f"{c.kind} ({c.meta})"
    id_suffix = f" · id={c.comment_id}" if c.comment_id else ""
    lines = [
        f"#### `{c.login}` · {c.at} · {kind_label}{id_suffix}",
        "",
        c.body,
        "",
    ]
    return lines


def _render_markdown(registers: list[PrRegister], *, operator: str, state_filter: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total_comments = sum(len(r.comments) for r in registers)
    lines = [
        "# Upstream PR comment register",
        "",
        f"*Generated: {now} · operator: `{operator}` · filter: `{state_filter}`*",
        "",
        "Every captured comment from GitHub (description, discussion, reviews, inline).",
        "Human voices grouped first; bots and automation in a separate section.",
        "",
        "- **You** — operator / PR author",
        "- **Maintainer** — repo owner or anyone who submitted a PR review",
        "- **Contributor** — other human participants",
        "- **Bots** — github-actions, dependabot, code assistants, etc.",
        "",
        f"**PRs processed:** {len(registers)} · **comments captured:** {total_comments}",
        "",
        "---",
        "",
    ]

    for reg in registers:
        lines.append(f"## {reg.repo} #{reg.number}")
        lines.append("")
        lines.append(f"**{reg.title}**")
        lines.append("")
        lines.append(f"- URL: {reg.url}")
        lines.append(f"- State: `{reg.state}`")
        if reg.almanac_stub:
            lines.append("- Almanac engine propagate (stub body — see description only)")
        lines.append("")

        if not reg.comments:
            lines.append("*No comments captured.*")
            lines.append("")
            lines.append("---")
            lines.append("")
            continue

        by_role: dict[str, list[Comment]] = {
            "you": [],
            "maintainer": [],
            "contributor": [],
            "bot": [],
        }
        for c in reg.comments:
            by_role.setdefault(c.role, []).append(c)

        for role_key, heading in (
            ("you", "### You"),
            ("maintainer", "### Maintainers"),
            ("contributor", "### Other contributors"),
            ("bot", "### Bots & automation"),
        ):
            items = by_role.get(role_key, [])
            if not items:
                continue
            lines.append(heading)
            lines.append("")
            for c in items:
                lines.extend(_render_comment_block(c))

        lines.append("---")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export upstream PR comment register to Markdown")
    parser.add_argument(
        "--state",
        choices=("open", "merged", "closed", "all"),
        default="all",
        help="Which PRs to include (default: all external upstream PRs)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=ROOT / "docs" / "upstream" / "PR_HUMAN_REGISTER.md",
        help="Output markdown path",
    )
    parser.add_argument(
        "--operator",
        default=AUTHOR,
        help=f"GitHub login treated as 'you' (default: {AUTHOR})",
    )
    args = parser.parse_args()

    print(f"Collecting PRs (state={args.state})...", file=sys.stderr)
    prs = _collect_prs(args.state)
    print(f"Found {len(prs)} PRs", file=sys.stderr)

    registers: list[PrRegister] = []
    errors = 0
    for i, pr in enumerate(prs, 1):
        repo = pr["repository"]["nameWithOwner"]
        number = pr["number"]
        print(f"[{i}/{len(prs)}] {repo}#{number}", file=sys.stderr)
        try:
            registers.append(_fetch_pr_register(repo, number, operator=args.operator))
        except Exception as exc:
            errors += 1
            print(f"  WARN: {exc}", file=sys.stderr)
            registers.append(
                PrRegister(
                    repo=repo,
                    number=number,
                    title=pr.get("title", ""),
                    url=pr.get("url", ""),
                    state="ERROR",
                    body=f"_fetch failed: {exc}_",
                )
            )

    md = _render_markdown(registers, operator=args.operator, state_filter=args.state)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(md, encoding="utf-8")
    print(
        f"Wrote {args.output} ({len(md)} bytes, {errors} errors)",
        file=sys.stderr,
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
