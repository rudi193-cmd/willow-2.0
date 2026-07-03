"""session_stop crash-skeleton handoff helpers (handoff_v3)."""
from __future__ import annotations

from willow.fylgja.handoff_v3 import (
    claims_from_stack,
    extract_machine_block,
    should_write_stop_hook_handoff,
    skeleton_from_stack,
    write_stop_hook_skeleton_handoff,
    write_session_handoff_v3,
)


def test_should_skip_when_model_handoff_exists_for_session(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_HOME", str(tmp_path))
    monkeypatch.setattr(
        "willow.fylgja.handoff_write.willow_home", lambda: tmp_path, raising=True
    )
    write_session_handoff_v3(
        "willow",
        summary="model handoff",
        claims=[],
        next_bite={"id": "next-bite", "text": "done", "kind": "prose", "opened": "2026-07-03"},
        project="willow-2.0",
        session_id="sess-abc",
        skeleton={},
        written_by="model_tool_call",
    )
    assert should_write_stop_hook_handoff("willow", "sess-abc") is False


def test_writes_stop_hook_skeleton(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_HOME", str(tmp_path))
    monkeypatch.setattr(
        "willow.fylgja.handoff_write.willow_home", lambda: tmp_path, raising=True
    )
    stack = {
        "open_flags": [{"title": "fix kart", "fix_path": "run kart_task_run"}],
        "open_tasks": [{"id": "T1", "task": "pytest tests/", "status": "pending"}],
    }
    path = write_stop_hook_skeleton_handoff(
        "willow",
        stack,
        session_id="sess-stop-1",
        project="willow-2.0",
        runtime="cursor",
        repo_root=tmp_path,
    )
    assert path is not None
    block = extract_machine_block(path.read_text(encoding="utf-8"))
    assert block is not None
    assert block["written_by"] == "stop_hook"
    assert block["session_id"] == "sess-stop-1"
    assert block["skeleton"].get("kart_tasks")
    assert block["claims"]
    assert block["next_bite"]["text"] == "pytest tests/"


def test_skeleton_from_stack_merges_tasks():
    sk = skeleton_from_stack(
        {"open_tasks": [{"id": "A", "status": "running", "task": "work"}]},
        repo_root="/tmp",
    )
    assert sk["kart_tasks"][0]["id"] == "A"


def test_claims_from_stack_limits():
    stack = {
        "open_flags": [{"title": f"f{i}"} for i in range(5)],
        "open_tasks": [{"task": f"t{i}", "status": "pending"} for i in range(5)],
    }
    assert len(claims_from_stack(stack)) == 8
