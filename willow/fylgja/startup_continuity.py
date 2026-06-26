"""Boot/cold-recovery KB continuity — driver for startup_continuity.json."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "startup_continuity.json"


def config_path() -> Path:
    return _CONFIG_PATH


def load_config(path: Optional[Path] = None) -> dict[str, Any]:
    p = path or _CONFIG_PATH
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("startup_continuity.json must be a JSON object")
    return data


def iter_kb_searches(cfg: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
    """Normalize kb_searches[] with per-entry defaults from the config root."""
    data = cfg if cfg is not None else load_config()
    searches = data.get("kb_searches") or []
    default_continuity = bool(data.get("continuity", True))
    out: list[dict[str, Any]] = []
    for entry in searches:
        if not isinstance(entry, dict):
            continue
        query = (entry.get("query") or "").strip()
        if not query:
            continue
        merged = dict(entry)
        merged["query"] = query
        if "continuity" not in merged:
            merged["continuity"] = default_continuity
        out.append(merged)
    return out
