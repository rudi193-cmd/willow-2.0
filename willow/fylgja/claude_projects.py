"""Resolve Claude Code session JSONL paths across project slug variants."""
from __future__ import annotations

from pathlib import Path

# Claude encodes cwd as a slug under ~/.claude/projects/. Symlink vs github/
# path produces different slugs for the same repo — scan all known variants.
CLAUDE_PROJECT_ROOTS: tuple[Path, ...] = (
    Path.home() / ".claude" / "projects" / "-home-sean-campbell-github-willow-2-0",
    Path.home() / ".claude" / "projects" / "-home-sean-campbell-willow-2-0",
)


def claude_jsonl_paths() -> list[Path]:
    out: list[Path] = []
    for root in CLAUDE_PROJECT_ROOTS:
        if root.is_dir():
            out.extend(root.glob("*.jsonl"))
    return out


def find_claude_jsonl(session_id: str) -> Path | None:
    for root in CLAUDE_PROJECT_ROOTS:
        path = root / f"{session_id}.jsonl"
        if path.is_file():
            return path
    return None


def latest_claude_session_id() -> str:
    jsonls = claude_jsonl_paths()
    if not jsonls:
        return ""
    return max(jsonls, key=lambda p: p.stat().st_mtime).stem
