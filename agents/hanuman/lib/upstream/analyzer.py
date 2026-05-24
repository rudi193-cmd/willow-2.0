"""
analyzer.py — Fetch GitHub thread context for a pending work item.
b17: UPST1  ΔΣ=42

Builds a thread bundle: their comment, prior replies, fun bits, open questions,
CI state. Input to voice_drafter.

Never posts. Never writes to GitHub. Read-only.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from typing import Any

# Keywords that signal something worth a warm reply
_FUN_PHRASES = (
    "offered to", "happy to", "would you", "let me know",
    "great work", "nice ", "love this", "brilliant",
    "when you have a moment", "no rush", "just wanted",
    "appreciate", "thank you", "thanks for", "good catch",
    "assigned", "mentioned you", "ping me",
)

# Signals an open question worth addressing
_QUESTION_SIGNALS = (
    "?", "wondering", "curious", "not sure", "unclear",
    "should we", "could we", "what do you think", "any thoughts",
    "is this intentional", "was this on purpose",
)


def _gh(*args: str) -> Any:
    result = subprocess.run(
        ["gh", *args],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return json.loads(result.stdout) if result.stdout.strip().startswith(("{", "[")) else result.stdout


def _extract_fun_bits(text: str) -> list[str]:
    bits = []
    for sentence in re.split(r"[.!]\s+", text):
        s = sentence.strip().lower()
        if any(phrase in s for phrase in _FUN_PHRASES):
            bits.append(sentence.strip()[:120])
    return bits[:3]


def _extract_questions(text: str) -> list[str]:
    questions = []
    for sentence in re.split(r"[.!]\s+", text):
        s = sentence.strip()
        if any(sig in s.lower() for sig in _QUESTION_SIGNALS) and len(s) > 10:
            questions.append(s[:120])
    return questions[:4]


def _fetch_pr(repo: str, number: int) -> dict:
    try:
        meta = _gh("pr", "view", str(number), "--repo", repo,
                   "--json", "title,url,state,mergeable,mergeStateStatus,statusCheckRollup,reviews,comments")
    except Exception as exc:
        return {"error": str(exc)}

    comments_raw = meta.get("comments", [])
    reviews_raw = meta.get("reviews", [])

    # Most recent non-bot comment from someone else
    author_login = ""
    their_comment = ""
    for c in reversed(comments_raw):
        login = c.get("author", {}).get("login", "")
        body = c.get("body", "").strip()
        if login and login.lower() not in ("github-actions[bot]", "renovate[bot]") and body:
            author_login = login
            their_comment = body[:800]
            break

    # Most recent review comment
    for r in reversed(reviews_raw):
        login = r.get("author", {}).get("login", "")
        body = r.get("body", "").strip()
        if login and body and not their_comment:
            author_login = login
            their_comment = body[:800]
            break

    ci_checks = meta.get("statusCheckRollup", [])
    ci_state = "unknown"
    if ci_checks:
        states = {c.get("conclusion") or c.get("status", "") for c in ci_checks}
        if "FAILURE" in states or "FAILED" in states:
            ci_state = "failing"
        elif all(s in ("SUCCESS", "COMPLETED") for s in states):
            ci_state = "passing"
        else:
            ci_state = "pending"

    mergeable = meta.get("mergeStateStatus", meta.get("mergeable", "UNKNOWN"))

    return {
        "kind": "pr_comment",
        "author": author_login,
        "their_comment": their_comment,
        "fun_bits": _extract_fun_bits(their_comment),
        "open_questions": _extract_questions(their_comment),
        "ci_state": ci_state,
        "mergeable": str(mergeable).lower(),
        "pr_state": meta.get("state", ""),
        "needs_reply": bool(their_comment),
    }


def _fetch_issue(repo: str, number: int) -> dict:
    try:
        meta = _gh("issue", "view", str(number), "--repo", repo,
                   "--json", "title,url,state,comments,assignees,labels")
    except Exception as exc:
        return {"error": str(exc)}

    comments_raw = meta.get("comments", [])
    their_comment = ""
    author_login = ""
    for c in reversed(comments_raw):
        login = c.get("author", {}).get("login", "")
        body = c.get("body", "").strip()
        if login and "[bot]" not in login.lower() and body:
            author_login = login
            their_comment = body[:800]
            break

    return {
        "kind": "issue_comment",
        "author": author_login,
        "their_comment": their_comment,
        "fun_bits": _extract_fun_bits(their_comment),
        "open_questions": _extract_questions(their_comment),
        "ci_state": "n/a",
        "mergeable": "n/a",
        "issue_state": meta.get("state", ""),
        "needs_reply": bool(their_comment),
    }


def _parse_number(url: str) -> tuple[str, int] | None:
    """Extract (repo, number) from a GitHub API URL."""
    m = re.search(r"repos/([^/]+/[^/]+)/(?:pulls|issues)/(\d+)", url or "")
    if m:
        return m.group(1), int(m.group(2))
    # Also handle html URLs
    m = re.search(r"github\.com/([^/]+/[^/]+)/(?:pull|issues)/(\d+)", url or "")
    if m:
        return m.group(1), int(m.group(2))
    return None


def analyze(pending: dict) -> dict:
    """
    Enrich a pending SOIL record with thread context.
    Returns updated fields to merge into the record.
    """
    url = pending.get("url", "")
    kind = pending.get("kind", "")
    repo = pending.get("repo", "")

    parsed = _parse_number(url)
    if not parsed:
        return {"their_comment": "", "open_questions": [], "fun_bits": [], "analyze_error": "no url"}

    repo_from_url, number = parsed
    repo = repo_from_url or repo

    try:
        if "pull" in url.lower() or kind in ("pullrequest", "pr_comment"):
            bundle = _fetch_pr(repo, number)
        else:
            bundle = _fetch_issue(repo, number)
    except Exception as exc:
        return {"analyze_error": str(exc)}

    return {
        "their_comment": bundle.get("their_comment", ""),
        "open_questions": bundle.get("open_questions", []),
        "fun_bits": bundle.get("fun_bits", []),
        "ci_state": bundle.get("ci_state", "unknown"),
        "mergeable": bundle.get("mergeable", "unknown"),
        "needs_reply": bundle.get("needs_reply", False),
        "author": bundle.get("author", ""),
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: analyzer.py <github_url_or_pr_number> [repo]")
        sys.exit(1)
    url = sys.argv[1]
    repo = sys.argv[2] if len(sys.argv) > 2 else ""
    result = analyze({"url": url, "repo": repo, "kind": "pullrequest"})
    print(json.dumps(result, indent=2))
