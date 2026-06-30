"""
handoff_project.py — Resolve fleet project id for handoff read/write scoping.

Handoffs are keyed by (agent, project). Project ids come from the MCP fleet
registry ($WILLOW_HOME/mcp/projects.json) when registered; otherwise the repo
folder name under ~/github.
"""
from __future__ import annotations

import os
from pathlib import Path

from willow.fylgja.project_wiring import expand_home

DEFAULT_LEGACY_PROJECT = "willow-2.0"


def _github_root() -> Path:
    return Path.home() / "github"


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _registry_projects() -> list[tuple[Path, str]]:
    rows: list[tuple[Path, str]] = []
    try:
        from willow.fylgja.mcp_projects import load_registry

        reg = load_registry(bootstrap=False)
    except Exception:
        return rows
    for pid, entry in (reg.get("projects") or {}).items():
        if not isinstance(entry, dict):
            continue
        raw = str(entry.get("path") or "").strip()
        if not raw:
            continue
        try:
            rows.append((Path(expand_home(raw)).resolve(), str(pid)))
        except OSError:
            continue
    rows.sort(key=lambda pair: len(str(pair[0])), reverse=True)
    return rows


def _github_repo_slug(path: Path) -> str:
    """First path component under ~/github, or repo basename when cwd is inside a git tree."""
    resolved = path.resolve()
    github = _github_root()
    if not _is_under(resolved, github):
        if (resolved / ".git").is_dir():
            return resolved.name
        return ""
    rel = resolved.relative_to(github.resolve())
    if not rel.parts:
        return ""
    return rel.parts[0]


def _probe_paths(start: Path | None) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []

    def _add(path: Path) -> None:
        try:
            key = str(path.resolve())
        except OSError:
            return
        if key in seen:
            return
        seen.add(key)
        out.append(path)

    raw = os.environ.get("WILLOW_PROJECT_ROOT", "").strip()
    if raw:
        _add(Path(raw))
    if start is not None:
        _add(start)
    _add(Path.cwd())
    return out


def resolve_handoff_project(start: Path | None = None) -> str:
    """Return fleet project id for handoff scoping, or '' when unknown."""
    override = os.environ.get("WILLOW_HANDOFF_PROJECT", "").strip()
    if override:
        return override

    registry = _registry_projects()
    for probe in _probe_paths(start):
        try:
            resolved = probe.resolve()
        except OSError:
            continue
        for root, pid in registry:
            if resolved == root or _is_under(resolved, root):
                return pid
        slug = _github_repo_slug(resolved)
        if slug:
            return slug
    return ""


def normalize_handoff_project(project: str | None) -> str:
    return (project or "").strip()


def handoff_project_matches(stored: str | None, requested: str) -> bool:
    """True when a handoff row belongs to the requested project scope."""
    req = normalize_handoff_project(requested)
    if not req:
        return True
    got = normalize_handoff_project(stored)
    if got:
        return got == req
    return req == DEFAULT_LEGACY_PROJECT
