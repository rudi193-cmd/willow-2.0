"""Tests for willow/fylgja/hook_runner.py Cursor ↔ Claude payload mapping."""
from willow.fylgja.hook_runner import _cursor_to_claude


def test_cursor_subagent_start_maps_to_task():
    payload = {
        "hook_event_name": "subagentStart",
        "subagent_type": "generalPurpose",
        "task": "search for hooks",
        "parent_conversation_id": "conv-1",
    }
    out = _cursor_to_claude("willow.fylgja.events.pre_tool", payload)
    assert out["tool_name"] == "Task"
    assert out["tool_input"]["subagent_type"] == "generalPurpose"
    assert out["session_id"] == "conv-1"


def test_cursor_pretool_use_maps_shell_to_bash():
    payload = {
        "hook_event_name": "preToolUse",
        "tool_name": "Shell",
        "tool_input": {"command": "cd /tmp && git status"},
        "conversation_id": "conv-2",
    }
    out = _cursor_to_claude("willow.fylgja.events.pre_tool", payload)
    assert out["tool_name"] == "Bash"
    assert "git status" in out["tool_input"]["command"]


def test_cursor_pretool_use_maps_read():
    payload = {
        "hook_event_name": "preToolUse",
        "tool_name": "Read",
        "tool_input": {"path": "/tmp/foo.py"},
        "conversation_id": "conv-3",
    }
    out = _cursor_to_claude("willow.fylgja.events.pre_tool", payload)
    assert out["tool_name"] == "Read"
    assert out["tool_input"]["path"] == "/tmp/foo.py"
