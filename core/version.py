"""Willow release version — read from repo VERSION, pin to ~/.willow/version.

b17: VER20 · ΔΣ=42
"""
from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_VERSION_FILE = _REPO_ROOT / "VERSION"
_INSTALLED = Path.home() / ".willow" / "version"


def get_version() -> str:
    if _VERSION_FILE.is_file():
        return _VERSION_FILE.read_text().strip()
    return "2.0.0"


VERSION = get_version()


def sync_installed_version() -> str:
    """Write repo VERSION to ~/.willow/version when it differs."""
    v = get_version()
    _INSTALLED.parent.mkdir(parents=True, exist_ok=True)
    current = _INSTALLED.read_text().strip() if _INSTALLED.is_file() else ""
    if current != v:
        _INSTALLED.write_text(v + "\n")
    return v
