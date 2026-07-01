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
    assert out["tool_input"]["file_path"] == "/tmp/foo.py"


def test_cursor_pretool_use_write_maps_path_to_file_path():
    """Boot gate and tamper guard key on file_path; Cursor sends path."""
    payload = {
        "hook_event_name": "preToolUse",
        "tool_name": "Write",
        "tool_input": {"path": "/tmp/willow-boot-done-willow.flag", "content": "booted"},
        "conversation_id": "conv-4",
    }
    out = _cursor_to_claude("willow.fylgja.events.pre_tool", payload)
    assert out["tool_name"] == "Write"
    assert out["tool_input"]["file_path"] == "/tmp/willow-boot-done-willow.flag"
    assert out["tool_input"]["content"] == "booted"


def test_cursor_pretool_use_strreplace_maps_to_edit():
    payload = {
        "hook_event_name": "preToolUse",
        "tool_name": "StrReplace",
        "tool_input": {"path": "/tmp/foo.py"},
        "conversation_id": "conv-5",
    }
    out = _cursor_to_claude("willow.fylgja.events.pre_tool", payload)
    assert out["tool_name"] == "Edit"
    assert out["tool_input"]["file_path"] == "/tmp/foo.py"


def test_cursor_pretool_use_explicit_file_path_wins():
    payload = {
        "hook_event_name": "preToolUse",
        "tool_name": "Read",
        "tool_input": {"file_path": "/tmp/a.py", "path": "/tmp/b.py"},
        "conversation_id": "conv-6",
    }
    out = _cursor_to_claude("willow.fylgja.events.pre_tool", payload)
    assert out["tool_input"]["file_path"] == "/tmp/a.py"
