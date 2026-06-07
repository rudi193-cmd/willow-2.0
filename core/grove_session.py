"""
grove_session.py — Grove session state persistence.
b17: GSESS1  ΔΣ=42

Writes hard_close=True on start, False on clean exit.
Resume prompt fires if hard_close=True at next boot.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from willow.fylgja.willow_home import willow_home

_SESSION_FILE = willow_home() / "grove_session.json"

_DEFAULTS: dict[str, Any] = {
    "hard_close":    True,
    "last_pane":     "home",
    "last_channel":  None,
    "last_scroll":   0,
    "closed_at":     None,
}

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _soil():
    from core import soil as _soil_mod
    return _soil_mod


def _read() -> dict:
    try:
        record = _soil().get("system/grove_session", "main")
        if record:
            return {**_DEFAULTS, **{k: v for k, v in record.items() if not k.startswith("_")}}
    except Exception:
        pass
    # Flat file fallback (seeds SOIL on next write)
    try:
        return json.loads(_SESSION_FILE.read_text())
    except Exception:
        return dict(_DEFAULTS)


def _write(data: dict) -> None:
    try:
        _soil().put("system/grove_session", "main", data)
    except Exception:
        # Flat file fallback if SOIL unavailable (e.g. DB down at boot)
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
