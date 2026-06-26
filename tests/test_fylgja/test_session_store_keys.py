"""PR 3: session composite store id alignment."""
import os
from unittest.mock import patch

os.environ.setdefault("WILLOW_AGENT_NAME", "hanuman")

from willow.fylgja.events._session_store import (
    session_composite_lookup_ids,
    session_composite_record_id,
)
import willow.fylgja.events.session_start as ss


def test_session_composite_record_id():
    assert session_composite_record_id("abcdef1234567890") == "session-abcdef12"
    assert session_composite_record_id("") == "session-unknown"


def test_lookup_ids_primary_before_legacy():
    ids = session_composite_lookup_ids("abcdef1234567890")
    assert ids[0] == "session-abcdef12"
    assert len(ids) >= 2


def test_silent_startup_reads_session_id_key():
    calls: list[tuple[str, dict]] = []

    def fake_call(name, params, timeout=5):
        calls.append((name, params))
        if name == "store_get" and params.get("id") == "session-abcdef12":
            return {"next_bite": "finish PR 3", "type": "session"}
        if name == "handoff_latest":
            return {}
        if name == "fleet_status":
            return {"postgres": {"knowledge": 1}}
        if name in ("store_search", "store_list"):
            return []
        if name == "soil_get":
            return {"error": "not_found"}
        return {}

    # _run_silent_startup calls ensure_fresh_bridge (not read_bridge directly).
    # Without mocking it, CI runs build_bridge() and leaks a real next_bite.
    with patch("willow.fylgja.cross_runtime.ensure_fresh_bridge", return_value={}):
        with patch.object(ss, "call", fake_call):
            with patch.object(ss, "AGENT", "hanuman"):
                result = ss._run_silent_startup("abcdef1234567890")

    get_ids = [p["id"] for n, p in calls if n == "store_get"]
    assert get_ids[0] == "session-abcdef12"
    assert result["next_bite"] == "finish PR 3"
