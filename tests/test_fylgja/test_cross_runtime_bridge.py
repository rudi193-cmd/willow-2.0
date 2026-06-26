"""cross_runtime bridge freshness — stale bridge must not override newer handoff."""
from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("WILLOW_AGENT_NAME", "willow")

from willow.fylgja import cross_runtime as cr
import willow.fylgja.events.session_start as ss


def test_bridge_covers_handoff_newer_live_handoff():
    bridge = {"handoff_source": "session_handoff-2026-06-17k_willow.md"}
    assert not cr.bridge_covers_handoff(
        bridge,
        "session_handoff-2026-06-26d_willow.md",
        "2026-06-26",
    )


def test_bridge_covers_handoff_same_or_newer():
    bridge = {"handoff_source": "session_handoff-2026-06-26d_willow.md"}
    assert cr.bridge_covers_handoff(
        bridge,
        "session_handoff-2026-06-26c_willow.md",
        "2026-06-26",
    )


def test_silent_startup_keeps_handoff_next_bite_when_bridge_stale():
    stale_bridge = {
        "handoff_source": "session_handoff-2026-06-17k_willow.md",
        "open_threads": ["**stale** thread"],
        "next_bite": "stale carried bite",
    }
    live_bite = "Sean writes PERSONAL PARAGRAPH openings"

    def fake_call(name, params, timeout=5):
        if name == "handoff_latest":
            return {
                "filename": "session_handoff-2026-06-26d_willow.md",
                "date": "2026-06-26",
                "summary": "whitepaper session",
                "open_threads": ["**fresh** thread"],
                "next_bite": live_bite,
            }
        if name == "fleet_status":
            return {"postgres": {"knowledge": 1}}
        if name in ("store_search", "store_list"):
            return []
        if name == "soil_get":
            return {"error": "not_found"}
        return {}

    with patch("willow.fylgja.cross_runtime.ensure_fresh_bridge", return_value=stale_bridge):
        with patch.object(ss, "call", fake_call):
            with patch.object(ss, "AGENT", "willow"):
                result = ss._run_silent_startup("abcdef1234567890")

    assert result["next_bite"] == live_bite
    assert result["handoff_threads"] == ["**fresh** thread"]
    assert any(e.get("step") == "cross_runtime" for e in result["mcp_errors"])


def test_silent_startup_applies_fresh_bridge():
    fresh_bridge = {
        "handoff_source": "session_handoff-2026-06-26d_willow.md",
        "open_threads": ["**bridge** thread"],
        "next_bite": "bridge bite from rebuild",
    }

    def fake_call(name, params, timeout=5):
        if name == "handoff_latest":
            return {
                "filename": "session_handoff-2026-06-26d_willow.md",
                "date": "2026-06-26",
                "summary": "whitepaper session",
                "open_threads": ["**handoff** thread"],
                "next_bite": "handoff bite",
            }
        if name == "fleet_status":
            return {"postgres": {"knowledge": 1}}
        if name in ("store_search", "store_list"):
            return []
        if name == "soil_get":
            return {"error": "not_found"}
        return {}

    with patch("willow.fylgja.cross_runtime.ensure_fresh_bridge", return_value=fresh_bridge):
        with patch.object(ss, "call", fake_call):
            with patch.object(ss, "AGENT", "willow"):
                result = ss._run_silent_startup("abcdef1234567890")

    assert result["next_bite"] == "bridge bite from rebuild"
    assert result["handoff_threads"] == ["**bridge** thread"]
