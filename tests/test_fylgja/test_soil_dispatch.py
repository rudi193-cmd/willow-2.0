"""Direct soil_ dispatch in the hook MCP client + stack-snapshot failure surfacing.

Regression guard for the silent stack-snapshot freeze: soil_put took the
subprocess willow-mcp fallback (4 cold spawns under an 8s timeout) and its
return value was never checked, so a failed write left stack/current frozen
for days with no signal. These tests pin the two halves of the fix:
  1. soil_ calls dispatch directly to StorePort (no subprocess spawn).
  2. _write_stack_snapshot logs a hook error when the write does not land.
"""
import os
from unittest.mock import patch

os.environ.setdefault("WILLOW_AGENT_NAME", "hanuman")

import willow.fylgja._mcp as mcp
import willow.fylgja.events.stop as stop


class _FakeStore:
    def __init__(self):
        self.records: dict[tuple[str, str], dict] = {}

    def put(self, collection, record, record_id=None, deviation=0.0):
        rid = record_id or record.get("id") or "GEN1"
        self.records[(collection, rid)] = record
        return rid, "work_quiet", None

    def get(self, collection, record_id):
        return self.records.get((collection, record_id))


def test_soil_put_get_dispatch_direct_no_subprocess():
    fake = _FakeStore()

    def _boom(*a, **k):
        raise AssertionError("subprocess fallback must not run for soil_ calls")

    with patch.object(mcp, "_get_store", lambda: fake):
        with patch.object(mcp, "_subprocess_call", _boom):
            put = mcp.call("soil_put", {
                "app_id": "hanuman",
                "collection": "hanuman/stack",
                "record_id": "current",
                "record": {"id": "current", "written_at": "now"},
            })
            assert put["id"] == "current"
            assert put["action"] == "work_quiet"

            got = mcp.call("soil_get", {
                "app_id": "hanuman",
                "collection": "hanuman/stack",
                "record_id": "current",
            })
            assert got["written_at"] == "now"


def test_soil_get_missing_returns_not_found():
    fake = _FakeStore()
    with patch.object(mcp, "_get_store", lambda: fake):
        got = mcp.call("soil_get", {
            "app_id": "hanuman",
            "collection": "hanuman/stack",
            "record_id": "nope",
        })
        assert got == {"error": "not_found"}


def test_stack_snapshot_logs_error_when_write_fails():
    logged: list[tuple[str, dict]] = []

    def fake_call(name, params, timeout=8):
        if name == "agent_task_list":
            return {"pending": [], "count": 0}
        if name == "handoff_latest":
            return {"filename": "h.md", "open_threads": []}
        if name == "ledger_read":
            return {"entries": [{"content": {"open_decisions": []}}]}
        if name == "soil_put":
            return {"error": "timeout_on_init", "tool": "soil_put"}
        return {}

    with patch.object(stop, "call", fake_call):
        with patch.object(stop, "_log_hook_error",
                          lambda where, detail: logged.append((where, detail))):
            stop._write_stack_snapshot("sess-1")

    assert len(logged) == 1
    assert logged[0][0] == "stack_snapshot"
    assert "timeout_on_init" in repr(logged[0][1])


def test_stack_snapshot_silent_on_success():
    logged: list = []

    def fake_call(name, params, timeout=8):
        if name == "agent_task_list":
            return {"pending": [], "count": 0}
        if name == "handoff_latest":
            return {"filename": "h.md", "open_threads": []}
        if name == "ledger_read":
            return {"entries": [{"content": {"open_decisions": []}}]}
        if name == "soil_put":
            return {"id": "current", "action": "work_quiet"}
        return {}

    with patch.object(stop, "call", fake_call):
        with patch.object(stop, "_log_hook_error",
                          lambda where, detail: logged.append((where, detail))):
            stop._write_stack_snapshot("sess-2")

    assert logged == []
