"""PR 2: stack snapshot SOIL round-trip (session_start ↔ stop)."""
import os
from unittest.mock import patch

os.environ.setdefault("WILLOW_AGENT_NAME", "hanuman")

import willow.fylgja.events._stack_snapshot as stack
import willow.fylgja.events.session_start as ss


def test_parse_agent_task_list_pending_shape():
    result = stack.parse_agent_task_list({
        "pending": [{"id": "AB12", "task": "echo hi", "status": "pending"}],
        "count": 1,
    })
    assert len(result) == 1
    assert result[0]["id"] == "AB12"
    assert result[0]["title"] == "echo hi"


def test_normalize_stack_record_not_found():
    assert stack.normalize_stack_record({"error": "not_found"}) == {}


def test_silent_startup_soil_get_uses_record_id():
    calls: list[tuple[str, dict]] = []

    def fake_call(name, params, timeout=5):
        calls.append((name, params))
        if name == "handoff_latest":
            return {}
        if name == "fleet_status":
            return {"postgres": {"knowledge": 1}}
        if name == "store_search":
            return []
        if name == "store_list":
            return []
        if name == "soil_get":
            return {"id": "current", "open_tasks": [], "written_at": "2026-06-05"}
        return {}

    with patch.object(ss, "call", fake_call):
        with patch.object(ss, "AGENT", "hanuman"):
            result = ss._run_silent_startup()

    soil = [p for n, p in calls if n == "soil_get"]
    assert len(soil) == 1
    assert soil[0]["record_id"] == "current"
    assert "key" not in soil[0]
    assert result["stack_snapshot"].get("id") == "current"


def test_silent_startup_stack_missing_when_traces_exist():
    def fake_call(name, params, timeout=5):
        if name == "handoff_latest":
            return {}
        if name == "fleet_status":
            return {"postgres": {"knowledge": 1}}
        if name == "store_search":
            return [{"summary": "did work"}]
        if name == "store_list":
            return []
        if name == "soil_get":
            return {"error": "not_found"}
        return {}

    with patch.object(ss, "call", fake_call):
        with patch.object(ss, "AGENT", "hanuman"):
            result = ss._run_silent_startup()

    steps = [e.get("step") for e in result["mcp_errors"]]
    assert "stack_missing" in steps
