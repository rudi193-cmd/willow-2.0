"""core.boot_gate — shared boot-sentinel check used by both the PreToolUse
hook and agent_task_submit() (Kart), since PreToolUse never fires for
mcp__willow__* tool calls."""
from core.boot_gate import boot_done_path, is_booted


def test_boot_done_path_keyed_to_agent_name():
    assert boot_done_path("willow").name == "willow-boot-done-willow.flag"
    assert boot_done_path("hanuman").name == "willow-boot-done-hanuman.flag"


def test_is_booted_true_under_pytest(monkeypatch):
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_boot_gate.py::x")
    assert is_booted("nonexistent-agent-xyz") is True


def test_is_booted_false_without_sentinel(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    assert is_booted("nonexistent-agent-xyz") is False


def test_is_booted_true_with_sentinel(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    p = boot_done_path("fixture-agent-abc")
    p.write_text("booted")
    try:
        assert is_booted("fixture-agent-abc") is True
    finally:
        p.unlink(missing_ok=True)
