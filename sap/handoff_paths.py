"""Resolve canonical handoff directories and SQLite index paths."""
from __future__ import annotations

from pathlib import Path

from willow.fylgja.willow_home import fleet_home as willow_home
from willow.fylgja.willow_home import private_home, willow_home_alias


def handoffs_root() -> Path:
    """Directory containing per-agent handoff folders."""
    return willow_home() / "handoffs"


def handoffs_roots() -> list[Path]:
    """Handoff parent dirs: active WILLOW_HOME plus private fleet mirror when distinct."""
    roots: list[Path] = []
    seen: set[str] = set()
    for candidate in (
        handoffs_root(),
        private_home() / "handoffs",
        willow_home_alias() / "handoffs",
    ):
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        key = str(resolved)
        if key in seen or not resolved.is_dir():
            continue
        roots.append(resolved)
        seen.add(key)
    return roots


def handoff_db_path(agent: str) -> Path:
    return handoffs_root() / agent / "handoffs.db"


def resolve_agent_handoff_file(agent: str, filename: str) -> Path | None:
    """Locate a session handoff markdown file by basename across handoff roots."""
    if not agent or not filename or filename.startswith("kb_"):
        return None
    if not filename.endswith(".md"):
        return None
    for root in handoffs_roots():
        candidate = root / agent / filename
        if candidate.is_file():
            return candidate
    return None


def discover_handoff_dirs(agent: str) -> str:
    """Colon-separated scan dirs for build_handoff_db / handoff_rebuild."""
    dirs: list[str] = []
    seen: set[str] = set()
    for root in handoffs_roots():
        if root.is_dir():
            for sub in sorted(root.iterdir()):
                if sub.is_dir() and not sub.name.startswith("."):
                    path = str(sub.resolve())
                    if path not in seen:
                        dirs.append(path)
                        seen.add(path)
        agent_dir = root / agent
        if agent_dir.is_dir():
            path = str(agent_dir.resolve())
            if path not in seen:
                dirs.append(path)
                seen.add(path)
    if not dirs:
        dirs = [str(handoffs_root() / agent)]
    nest = willow_home() / "Nest" / agent
    if nest.is_dir():
        path = str(nest.resolve())
        if path not in seen:
            dirs.append(path)
    return ":".join(dirs)
