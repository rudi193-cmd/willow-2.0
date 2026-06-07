"""Resolve canonical handoff directories and SQLite index paths."""
from __future__ import annotations

from pathlib import Path

from willow.fylgja.willow_home import fleet_home as willow_home


def handoffs_root() -> Path:
    """Directory containing per-agent handoff folders."""
    return willow_home() / "handoffs"


def handoff_db_path(agent: str) -> Path:
    return handoffs_root() / agent / "handoffs.db"


def discover_handoff_dirs(agent: str) -> str:
    """Colon-separated scan dirs for build_handoff_db / handoff_rebuild."""
    root = handoffs_root()
    dirs: list[str] = []
    if root.is_dir():
        dirs = [
            str(sub)
            for sub in sorted(root.iterdir())
            if sub.is_dir() and not sub.name.startswith(".")
        ]
    if not dirs:
        dirs = [str(root / agent)]
    nest = willow_home() / "Nest" / agent
    if nest.is_dir() and str(nest) not in dirs:
        dirs.append(str(nest))
    return ":".join(dirs)
