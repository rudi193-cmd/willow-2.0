import json
from io import StringIO
from unittest.mock import patch
import pytest


def _run(stdin_data: dict) -> str:
    import willow.fylgja.events.post_tool as m
    inp = StringIO(json.dumps(stdin_data))
    out = StringIO()
    with patch("sys.stdin", inp), patch("sys.stdout", out):
        try:
            m.main()
        except SystemExit:
            pass
    return out.getvalue()


def test_toolsearch_emits_directive():
    out = _run({"tool_name": "ToolSearch", "tool_input": {}})
    assert "TOOL-SEARCH-COMPLETE" in out
    assert "Schema loaded" in out


def test_other_tool_emits_nothing():
    out = _run({"tool_name": "Read", "tool_input": {}})
    assert out.strip() == ""


def test_edit_tool_writes_trace(tmp_path):
    """Significant tool should call store_put with a trace atom."""
    calls = []
    rate_file = tmp_path / "rate.json"
    def fake_call(tool, args, timeout=5):
        calls.append((tool, args))
        return {"id": "turn-abc12345-1234567890"}
    with patch("willow.fylgja.events.post_tool.call", fake_call), \
         patch("willow.fylgja.events.post_tool._RATE_FILE", rate_file):
        _run({"tool_name": "Edit", "tool_input": {"file_path": "/foo/bar.py"}})
    assert len(calls) == 1
    tool_name, args = calls[0]
    assert tool_name == "store_put"
    record = args["record"]
    assert record["type"] == "trace"
    assert record["tool"] == "Edit"
    assert "/foo/bar.py" in record["target"]


def test_read_tool_writes_no_trace():
    """Read-only tools must not write trace atoms."""
    calls = []
    def fake_call(tool, args, timeout=5):
        calls.append((tool, args))
        return {}
    with patch("willow.fylgja.events.post_tool.call", fake_call):
        _run({"tool_name": "Read", "tool_input": {"file_path": "/foo/bar.py"}})
    store_calls = [c for c in calls if c[0] == "store_put"]
    assert store_calls == []


def test_rate_limit_suppresses_duplicate_within_60s(tmp_path):
    """Same tool+target within 60s should only write one trace."""
    calls = []
    def fake_call(tool, args, timeout=5):
        calls.append((tool, args))
        return {}
    rate_file = tmp_path / "rate.json"
    with patch("willow.fylgja.events.post_tool.call", fake_call), \
         patch("willow.fylgja.events.post_tool._RATE_FILE", rate_file):
        _run({"tool_name": "Edit", "tool_input": {"file_path": "/foo/bar.py"}})
        _run({"tool_name": "Edit", "tool_input": {"file_path": "/foo/bar.py"}})
    store_calls = [c for c in calls if c[0] == "store_put"]
    assert len(store_calls) == 1


def test_store_put_failure_does_not_crash(tmp_path):
    """Trace writer must never crash the hook."""
    rate_file = tmp_path / "rate.json"
    def fake_call(tool, args, timeout=5):
        raise RuntimeError("MCP unavailable")
    with patch("willow.fylgja.events.post_tool.call", fake_call), \
         patch("willow.fylgja.events.post_tool._RATE_FILE", rate_file):
        try:
            _run({"tool_name": "Edit", "tool_input": {"file_path": "/foo/bar.py"}})
        except Exception as exc:
            pytest.fail(f"Hook raised an exception: {exc}")


def test_task_update_writes_active_build_file(tmp_path, monkeypatch):
    import willow.fylgja.events.post_tool as m
    ledger = tmp_path / "ledger.json"
    active = tmp_path / "active-build.json"
    monkeypatch.setattr(m, "_TASK_LEDGER_FILE", ledger)
    monkeypatch.setattr(m, "_ACTIVE_BUILD_FILE", active)
    _run({
        "tool_name": "TaskUpdate",
        "tool_input": {
            "taskId": "t1",
            "status": "in_progress",
            "activeForm": "fix hook enforcement",
        },
    })
    assert active.is_file()
    data = json.loads(active.read_text())
    assert data["label"] == "fix hook enforcement"
    _run({
        "tool_name": "TaskUpdate",
        "tool_input": {"taskId": "t1", "status": "completed"},
    })
    assert not active.exists()


def test_agent_task_submit_records_kart_pending(tmp_path, monkeypatch):
    import willow.fylgja.events.post_tool as m
    pending = tmp_path / "kart-pending.json"
    monkeypatch.setattr(m, "_kart_pending_path", lambda sid: pending)
    _run({
        "tool_name": "mcp__willow__agent_task_submit",
        "tool_input": {"task": "pytest tests/ -q"},
        "tool_response": {"task_id": "KART1"},
        "session_id": "sess-abc",
    })
    assert pending.is_file()
    data = json.loads(pending.read_text())
    assert data["command"] == "pytest tests/ -q"
    assert data["task_id"] == "KART1"
