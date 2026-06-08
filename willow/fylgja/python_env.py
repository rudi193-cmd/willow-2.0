"""Shared Python interpreter resolution for Willow launchers and Kart."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from willow.fylgja.willow_home import willow_home


def _bin_dir(venv: Path) -> Path:
    return venv / ("Scripts" if os.name == "nt" else "bin")


def _python_name() -> str:
    return "python.exe" if os.name == "nt" else "python3"


def venv_candidates(root: Path | None = None) -> list[Path]:
    """Return Willow venv directories in canonical preference order."""
    candidates: list[Path] = []
    if root is not None:
        candidates.append(root / ".venv-dev")
    candidates.append(Path.home() / "github" / "willow-2.0" / ".venv-dev")
    if root is not None:
        try:
            candidates.append(willow_home(root) / "venv")
        except Exception:
            pass
    candidates.extend([
        Path.home() / "github" / ".willow" / "venv",
        Path.home() / ".willow" / "venv",
        Path.home() / ".willow-venv",
    ])

    out: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            key = str(candidate.expanduser().resolve())
        except OSError:
            key = str(candidate.expanduser())
        if key in seen:
            continue
        seen.add(key)
        out.append(candidate.expanduser())
    return out


def venv_bin_dirs(root: Path | None = None) -> list[Path]:
    """Return existing Willow venv bin dirs in preference order."""
    bins: list[Path] = []
    for venv in venv_candidates(root):
        bin_dir = _bin_dir(venv)
        if bin_dir.is_dir():
            bins.append(bin_dir)
    return bins


def willow_python(root: Path | None = None) -> str:
    """Resolve the Python executable Willow should use for this repo/root."""
    env_python = (os.environ.get("WILLOW_PYTHON") or "").strip()
    if env_python and Path(env_python).expanduser().is_file():
        return str(Path(env_python).expanduser())

    for bin_dir in venv_bin_dirs(root):
        py = bin_dir / _python_name()
        if py.is_file():
            return str(py)

    return sys.executable

