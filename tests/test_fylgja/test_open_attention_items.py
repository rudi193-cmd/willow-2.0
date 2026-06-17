"""session_start open gaps + flags merge."""
import os
from unittest.mock import patch

os.environ.setdefault("WILLOW_AGENT_NAME", "willow")

import willow.fylgja.events.session_start as ss


def test_open_attention_items_merges_gaps_and_flags():
    def fake_call(name, params, timeout=5):
        if name != "store_list":
            return []
        coll = params.get("collection", "")
        if coll == "willow/gaps":
            return [
                {"status": "open", "title": "Human gap A", "severity": 5},
                {"status": "closed", "title": "Closed gap"},
            ]
        if coll == "willow/flags":
            return [
                {
                    "flag_state": "open",
                    "title": "Repeated enforcement: 'Bash' blocked 50× fleet-wide",
                    "hit_count": 50,
                },
                {
                    "flag_state": "open",
                    "title": "Blessed path for Bash",
                    "hit_count": 20,
                },
                {"flag_state": "resolved", "title": "Old flag"},
            ]
        return []

    with patch.object(ss, "call", fake_call):
        count, titles = ss._open_attention_items("willow")

    assert count == 2
    assert titles[0] == "Repeated enforcement: 'Bash' blocked 50× fleet-wide"
    assert "Human gap A" in titles
    assert not any("Blessed path" in t for t in titles)


def test_open_attention_items_flags_only_when_gaps_empty():
    def fake_call(name, params, timeout=5):
        if name == "store_list" and params.get("collection") == "willow/flags":
            return [{"flag_state": "open", "title": "Only flag", "hit_count": 10}]
        return []

    with patch.object(ss, "call", fake_call):
        count, titles = ss._open_attention_items("willow")

    assert count == 1
    assert titles == ["Only flag"]
