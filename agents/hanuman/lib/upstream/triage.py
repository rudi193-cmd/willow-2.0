"""
triage.py — Classify GitHub notifications into steward lanes.
b17: UPST1  ΔΣ=42

Lanes: noise | auto | watch | draft | urgent

Rules run first (cheap). LLM classifier reserved for ambiguous human comments.
"""
from __future__ import annotations

import re
from typing import NotRequired, TypedDict

WATCH_REPOS: list[str] = []  # populated from config at runtime


class Notification(TypedDict):
    id: str
    reason: str          # GitHub reason field
    subject_type: str    # PullRequest | Issue | Release | etc.
    subject_title: str
    subject_url: str
    repo: str
    updated_at: str
    unread: bool
    latest_comment_url: NotRequired[str]  # subject.latest_comment_url when present


Lane = str  # "noise" | "auto" | "watch" | "draft" | "urgent"

# PGP signing failures in worktrees — mechanic can advise, not a noise discard
# Upstream contributors hit this when their worktree doesn't inherit the signing key.
_PGP_PATTERNS = ("gpg failed to sign", "gpg: signing failed", "error: gpg failed")

# Reasons that almost always need a reply
_HUMAN_REASONS = {"mention", "review_requested", "assign"}
# Reasons that are usually background noise
_WATCH_REASONS = {"subscribed", "comment"}
# Bot name fragments — these authors rarely need replies
_BOT_FRAGMENTS = ("bot", "[bot]", "renovate", "dependabot", "github-actions")


def _is_bot_title(title: str) -> bool:
    lower = title.lower()
    return any(f in lower for f in ("ci:", "chore(deps)", "bump ", "update lock"))


def _is_ci_noise(n: Notification) -> bool:
    title = n["subject_title"].lower()
    return (
        n["reason"] in ("ci_activity", "subscribed")
        and any(kw in title for kw in ("ci:", "test:", "build:", "workflow run", "check run"))
    )


def classify(n: Notification, watch_repos: list[str] | None = None) -> Lane:
    """Return the steward lane for a notification."""
    repos = watch_repos or WATCH_REPOS
    repo = n["repo"]
    reason = n["reason"]
    s_type = n["subject_type"]
    title = n["subject_title"]

    # 0. PGP signing failure in worktree — auto before any noise discard
    # Contributor's worktree doesn't inherit the signing key; mechanic fix:
    #   git config commit.gpgsign false  (in the worktree)
    title_lower = title.lower()
    if any(p in title_lower for p in _PGP_PATTERNS):
        return "auto"

    # 1. Urgent — mentions, review requests, assignments
    if reason in _HUMAN_REASONS:
        return "urgent"

    # 2. Noise — CI activity on non-watched repos or bot titles
    if _is_ci_noise(n) and repo not in repos:
        return "noise"
    if _is_bot_title(title) and repo not in repos:
        return "noise"

    # 3. Release notifications — low-value
    if s_type == "Release":
        return "noise"

    # 4. Watch — open PRs waiting on maintainer, merged items
    merged_keywords = ("merged", "closed")
    if any(kw in title.lower() for kw in merged_keywords):
        return "watch"
    if s_type in ("PullRequest", "Issue") and reason == "subscribed" and repo not in repos:
        return "watch"

    # 5. Draft — human comment on watched repo or authored PR
    if reason == "comment" and s_type in ("PullRequest", "Issue"):
        if repo in repos:
            return "draft"
        # heuristic: if it's a comment not in a bot-title thread, likely needs reply
        if not _is_bot_title(title):
            return "draft"

    # 5b. Author-thread activity — GitHub uses reason=author when someone comments
    # on your issue/PR (not reason=comment). latest_comment_url is the signal.
    if (
        reason == "author"
        and s_type in ("PullRequest", "Issue")
        and n.get("latest_comment_url")
        and not _is_bot_title(title)
    ):
        return "draft"

    # 6. CI noise on any repo — already caught above if non-watched; catch watched too
    if _is_ci_noise(n):
        return "watch"  # watched repo CI — track but don't draft

    # default: watch (safe — will surface in digest, not inbox)
    return "watch"


def work_id(n: Notification) -> str:
    """Stable dedup key for a notification."""
    url = n.get("subject_url") or n.get("id") or "unknown"
    safe_url = re.sub(r"[^a-z0-9]", "-", url.lower())[-40:]
    return f"b17:UPST1-{safe_url}"
