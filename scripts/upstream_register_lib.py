"""Shared timeline + thread discovery for upstream desk analytics."""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".github" / "scripts"))
sys.path.insert(0, str(ROOT / "scripts"))

from update_tracker import AUTHOR, run_gh_search  # noqa: E402
from upstream_commenter_register_export import (  # noqa: E402
    _search_commenter_threads,
)
from upstream_pr_register_export import (  # noqa: E402
    Comment,
    _fetch_pr_meta,
    _fetch_pr_register,
    _gh_json,
    _gh_paginate_list,
    _is_bot,
    _repo_owner,
)

ISO_FMT = "%Y-%m-%d %H:%M UTC"


@dataclass
class ThreadRef:
    repo: str
    number: int
    title: str
    url: str
    state: str
    thread_author: str
    is_pull_request: bool
    you_author: bool  # operator opened the PR


@dataclass
class TimelineEvent:
    at: datetime
    login: str
    kind: str
    body: str
    is_operator: bool
    is_bot: bool
    meta: str = ""


@dataclass
class ThreadTimeline:
    thread: ThreadRef
    events: list[TimelineEvent] = field(default_factory=list)

    def operator_events(self) -> list[TimelineEvent]:
        return [e for e in self.events if e.is_operator and not e.is_bot]

    def maintainer_events(self) -> list[TimelineEvent]:
        return [e for e in self.events if not e.is_operator and not e.is_bot]


def _parse_ts(ts: str) -> datetime:
    if not ts or ts == "(PR opened)":
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.strptime(ts, ISO_FMT).replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def _comment_to_event(c: Comment, *, operator: str) -> TimelineEvent:
    return TimelineEvent(
        at=_parse_ts(c.at),
        login=c.login,
        kind=c.kind,
        body=c.body,
        is_operator=c.login.lower() == operator.lower(),
        is_bot=_is_bot(c.login),
        meta=c.meta,
    )


def _issue_comments_as_events(repo: str, number: int, *, operator: str) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    for c in _gh_paginate_list(f"repos/{repo}/issues/{number}/comments"):
        login = (c.get("user") or {}).get("login", "")
        body = (c.get("body") or "").strip()
        if not body:
            continue
        ts = c.get("created_at", "")
        if ts:
            at = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        else:
            at = datetime.min.replace(tzinfo=timezone.utc)
        events.append(
            TimelineEvent(
                at=at,
                login=login,
                kind="discussion",
                body=body,
                is_operator=login.lower() == operator.lower(),
                is_bot=_is_bot(login),
            )
        )
    return events


def collect_authored_threads(operator: str) -> list[ThreadRef]:
    open_prs = run_gh_search(["--state", "open"])
    merged_prs = run_gh_search(["--merged"])
    closed = run_gh_search(["--state", "closed"])
    merged_urls = {p["url"] for p in merged_prs}
    closed_only = [p for p in closed if p["url"] not in merged_urls]
    prs = open_prs + merged_prs + closed_only
    threads: list[ThreadRef] = []
    for pr in prs:
        repo = pr["repository"]["nameWithOwner"]
        threads.append(
            ThreadRef(
                repo=repo,
                number=pr["number"],
                title=pr.get("title", ""),
                url=pr.get("url", ""),
                state="",
                thread_author=operator,
                is_pull_request=True,
                you_author=True,
            )
        )
    # dedupe + fill state
    seen: set[tuple[str, int]] = set()
    out: list[ThreadRef] = []
    for t in threads:
        key = (t.repo, t.number)
        if key in seen:
            continue
        seen.add(key)
        try:
            meta = _fetch_pr_meta(t.repo, t.number)
            t.state = meta.get("state", "")
            t.title = meta.get("title", t.title)
            t.url = meta.get("url", t.url)
        except Exception:
            t.state = "UNKNOWN"
        out.append(t)
    return out


def collect_commenter_threads(operator: str) -> list[ThreadRef]:
    raw = _search_commenter_threads(operator)
    return [
        ThreadRef(
            repo=t["repo"],
            number=t["number"],
            title=t["title"],
            url=t["url"],
            state=t["state"],
            thread_author=t["thread_author"],
            is_pull_request=t["is_pull_request"],
            you_author=False,
        )
        for t in raw
    ]


def build_timeline(thread: ThreadRef, *, operator: str) -> ThreadTimeline:
    events: list[TimelineEvent] = []
    if thread.is_pull_request:
        reg = _fetch_pr_register(thread.repo, thread.number, operator=operator)
        events = [_comment_to_event(c, operator=operator) for c in reg.comments]
    else:
        events = _issue_comments_as_events(thread.repo, thread.number, operator=operator)

    events.sort(key=lambda e: (e.at, e.kind, e.login))
    return ThreadTimeline(thread=thread, events=events)


def all_threads(operator: str) -> list[ThreadRef]:
    authored = collect_authored_threads(operator)
    commenter = collect_commenter_threads(operator)
    seen = {(t.repo, t.number) for t in authored}
    merged = list(authored)
    for t in commenter:
        if (t.repo, t.number) not in seen:
            merged.append(t)
    return merged


def first_maintainer_reply_hours(tl: ThreadTimeline, *, operator: str) -> float | None:
    """Hours from operator's first comment to first non-bot non-operator reply."""
    op_events = [e for e in tl.events if e.is_operator and not e.is_bot and e.kind != "description"]
    if not op_events and tl.thread.you_author:
        op_events = [e for e in tl.events if e.is_operator and not e.is_bot]
    if not op_events:
        return None
    first_op = min(op_events, key=lambda e: e.at)
    for e in tl.events:
        if e.at <= first_op.at:
            continue
        if e.is_bot or e.is_operator:
            continue
        delta = e.at - first_op.at
        return delta.total_seconds() / 3600.0
    return None


def maintainer_reviewers(tl: ThreadTimeline, *, operator: str) -> set[str]:
    owner = ""
    try:
        owner = _repo_owner(tl.thread.repo)
    except Exception:
        pass
    out: set[str] = set()
    for e in tl.events:
        if e.is_bot or e.is_operator:
            continue
        if e.kind == "review" or e.login.lower() == owner.lower():
            out.add(e.login)
    return out


RE_FILE_LINK = re.compile(
    r"(?:willow-2\.0/blob/[^/]+/|master/|`)([A-Za-z0-9_./-]+\.(?:py|md|json|ya?ml))(?:`|\"|\)|\s|$)",
    re.I,
)
RE_BACKTICK_PATH = re.compile(r"`([A-Za-z0-9_./-]+\.(?:py|md|json|ya?ml))`")
RE_REREVIEW = re.compile(
    r"re-?review|friendly re-review ping|ready for another look|re-requested your review",
    re.I,
)
RE_SHIPPED = re.compile(
    r"\b(?:we shipped|shipped|landed in|stopgap in|what we shipped)\b",
    re.I,
)
RE_TEST_CLAIM = re.compile(r"(\d+)\s+pass.*0\s+fail", re.I)
