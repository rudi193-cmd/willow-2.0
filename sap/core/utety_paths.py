"""
UTETY path resolution — find safe-app-store/apps/utety-chat from Willow.

ProfessorClient and utety_http previously defaulted to ~/safe-app-utety-chat
(sibling of willow-2.0), which often does not exist. Code lives in the monorepo
at ~/safe-app-store/apps/utety-chat or WILLOW_UTETY_ROOT.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Optional


def _is_utety_root(path: Path) -> bool:
    if not path.is_dir():
        return False
    return (path / "persona_compiler.py").is_file() or (path / "personas.py").is_file()


def _repo_root() -> Optional[Path]:
    here = Path(__file__).resolve()
    for candidate in (here.parent.parent.parent, *here.parents):
        if (candidate / "willow" / "fylgja" / "project_env.py").is_file():
            return candidate
    return None


def _candidate_roots(extra: Optional[Path] = None) -> Iterable[Path]:
    repo = extra or _repo_root()
    home = Path.home()

    env_root = os.environ.get("WILLOW_UTETY_ROOT", "").strip()
    if env_root:
        yield Path(env_root)

    if repo is not None:
        yield home / "safe-app-store" / "apps" / "utety-chat"
        yield repo.parent / "safe-app-store" / "apps" / "utety-chat"
        yield repo.parent / "safe-app-utety-chat"

    dev_root = os.environ.get("WILLOW_DEV_SAFE_ROOT", "").strip()
    if dev_root:
        yield Path(dev_root) / "safe-app-utety-chat"
        yield Path(dev_root) / "utety-chat"

    yield home / "safe-app-store" / "apps" / "utety-chat"
    yield home / "safe-app-utety-chat"


def resolve_utety_chat_root(start: Optional[Path] = None) -> Optional[Path]:
    """Return the first valid UTETY chat app root, or None."""
    seen: set[str] = set()
    for raw in _candidate_roots(start):
        try:
            path = raw.resolve()
        except OSError:
            continue
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        if _is_utety_root(path):
            return path
    return None


def ensure_utety_env(repo: Optional[Path] = None) -> Optional[Path]:
    """
    Set WILLOW_UTETY_ROOT and WILLOW_SAFE_ROOT when missing.
    Returns resolved UTETY root (may still be None if app not installed).
    """
    repo = repo or _repo_root()

    if not os.environ.get("WILLOW_SAFE_ROOT", "").strip():
        default_safe = Path.home() / "SAFE" / "Applications"
        if default_safe.is_dir():
            os.environ["WILLOW_SAFE_ROOT"] = str(default_safe)

    root = resolve_utety_chat_root(repo)
    if root is not None:
        os.environ["WILLOW_UTETY_ROOT"] = str(root)
    return root
