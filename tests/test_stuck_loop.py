"""Tests for willow/fylgja/stuck_loop.py — native cctime chain-detector reimplementation."""
import json

from willow.fylgja.stuck_loop import (
    ToolCall,
    detect_stuck_loops,
    detect_stuck_loops_in_jsonl,
    extract_tool_calls,
)


def _ts(seconds: int) -> str:
    return f"2026-07-05T00:00:{seconds:02d}.000Z"


def _assistant_msg(tool_id: str, tool_name: str, seconds: int) -> dict:
    return {
        "type": "assistant",
        "timestamp": _ts(seconds),
        "message": {"content": [{"type": "tool_use", "id": tool_id, "name": tool_name}]},
    }


def _result_msg(tool_id: str, seconds: int, *, is_error: bool) -> dict:
    return {
        "type": "user",
        "timestamp": _ts(seconds),
        "message": {
            "content": [{"type": "tool_result", "tool_use_id": tool_id, "is_error": is_error}]
        },
    }


def test_extract_tool_calls_pairs_use_and_result_in_order():
    messages = [
        _assistant_msg("t1", "Bash", 0),
        _result_msg("t1", 1, is_error=False),
        _assistant_msg("t2", "Read", 2),
        _result_msg("t2", 3, is_error=True),
    ]
    calls = extract_tool_calls(messages)
    assert [c.tool_name for c in calls] == ["Bash", "Read"]
    assert calls[0].is_error is False
    assert calls[1].is_error is True
    assert calls[1].start_ts < calls[1].end_ts


def test_extract_tool_calls_ignores_unmatched_tool_use():
    """A tool_use with no corresponding tool_result (e.g. transcript cut off
    mid-call) must not appear as a call — there's nothing to pair it with."""
    messages = [_assistant_msg("t1", "Bash", 0)]
    assert extract_tool_calls(messages) == []


def test_detect_stuck_loops_flags_chain_with_two_failures():
    calls = [
        ToolCall("Bash", 0, 1, is_error=True),
        ToolCall("Bash", 1, 2, is_error=True),
        ToolCall("Bash", 2, 3, is_error=False),  # chain resolves on 3rd attempt
    ]
    loops = detect_stuck_loops(calls)
    assert len(loops) == 1
    loop = loops[0]
    assert loop.tool_name == "Bash"
    assert loop.attempts == 3
    assert loop.failures == 2
    assert loop.resolved is True
    assert loop.duration_ms == 3


def test_detect_stuck_loops_ignores_single_failure():
    calls = [
        ToolCall("Bash", 0, 1, is_error=True),
        ToolCall("Read", 1, 2, is_error=False),  # different tool breaks the chain
    ]
    assert detect_stuck_loops(calls) == []


def test_detect_stuck_loops_unresolved_chain_still_flagged():
    """A chain that never recovers (every call errors, transcript just ends)
    is still a real stuck loop — resolved=False, not silently dropped."""
    calls = [
        ToolCall("Grep", 0, 1, is_error=True),
        ToolCall("Grep", 1, 2, is_error=True),
        ToolCall("Grep", 2, 3, is_error=True),
    ]
    loops = detect_stuck_loops(calls)
    assert len(loops) == 1
    assert loops[0].attempts == 3
    assert loops[0].failures == 3
    assert loops[0].resolved is False


def test_detect_stuck_loops_breaks_chain_on_tool_switch_even_mid_failure():
    """Switching tools ends the chain immediately, even if the prior call
    errored — matches analyzer.ts's same-tool-name requirement."""
    calls = [
        ToolCall("Bash", 0, 1, is_error=True),
        ToolCall("Edit", 1, 2, is_error=True),
        ToolCall("Bash", 2, 3, is_error=True),
    ]
    assert detect_stuck_loops(calls) == []


def test_detect_stuck_loops_multiple_independent_chains():
    calls = [
        ToolCall("Bash", 0, 1, is_error=True),
        ToolCall("Bash", 1, 2, is_error=True),
        ToolCall("Bash", 2, 3, is_error=False),
        ToolCall("Read", 3, 4, is_error=False),
        ToolCall("Grep", 4, 5, is_error=True),
        ToolCall("Grep", 5, 6, is_error=True),
        ToolCall("Grep", 6, 7, is_error=True),
    ]
    loops = detect_stuck_loops(calls)
    assert [(loop.tool_name, loop.failures) for loop in loops] == [("Bash", 2), ("Grep", 3)]


def test_detect_stuck_loops_in_jsonl_end_to_end(tmp_path):
    lines = [
        _assistant_msg("t1", "Bash", 0),
        _result_msg("t1", 1, is_error=True),
        _assistant_msg("t2", "Bash", 2),
        _result_msg("t2", 3, is_error=True),
        _assistant_msg("t3", "Bash", 4),
        _result_msg("t3", 5, is_error=False),
        "",  # blank line must be skipped
        "not json at all",  # malformed line must be skipped, not raise
    ]
    path = tmp_path / "session.jsonl"
    path.write_text(
        "\n".join(json.dumps(line) if isinstance(line, dict) else line for line in lines)
    )
    loops = detect_stuck_loops_in_jsonl(path)
    assert len(loops) == 1
    assert loops[0].tool_name == "Bash"
    assert loops[0].to_dict()["failures"] == 2
