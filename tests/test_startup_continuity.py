"""Tests for startup_continuity.json batch driver."""
from __future__ import annotations

import json
from pathlib import Path

from willow.fylgja.startup_continuity import iter_kb_searches, load_config


def test_load_config_has_continuity_default():
    cfg = load_config()
    assert cfg.get("continuity") is True
    assert isinstance(cfg.get("kb_searches"), list)
    assert len(cfg["kb_searches"]) >= 5


def test_iter_kb_searches_applies_continuity_default(tmp_path: Path):
    cfg = {
        "continuity": True,
        "kb_searches": [
            {"query": "alpha", "limit": 3},
            {"query": "beta", "continuity": False},
            {"query": ""},
        ],
    }
    path = tmp_path / "startup_continuity.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    rows = iter_kb_searches(load_config(path))
    assert len(rows) == 2
    assert rows[0]["continuity"] is True
    assert rows[1]["continuity"] is False
