#!/usr/bin/env python3
"""
core/atom_extractor.py — Automatic atom extraction from commits, merges, and tests.

Extracts atoms when code lands so the KB stays synchronized with work actually done.
Prevents "work completed but KB forgot" problem.

Entry points:
  - extract_commit_atom(commit_hash) → atom dict
  - extract_merge_atom(merge_commit, branch_name) → atom dict
  - extract_test_atoms(before, after) → list[atom dict]
"""

import re
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional, Callable


@dataclass
class Atom:
    """Atom for the knowledge base."""
    title: str
    summary: str
    category: str  # feature|bugfix|refactor|test|docs|infra|session_summary
    source_type: str  # commit|merge|test_event|session_event
    b17: str
    content: dict
    created_at: Optional[str] = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self):
        return asdict(self)


def git_show(commit_hash: str) -> Optional[dict]:
    """Fetch commit details: message, diff, files changed."""
    try:
        result = subprocess.run(
            ["git", "show", "--format=fuller", commit_hash],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            return None

        lines = result.stdout.split("\n")

        # Extract message (everything after empty line following headers)
        msg_start = None
        for i, line in enumerate(lines):
            if line == "":
                msg_start = i + 1
                break

        message = "\n".join(lines[msg_start:]) if msg_start else ""

        return {
            "hash": commit_hash,
            "output": result.stdout,
            "message": message.strip(),
        }
    except Exception:
        return None


def parse_commit_message(msg: str) -> tuple[str, str, str]:
    """Parse commit message into (subject, intent, body).

    Subject: first line
    Intent: extracted from subject (what category of work)
    Body: everything after first line
    """
    lines = msg.split("\n")
    subject = lines[0] if lines else ""
    body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""

    # Extract intent from subject (e.g., "feat:", "fix:", "refactor:")
    intent_match = re.match(r"^(feat|fix|refactor|test|docs|perf|style|chore)\(?([^)]*)\)?:\s*(.*)", subject)
    if intent_match:
        prefix, scope, rest = intent_match.groups()
        return subject, prefix, body or rest

    return subject, "other", body


def infer_category(msg: str, files_changed: Optional[list] = None) -> str:
    """Infer atom category from commit message and files changed."""
    lower_msg = msg.lower()

    if any(x in lower_msg for x in ["feat", "feature", "add", "new"]):
        return "feature"
    elif any(x in lower_msg for x in ["fix", "bug", "resolv", "close", "broken"]):
        return "bugfix"
    elif any(x in lower_msg for x in ["refactor", "reorganiz", "restructur"]):
        return "refactor"
    elif any(x in lower_msg for x in ["test", "tests", "coverage"]):
        return "test"
    elif any(x in lower_msg for x in ["doc", "readme", "comment"]):
        return "docs"
    elif any(x in lower_msg for x in ["infra", "ci", "deploy", "docker", "systemd"]):
        return "infra"
    elif any(x in lower_msg for x in ["revert"]):
        return "revert"

    # Infer from files if message is unclear
    if files_changed:
        if any("test_" in f or f.endswith(".test.py") for f in files_changed):
            return "test"
        if any(f.endswith((".md", ".txt")) for f in files_changed):
            return "docs"

    return "refactor"  # Default


def extract_scope_from_diff(output: str) -> list[str]:
    """Extract list of files changed from git show output."""
    files = []
    for line in output.split("\n"):
        # Match "diff --git a/path b/path" lines
        match = re.match(r"diff --git a/(.*) b/.*", line)
        if match:
            files.append(match.group(1))
    return files


def extract_references(msg: str) -> dict:
    """Extract issue/PR references from commit message."""
    refs = {
        "issues": [],
        "prs": [],
        "commits": [],
    }

    # GitHub issue/PR: #123 or fixes #456
    for match in re.finditer(r"#(\d+)", msg):
        refs["issues"].append(f"#{match.group(1)}")

    # Commit refs (40-char SHA)
    for match in re.finditer(r"([a-f0-9]{7,40})", msg):
        refs["commits"].append(match.group(1))

    return {k: v for k, v in refs.items() if v}


def extract_commit_atom(commit_hash: str) -> Optional[Atom]:
    """Extract atom from a single commit."""
    commit = git_show(commit_hash)
    if not commit:
        return None

    subject, intent, body = parse_commit_message(commit["message"])
    files = extract_scope_from_diff(commit["output"])
    refs = extract_references(commit["message"])
    category = infer_category(commit["message"], files)

    # Skip merge commits, WIP, fixup, revert-that-was-reverted
    if subject.startswith("Merge"):
        return None
    if subject.startswith(("WIP", "fixup", "squash")):
        return None

    summary = f"{intent.capitalize()}: {body[:200] if body else subject}"
    if files:
        summary += f"\n\nFiles: {', '.join(files[:5])}" + (f" + {len(files)-5} more" if len(files) > 5 else "")

    if refs:
        summary += f"\n\nRefs: {refs}"

    return Atom(
        title=subject,
        summary=summary,
        category=category,
        source_type="commit",
        b17=commit_hash[:7],
        content={
            "commit": commit_hash,
            "files_changed": files,
            "references": refs,
            "intent": intent,
        }
    )


def git_log_range(start: str, end: str) -> Optional[list[str]]:
    """Get commits between start and end (exclusive start, inclusive end)."""
    try:
        result = subprocess.run(
            ["git", "log", "--format=%H", f"{start}..{end}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            return None
        return [h for h in result.stdout.strip().split("\n") if h]
    except Exception:
        return None


def synthesize_multi_commit_intent(commits: list[str]) -> str:
    """Synthesize intent from multiple commits."""
    if not commits:
        return "Unknown"

    subjects = []
    for commit_hash in commits[:5]:  # Look at first 5
        commit = git_show(commit_hash)
        if commit:
            subject, _, _ = parse_commit_message(commit["message"])
            subjects.append(subject)

    # Common theme
    all_msgs = " ".join(subjects).lower()

    if any(x in all_msgs for x in ["feat", "feature", "add"]):
        return "Feature: " + subjects[0][:60]
    elif any(x in all_msgs for x in ["fix", "bug"]):
        return "Bugfix: " + subjects[0][:60]
    elif any(x in all_msgs for x in ["refactor"]):
        return "Refactor: " + subjects[0][:60]

    return subjects[0][:80] if subjects else "Unknown"


def extract_merge_atom(merge_commit: str, branch_name: str) -> Optional[Atom]:
    """Extract atom from a merge (synthesizes all commits in the branch)."""
    commit = git_show(merge_commit)
    if not commit:
        return None

    # Get commits in the branch (assuming standard merge)
    # This is approximate — real implementation would use git merge-base
    commits = git_log_range(f"{merge_commit}^1", merge_commit)
    if not commits:
        commits = []

    intent = synthesize_multi_commit_intent(commits or [merge_commit])
    category = infer_category(intent)

    summary = f"{intent}\n\nMerged branch: {branch_name}\nCommits: {len(commits)}"

    return Atom(
        title=f"Merge: {branch_name}",
        summary=summary,
        category=category,
        source_type="merge",
        b17=f"{branch_name[:10]}_{merge_commit[:7]}".replace("/", "_"),
        content={
            "branch": branch_name,
            "commit": merge_commit,
            "commits_in_branch": commits,
            "commit_count": len(commits),
        }
    )


# Test-related extraction (stubs for now)

def extract_test_atoms(before_results: dict, after_results: dict) -> list[Atom]:
    """Extract atoms from test results changes."""
    atoms = []

    # Newly passing tests
    newly_passing = (after_results.get("passing", 0) or 0) - (before_results.get("passing", 0) or 0)
    if newly_passing > 0:
        atoms.append(Atom(
            title=f"Tests: {newly_passing} newly passing",
            summary=f"{newly_passing} test(s) now passing. Fixes verified.",
            category="test",
            source_type="test_event",
            b17=f"TEST_{newly_passing}P",
            content={"newly_passing": newly_passing}
        ))

    # Regressions
    regressions = (before_results.get("passing", 0) or 0) - (after_results.get("passing", 0) or 0)
    if regressions > 0:
        atoms.append(Atom(
            title=f"REGRESSION: {regressions} tests now failing",
            summary=f"{regressions} test(s) regressed. Needs investigation.",
            category="test",
            source_type="test_event",
            b17=f"TEST_{regressions}F",
            content={"regressions": regressions}
        ))

    return atoms
