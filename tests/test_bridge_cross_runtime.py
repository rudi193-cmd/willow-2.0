"""bridge_cross_runtime.py — auto-discover sessions + handoff-driven threads."""
from __future__ import annotations

import json
from pathlib import Path

import scripts.bridge_cross_runtime as bridge


def test_prune_resolved_threads_drops_shipped_markers():
    raw = [
        "**Close fork** `FORK-CE988743` (shipped #434)",
        "**cross-runtime.json** stale — refresh",
        "**willow_run triple output** — P2",
        "**Local git:** fix/identity-drift",
    ]
    kept = bridge.prune_resolved_threads(raw)
    assert len(kept) == 1
    assert "willow_run" in kept[0]


def test_build_bridge_uses_handoff_threads(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_HOME", str(tmp_path))
    monkeypatch.setenv("WILLOW_AGENT_NAME", "willow")
    import importlib

    importlib.reload(bridge)

    agent_dir = tmp_path / "handoffs" / "willow"
    agent_dir.mkdir(parents=True)
    handoff = agent_dir / "session_handoff-2026-06-17f_willow.md"
    handoff.write_text(
        """---
agent: willow
date: 2026-06-17
session: 2026-06-17f
format: v2
---

# HANDOFF

## Open Threads

- **willow_run triple output** — dedup
- **cross-runtime.json** stale

## 17 Questions

Q17: What is the next single bite? willow_run dedup
""",
        encoding="utf-8",
    )

    out = bridge.build_bridge(agent="willow", claude_id="", cursor_id="", prune=True)
    assert out["handoff_source"] == handoff.name
    assert len(out["open_threads"]) == 1
    assert "willow_run" in out["open_threads"][0]
    assert "dedup" in out["next_bite"].lower() or "willow_run" in out["next_bite"]


def test_latest_session_id_claude_picks_newest(tmp_path, monkeypatch):
    root = tmp_path / "claude"
    root.mkdir()
    old = root / "aaaa.jsonl"
    new = root / "bbbb.jsonl"
    old.write_text("{}", encoding="utf-8")
    new.write_text("{}", encoding="utf-8")
    import os
    import time

    os.utime(old, (1, 1))
    time.sleep(0.01)
    new.touch()
    monkeypatch.setattr(bridge, "CLAUDE_ROOT", root)
    assert bridge.latest_session_id("claude") == "bbbb"
