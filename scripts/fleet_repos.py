#!/usr/bin/env python3
"""Shared fleet repo roots for session discovery (Claude + Cursor JSONL).

Used by register_jeles_sessions, session_indexer, extract_atoms_from_sessions,
and fleet_session_sweep. Single source of truth — do not duplicate paths elsewhere.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

_GITHUB = Path.home() / "github"


@dataclass(frozen=True)
class FleetRepo:
    name: str
    cwd: Path
    claude_roots: tuple[Path, ...]
    cursor_roots: tuple[Path, ...]


FLEET_REPOS: tuple[FleetRepo, ...] = (
    FleetRepo(
        name="willow",
        cwd=_GITHUB / "willow",
        claude_roots=(
            Path.home() / ".claude/projects/-home-sean-campbell-github-willow",
        ),
        cursor_roots=(
            Path.home() / ".cursor/projects/home-sean-campbell-github-willow",
            Path.home() / ".cursor/projects/home-sean-campbell-willow",
        ),
    ),
    FleetRepo(
        name="willow-2.0",
        cwd=_GITHUB / "willow-2.0",
        claude_roots=(
            Path.home() / ".claude/projects/-home-sean-campbell-github-willow-2-0",
            Path.home() / ".claude/projects/-home-sean-campbell-willow-2-0",
        ),
        cursor_roots=(
            Path.home() / ".cursor/projects/home-sean-campbell-github-willow-2-0",
            Path.home() / ".cursor/projects/home-sean-campbell-willow-2-0",
        ),
    ),
    FleetRepo(
        name="safe-app-store-public",
        cwd=_GITHUB / "safe-app-store-public",
        claude_roots=(
            Path.home() / ".claude/projects/-home-sean-campbell-github-safe-app-store-public",
        ),
        cursor_roots=(
            Path.home() / ".cursor/projects/home-sean-campbell-github-safe-app-store-public",
        ),
    ),
    FleetRepo(
        name="DispatchesFromReality",
        cwd=_GITHUB / "DispatchesFromReality",
        claude_roots=(
            Path.home() / ".claude/projects/-home-sean-campbell-github-DispatchesFromReality",
        ),
        cursor_roots=(
            Path.home() / ".cursor/projects/home-sean-campbell-github-DispatchesFromReality",
        ),
    ),
)

FLEET_BY_NAME = {r.name: r for r in FLEET_REPOS}


def mtime_date(path: Path) -> date | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).date()
    except OSError:
        return None


def _claude_jsonl_paths(repo: FleetRepo) -> list[Path]:
    out: list[Path] = []
    for root in repo.claude_roots:
        if root.is_dir():
            out.extend(sorted(root.glob("*.jsonl")))
    return out


def _cursor_jsonl_paths(repo: FleetRepo) -> list[Path]:
    out: list[Path] = []
    for root in repo.cursor_roots:
        transcripts = root / "agent-transcripts"
        if not transcripts.is_dir():
            continue
        for session_dir in sorted(transcripts.iterdir()):
            if not session_dir.is_dir():
                continue
            path = session_dir / f"{session_dir.name}.jsonl"
            if path.is_file() and "tool-results" not in str(path):
                out.append(path.resolve())
    return out


def discover_jsonl_paths(
    *,
    since: date | None = None,
    project: str = "",
    include_claude: bool = True,
    include_cursor: bool = True,
    repos: tuple[FleetRepo, ...] | None = None,
) -> list[tuple[Path, FleetRepo]]:
    if repos is None:
        repos = (FLEET_BY_NAME[project],) if project else FLEET_REPOS
    seen: set[str] = set()
    out: list[tuple[Path, FleetRepo]] = []
    for repo in repos:
        paths: list[Path] = []
        if include_claude:
            paths.extend(_claude_jsonl_paths(repo))
        if include_cursor:
            paths.extend(_cursor_jsonl_paths(repo))
        for path in paths:
            key = str(path.resolve())
            if key in seen:
                continue
            if since is not None:
                mtime = mtime_date(path)
                if mtime is None or mtime < since:
                    continue
            seen.add(key)
            out.append((path, repo))
    return sorted(out, key=lambda item: (mtime_date(item[0]) or date.min, item[0].stem))


def nest_dir() -> Path:
    return Path(__import__("os").environ.get("NEST", str(Path.home() / "Desktop" / "Nest"))).expanduser()
