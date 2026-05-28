"""Willow release version — read from repo VERSION, pin to WILLOW_HOME/version.

b17: VER20 · ΔΣ=42
"""
from __future__ import annotations

import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_VERSION_FILE = _REPO_ROOT / "VERSION"


def get_version() -> str:
    if _VERSION_FILE.is_file():
        return _VERSION_FILE.read_text().strip()
    return "2.0.0"


VERSION = get_version()


def installed_version_path() -> Path:
    """Resolved at call time so tests can monkeypatch Path.home() / WILLOW_HOME."""
    home = Path(os.environ.get("WILLOW_HOME", Path.home() / "github" / ".willow"))
    return home / "version"


def sync_installed_version() -> str:
    """Write repo VERSION to WILLOW_HOME/version when it differs."""
    v = get_version()
    path = installed_version_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    current = path.read_text().strip() if path.is_file() else ""
    if current != v:
        path.write_text(v + "\n")
    return v
