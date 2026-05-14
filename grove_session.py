"""
grove_session.py — Grove session state persistence.
b17: GSESS1  ΔΣ=42

Writes hard_close=True on start, False on clean exit.
Resume prompt fires if hard_close=True at next boot.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SESSION_FILE = Path.home() / ".willow" / "grove_session.json"

_DEFAULTS: dict[str, Any] = {
    "hard_close":    True,
    "last_pane":     "home",
    "last_channel":  None,
    "last_scroll":   0,
    "closed_at":     None,
}


def _read() -> dict:
    try:
        return json.loads(_SESSION_FILE.read_text())
    except Exception:
        return dict(_DEFAULTS)


def _write(data: dict) -> None:
    _SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SESSION_FILE.write_text(json.dumps(data, indent=2, default=str))


def mark_open() -> dict:
    """Call at app start. Marks session as potentially hard-closed. Returns prior state."""
    prior = _read()
    current = dict(_DEFAULTS)
    current["hard_close"] = True
    _write(current)
    return prior


def mark_closed() -> None:
    """Call on clean exit. Clears hard_close flag."""
    data = _read()
    data["hard_close"] = False
    data["closed_at"]  = datetime.now(timezone.utc).isoformat()
    _write(data)


def save_state(pane: str, channel: str | None = None, scroll: int = 0) -> None:
    """Persist current navigation state."""
    data = _read()
    data["last_pane"]    = pane
    data["last_channel"] = channel
    data["last_scroll"]  = scroll
    _write(data)


def was_hard_closed(prior: dict) -> bool:
    return bool(prior.get("hard_close", False))
