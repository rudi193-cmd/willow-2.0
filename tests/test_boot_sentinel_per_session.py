"""Per-session boot sentinel — cross-window collision regression.

2026-07-04: the boot sentinel was keyed by agent name only, and every
parallel window runs as the same fleet identity. Any new window's
SessionStart unlinked the shared flag, so a running session's sentinel
"vanished mid-session". The sentinel is now keyed per (agent, session);
these tests pin the naming contract, the gate behavior, and the actual
clearing side effects — not just shapes.
"""
import json
from pathlib import Path

import pytest

from core.boot_gate import boot_done_path, is_booted
from willow.fylgja.events import pre_tool as _pt
from willow.fylgja.events import prompt_submit as _ps
from willow.fylgja.events import session_start as _ss


def test_boot_done_path_session_scoped():
    p = boot_done_path("willow", "sess-1234abcd")
    assert p.name == "willow-boot-done-willow-sess-1234abcd.flag"
    # no session id -> legacy shared path, unchanged
    assert boot_done_path("willow").name == "willow-boot-done-willow.flag"


def test_boot_done_path_sanitizes_session_id():
    p = boot_done_path("willow", "../../etc/passwd")
    assert "/" not in p.name.replace("willow-boot-done-", "")
    assert p.parent == Path("/tmp")


def test_hook_helpers_match_boot_gate_naming():
    # The hooks inline the path logic (they must not crash on import
    # failures); this pins them to core.boot_gate so they can't drift.
    for mod in (_pt, _ps, _ss):
        got = mod._boot_done("sess-77")
        want = boot_done_path(mod.AGENT, "sess-77")
        assert got == want, f"{mod.__name__} sentinel path drifted from boot_gate"
        # empty session id falls back to the module's legacy constant
        assert mod._boot_done("") == mod.BOOT_DONE


def test_is_booted_per_session(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    agent = "fixture-agent-persess"
    flag = boot_done_path(agent, "sess-a")
    flag.write_text("booted")
    try:
        assert is_booted(agent, "sess-a") is True
        assert is_booted(agent, "sess-b") is False
        # no session id (MCP server lane): any live session flag counts
        assert is_booted(agent) is True
    finally:
        flag.unlink(missing_ok=True)
    assert is_booted(agent) is False


def test_check_boot_gate_session_scoped(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    legacy = tmp_path / "willow-boot-done-willow.flag"
    monkeypatch.setattr(_pt, "BOOT_DONE", legacy)

    sid = "gate-sess-1"
    flag = _pt._boot_done(sid)
    flag.unlink(missing_ok=True)
    try:
        reason = _pt.check_boot_gate("Bash", {"command": "echo hi"}, sid)
        assert reason is not None
        # the gate must tell the agent the exact session-scoped path
        assert str(flag) in reason
        # writing that exact path is exempt from the gate
        assert _pt.check_boot_gate("Write", {"file_path": str(flag)}, sid) is None
        flag.write_text("booted")
        assert _pt.check_boot_gate("Bash", {"command": "echo hi"}, sid) is None
    finally:
        flag.unlink(missing_ok=True)


def test_fresh_session_does_not_clobber_other_sessions(tmp_path, monkeypatch):
    """THE collision: window B's fresh SessionStart must not clear window A."""
    monkeypatch.setattr(_ss, "BOOT_DONE", tmp_path / "legacy.flag")
    flag_a = _ss._boot_done("window-a-sess")
    flag_b = _ss._boot_done("window-b-sess")
    flag_a.write_text("booted")
    flag_b.write_text("booted")
    (tmp_path / "legacy.flag").write_text("booted")
    try:
        _ss._clear_boot_sentinels("window-b-sess")
        assert flag_a.exists(), "fresh session B cleared session A's sentinel"
        assert not flag_b.exists(), "fresh session must clear its own sentinel"
        assert not (tmp_path / "legacy.flag").exists(), "legacy shared flag should clear"
    finally:
        flag_a.unlink(missing_ok=True)
        flag_b.unlink(missing_ok=True)


def test_clear_prunes_only_stale_flags(tmp_path, monkeypatch):
    import os
    import time

    monkeypatch.setattr(_ss, "BOOT_DONE", tmp_path / "legacy.flag")
    stale = _ss._boot_done("stale-old-sess")
    fresh = _ss._boot_done("fresh-live-sess")
    stale.write_text("booted")
    fresh.write_text("booted")
    old = time.time() - 72 * 3600
    os.utime(stale, (old, old))
    try:
        _ss._clear_boot_sentinels("some-new-sess")
        assert not stale.exists(), "72h-old flag should be pruned"
        assert fresh.exists(), "live flag must survive another session's boot"
    finally:
        stale.unlink(missing_ok=True)
        fresh.unlink(missing_ok=True)


def test_boot_guard_message_names_session_flag(capsys, monkeypatch):
    monkeypatch.setattr(_ps, "is_first_turn", lambda: True)
    sid = "guard-sess-9"
    flag = _ps._boot_done(sid)
    flag.unlink(missing_ok=True)
    _ps._boot_guard(sid)
    out = capsys.readouterr().out
    assert str(flag) in out


def test_pre_tool_main_gate_uses_payload_session_id(monkeypatch, capsys):
    """End-to-end through main(): the block reason carries the session path."""
    import io
    import sys

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    sid = "main-sess-42"
    flag = _pt._boot_done(sid)
    flag.unlink(missing_ok=True)
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": "echo hi"},
        "session_id": sid,
    })
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    with pytest.raises(SystemExit):
        _pt.main()
    out = capsys.readouterr().out
    data = json.loads(out.strip().splitlines()[0])
    assert data["decision"] == "block"
    assert str(flag) in data["reason"]
