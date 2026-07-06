import json
import time
from unittest.mock import patch
from willow.fylgja.events.pre_tool import (
    check_bash_block,
    check_agent_block,
    check_hook_tamper_guard,
    check_kb_first,
    check_channel_enforce,
    check_native_web_block,
)


def test_blocks_psql():
    result = check_bash_block("psql -U willow willow_20")
    assert result is not None
    decision, reason = result
    assert decision == "block"
    assert "MCP" in reason


def test_blocks_cat():
    result = check_bash_block("cat /home/sean/somefile.py")
    assert result is not None
    decision, reason = result
    assert decision == "block"
    assert "Read" in reason


def test_blocks_ls():
    result = check_bash_block("ls /home/sean/")
    assert result is not None
    decision, reason = result
    assert decision in ("block", "warn")
    assert "MCP" in reason or "kart" in reason.lower()


def test_blocks_git():
    # git via agent Bash has no creds and is the canonical Kart use case — block
    # on first attempt so the agent routes to Kart immediately (worktree cleanup
    # is exempted earlier in check_bash_block; see test_allows_worktree_cleanup_git).
    result = check_bash_block("git log --oneline -10")
    assert result is not None
    decision, reason = result
    assert decision == "block"
    assert "agent_task_submit" in reason or "kart" in reason.lower()


def test_blocks_gh():
    result = check_bash_block("gh pr list --limit 5")
    assert result is not None
    decision, reason = result
    assert decision == "block"
    assert "allow_net" in reason.lower()


def test_allows_worktree_cleanup_git():
    """S18: host-side worktree husk removal stays unguarded."""
    assert check_bash_block("git -C ~/github/willow-2.0 worktree prune") is None


def test_allows_pytest():
    reason = check_bash_block("python3 -m pytest tests/ -v")
    assert reason is None


def test_warns_bash_script():
    result = check_bash_block("bash scripts/store_import_guard.sh")
    assert result is not None
    decision, reason = result
    assert decision == "warn"
    assert "Kart" in reason or "kart" in reason.lower()


def test_warns_bash_script_with_path():
    result = check_bash_block("bash /tmp/my_job.sh")
    assert result is not None
    decision, _ = result
    assert decision == "warn"


def test_blocks_pythonpath_bypass():
    result = check_bash_block('PYTHONPATH=/home/sean/willow-2.0 python3 -c "from core.pg_bridge import try_connect"')
    assert result is not None
    decision, reason = result
    assert decision in ("block", "warn")
    assert "MCP" in reason or "PYTHONPATH" in reason or "kart" in reason.lower()


def test_blocks_python_m_willow():
    result = check_bash_block("python3 -m willow.fylgja.events.shutdown")
    assert result is not None
    decision, reason = result
    assert decision == "block"
    assert "MCP" in reason


def test_blocks_inline_core_import():
    result = check_bash_block('python3 -c "from core import soil; print(soil.stats())"')
    assert result is not None
    decision, _ = result
    assert decision in ("block", "warn")


def test_allows_install_project_module():
    reason = check_bash_block("python3 -m willow.fylgja.install_project hanuman --ide all")
    assert reason is None


def test_blocks_explore_subagent():
    reason = check_agent_block("Explore")
    assert reason is not None
    assert "willow_find" in reason or "MCP" in reason


def test_blocks_general_purpose_subagent():
    reason = check_agent_block("generalPurpose")
    assert reason is not None
    assert "blocked" in reason.lower()


def test_blocks_explore_subagent_cursor_casing():
    assert check_agent_block("explore") is not None


def test_blocks_shell_subagent():
    assert check_agent_block("shell") is not None


def test_allows_review_subagents():
    assert check_agent_block("bugbot") is None
    assert check_agent_block("security-review") is None


def test_blocks_git_after_cd():
    result = check_bash_block("cd /home/sean/github/willow-2.0 && git status -sb")
    assert result is not None
    assert result[0] == "block"
    assert "git" in result[1].lower() or "Kart" in result[1]


def test_blocks_python_os_walk():
    cmd = 'python3 -c "import os; print(list(os.walk(\".\")))"'
    result = check_bash_block(cmd)
    assert result is not None
    assert result[0] == "block"


def test_blocks_python_heredoc():
    cmd = "python3 << 'EOF'\nimport os\nfor r, ds, fs in os.walk('.'): print(r)\nEOF"
    result = check_bash_block(cmd)
    assert result is not None
    assert result[0] == "block"


def test_blocks_rg_cli():
    result = check_bash_block("rg -n check_boot_gate willow/")
    assert result is not None
    assert result[0] == "block"


def test_hook_guard_blocks_read_of_pre_tool(monkeypatch):
    monkeypatch.delenv("WILLOW_HOOK_MAINTENANCE", raising=False)
    reason = check_hook_tamper_guard(
        "Read",
        {"file_path": "/home/sean/github/willow-2.0/willow/fylgja/events/pre_tool.py"},
    )
    assert reason is not None
    assert "not readable" in reason


def test_hook_guard_allows_with_maintenance_flag(monkeypatch):
    monkeypatch.setenv("WILLOW_HOOK_MAINTENANCE", "1")
    assert check_hook_tamper_guard(
        "Read",
        {"file_path": "/home/sean/github/willow-2.0/willow/fylgja/events/pre_tool.py"},
    ) is None


def test_blocks_general_purpose_agent_legacy():
    reason = check_agent_block("general-purpose")
    assert reason is not None


def test_task_subagent_blocked_via_pre_tool():
    out = _run_pre_tool({
        "tool_name": "Task",
        "tool_input": {"subagent_type": "generalPurpose", "description": "grep the repo"},
        "session_id": "task-block-1",
    })
    assert out.strip()
    data = json.loads(out)
    assert data["decision"] == "block"


def test_kb_first_returns_advisory_when_record_found():
    mock_result = [{"id": "abc", "title": "settings.json", "collection": "hanuman/file-index"}]
    with patch("willow.fylgja.events.pre_tool._mcp_store_search", return_value=mock_result):
        advisory = check_kb_first("/home/sean/.claude/settings.json")
    assert advisory is not None
    assert "KB-FIRST" in advisory


def test_kb_first_returns_none_when_no_record():
    with patch("willow.fylgja.events.pre_tool._mcp_store_search", return_value=[]):
        advisory = check_kb_first("/some/unknown/file.py")
    assert advisory is None


# ── Safety gate integration ───────────────────────────────────────────────────

from io import StringIO


def _run_pre_tool(stdin_data: dict) -> str:
    import willow.fylgja.events.pre_tool as m
    inp = StringIO(json.dumps(stdin_data))
    out = StringIO()
    with patch("sys.stdin", inp), patch("sys.stdout", out):
        try:
            m.main()
        except SystemExit:
            pass
    return out.getvalue()


def test_safety_gate_blocks_training_tool_without_consent():
    out = _run_pre_tool({
        "tool_name": "mcp__willow__index_feedback_write",
        "tool_input": {"app_id": "hanuman"},
        "session_id": "abc123",
    })
    assert out.strip(), "Expected a block response, got empty output"
    data = json.loads(out)
    assert data["decision"] == "block"
    assert "HS-003" in data["reason"] or "training" in data["reason"].lower()


def test_safety_gate_allows_benign_bash():
    # Use an allow-listed command (pytest) so the safety gate is what's exercised,
    # not the workflow guard (git/gh now hard-block on first attempt).
    out = _run_pre_tool({
        "tool_name": "Bash",
        "tool_input": {"command": "python3 -m pytest tests/ -q"},
        "session_id": "abc123",
    })
    if out.strip():
        data = json.loads(out)
        assert data.get("decision") != "block"


# ── Channel enforcement hooks ─────────────────────────────────────────────────

def test_channel_enforce_warns_on_fleet_over_400_chars():
    msg = "x" * 450
    warn = check_channel_enforce(
        "mcp__grove__grove_send_message",
        {"channel_name": "fleet", "content": msg}
    )
    assert warn is not None
    data = json.loads(warn)
    assert data["decision"] == "warn"
    assert "400" in data["reason"]
    assert "#fleet" in data["reason"]


def test_channel_enforce_allows_fleet_under_400_chars():
    msg = "x" * 350
    warn = check_channel_enforce(
        "mcp__grove__grove_send_message",
        {"channel_name": "fleet", "content": msg}
    )
    assert warn is None


def test_channel_enforce_allows_other_channels_over_400_chars():
    msg = "x" * 500
    warn = check_channel_enforce(
        "mcp__grove__grove_send_message",
        {"channel_name": "general", "content": msg}
    )
    assert warn is None


def test_channel_enforce_ignores_non_grove_tools():
    msg = "x" * 500
    warn = check_channel_enforce(
        "store_put",
        {"channel_name": "fleet", "content": msg}
    )
    assert warn is None


def test_channel_enforce_via_pre_tool_integration():
    out = _run_pre_tool({
        "tool_name": "mcp__grove__grove_send_message",
        "tool_input": {
            "channel_name": "fleet",
            "content": "x" * 450
        },
        "session_id": "abc123",
    })
    assert out.strip(), "Expected warn response for >400 char #fleet message"
    data = json.loads(out)
    assert data["decision"] == "warn"


def test_channel_enforce_grove_alias():
    msg = "x" * 450
    warn = check_channel_enforce(
        "mcp__claude_ai_Grove__grove_send_message",  # alternate tool name
        {"channel_name": "fleet", "content": msg}
    )
    assert warn is not None
    data = json.loads(warn)
    assert data["decision"] == "warn"


# ── Block telemetry flag trigger (Phase 4b) ───────────────────────────────────

from unittest.mock import MagicMock
import willow.fylgja.events.pre_tool as _pt


def _make_store(hit_count=0, flag_state=None, flag_opened=False):
    """Return a mock WillowStore with configurable existing telemetry + flag state.

    flag_opened models corpus/block_telemetry's one-shot marker (post-lifecycle-fix):
    once True, _corpus_log_block never opens another willow/flags record for this
    rule_key, regardless of hit_count or the flags collection's own flag_state —
    that's what stops the board from re-cluttering on every later threshold multiple.
    """
    store = MagicMock()
    telemetry_row = (
        {
            "hit_count": hit_count,
            "runtimes": [],
            "first_seen": "2026-01-01T00:00:00+00:00",
            "flag_opened": flag_opened,
        }
        if hit_count else {}
    )
    flag_row = {"flag_state": flag_state} if flag_state else {}

    def _get(collection, record_id):
        if "block_telemetry" in collection:
            return telemetry_row or None
        if "flags" in collection:
            return flag_row or None
        return None

    store.get.side_effect = _get
    return store


def _flag_puts(store):
    return [c for c in store.put.call_args_list if c.args and "flags" in str(c.args[0])]


def _telemetry_puts(store):
    return [c for c in store.put.call_args_list if c.args and "block_telemetry" in str(c.args[0])]


def test_flag_not_opened_below_threshold():
    store = _make_store(hit_count=0)
    with (
        patch("willow.fylgja.events.pre_tool._BLOCK_FLAG_THRESHOLD", 10),
        patch("core.store_port.get_store_port", return_value=store),
    ):
        _pt._corpus_log_block("Bash", "some reason", "sess1")
    assert not _flag_puts(store), "No flag should be opened before threshold"


def test_flag_opened_at_threshold():
    store = _make_store(hit_count=9)  # next hit → 10 = threshold
    with (
        patch("willow.fylgja.events.pre_tool._BLOCK_FLAG_THRESHOLD", 10),
        patch("core.store_port.get_store_port", return_value=store),
    ):
        _pt._corpus_log_block("Bash", "Use MCP instead of shell.", "sess1")
    puts = _flag_puts(store)
    assert puts, "A flag should be opened when hit_count reaches threshold"
    written = puts[0].args[1]
    assert written.get("flag_state") == "open"
    assert "Bash" in written.get("title", "")
    assert "Repeated enforcement" in written.get("title", "")
    assert written.get("source") == "block_telemetry"
    telemetry = _telemetry_puts(store)
    assert telemetry and telemetry[0].args[1].get("flag_opened") is True


def test_flag_not_duplicated_when_already_open():
    store = _make_store(hit_count=9, flag_state="open", flag_opened=True)
    with (
        patch("willow.fylgja.events.pre_tool._BLOCK_FLAG_THRESHOLD", 10),
        patch("core.store_port.get_store_port", return_value=store),
    ):
        _pt._corpus_log_block("Bash", "Use MCP instead of shell.", "sess1")
    assert not _flag_puts(store), "Should not re-open a flag that is already open"


def test_flag_not_reopened_after_resolution():
    """Lifecycle fix: once flag_opened is set, later threshold crossings (20, 30,
    40, 70...) must NOT mint another willow/flags record even if the operator
    resolved the earlier one — this is what stopped the board from re-cluttering
    forever (flag-bash-attempt1-routing). The hit_count keeps climbing in
    corpus/block_telemetry regardless; only the one-shot alert is suppressed."""
    store = _make_store(hit_count=19, flag_state="resolved", flag_opened=True)
    with (
        patch("willow.fylgja.events.pre_tool._BLOCK_FLAG_THRESHOLD", 10),
        patch("core.store_port.get_store_port", return_value=store),
    ):
        _pt._corpus_log_block("Bash", "Use MCP instead of shell.", "sess1")
    assert not _flag_puts(store), "Should not reopen once flag_opened is set, even past another threshold multiple"
    telemetry = _telemetry_puts(store)
    assert telemetry and telemetry[0].args[1].get("hit_count") == 20, "Counter still climbs in telemetry"


# ── Per-session Bash counter ──────────────────────────────────────────────────


def test_bash_counter_increments(tmp_path, monkeypatch):
    monkeypatch.setattr(_pt, "_bash_counter_path", lambda sid: tmp_path / f"bash-{sid}.txt")
    assert _pt._increment_bash_count("s1") == 1
    assert _pt._increment_bash_count("s1") == 2
    assert _pt._increment_bash_count("s1") == 3


def test_bash_counter_isolated_per_session(tmp_path, monkeypatch):
    monkeypatch.setattr(_pt, "_bash_counter_path", lambda sid: tmp_path / f"bash-{sid}.txt")
    _pt._increment_bash_count("sess-a")
    _pt._increment_bash_count("sess-a")
    assert _pt._increment_bash_count("sess-b") == 1


def test_count_warn_emitted_at_threshold(tmp_path, monkeypatch):
    monkeypatch.setattr(_pt, "_bash_counter_path", lambda sid: tmp_path / f"bash-{sid}.txt")
    # Drive count to threshold - 1
    for _ in range(4):
        _pt._increment_bash_count("s-thresh")
    # Fifth call crosses threshold=5. Use an allow-listed command (pytest) so the
    # BASH-COUNT nudge is what's emitted, not a workflow block.
    out = _run_pre_tool({
        "tool_name": "Bash",
        "tool_input": {"command": "python3 -m pytest tests/ -q"},
        "session_id": "s-thresh",
    })
    assert out.strip(), "Expected a warn at threshold crossing"
    data = json.loads(out)
    assert data["decision"] == "warn"
    assert "BASH-COUNT" in data["reason"]
    assert "5" in data["reason"]


def test_count_warn_not_emitted_below_threshold(tmp_path, monkeypatch):
    monkeypatch.setattr(_pt, "_bash_counter_path", lambda sid: tmp_path / f"bash-{sid}.txt")
    # Only 3 calls — threshold=5 not reached
    for _ in range(3):
        _pt._increment_bash_count("s-low")
    out = _run_pre_tool({
        "tool_name": "Bash",
        "tool_input": {"command": "python3 -m pytest tests/ -q"},
        "session_id": "s-low",
    })
    # No output expected (pytest is allow-listed, count=4 < threshold=5)
    if out.strip():
        data = json.loads(out)
        assert data.get("decision") != "block"
        assert "BASH-COUNT" not in data.get("reason", "")


# ── Bash warn escalation (behavioral feedback loop) ─────────────────────────────


def test_grep_blocks_on_first_attempt(tmp_path, monkeypatch):
    """grep is a read-only habit — block immediately, no free first attempt, and
    name a tool that exists in the session (NOT native Grep, which is absent under
    the Willow MCP profile) so the agent routes right without burning a strike."""
    monkeypatch.setattr(_pt, "_session_rule_strikes_path", lambda sid: tmp_path / f"strikes-{sid}.json")
    monkeypatch.setattr(_pt, "_bash_counter_path", lambda sid: tmp_path / f"bash-{sid}.txt")
    out1 = _run_pre_tool({
        "tool_name": "Bash",
        "tool_input": {"command": "grep -r foo ."},
        "session_id": "grep-block-s1",
    })
    assert out1.strip()
    data1 = json.loads(out1)
    assert data1["decision"] == "block"
    reason = data1["reason"]
    assert "Grep(" not in reason
    assert "willow_find" in reason or "code_graph_search" in reason
    assert "willow_run" in reason or "agent_task_submit" in reason


def test_find_blocks_on_first_attempt(tmp_path, monkeypatch):
    """find → code_graph_search/willow_find/Kart; block on first attempt, no free
    strike, and never name native Glob (absent under the Willow MCP profile)."""
    monkeypatch.setattr(_pt, "_session_rule_strikes_path", lambda sid: tmp_path / f"strikes-{sid}.json")
    monkeypatch.setattr(_pt, "_bash_counter_path", lambda sid: tmp_path / f"bash-{sid}.txt")
    out1 = _run_pre_tool({
        "tool_name": "Bash",
        "tool_input": {"command": "find . -name '*.py'"},
        "session_id": "find-block-s1",
    })
    assert out1.strip()
    data1 = json.loads(out1)
    assert data1["decision"] == "block"
    reason = data1["reason"]
    assert "Glob(" not in reason
    assert "code_graph_search" in reason or "willow_find" in reason
    assert "willow_run" in reason or "agent_task_submit" in reason


def test_warn_escalates_to_block_on_second_strike(tmp_path, monkeypatch):
    # du is still a warn-tier habit (Glob/Kart alternative); use it to exercise the
    # warn→block escalation now that git/gh/grep/find hard-block on first attempt.
    monkeypatch.setattr(_pt, "_session_rule_strikes_path", lambda sid: tmp_path / f"strikes-{sid}.json")
    monkeypatch.setattr(_pt, "_bash_counter_path", lambda sid: tmp_path / f"bash-{sid}.txt")
    cmd = "du -sh /tmp"
    out1 = _run_pre_tool({
        "tool_name": "Bash",
        "tool_input": {"command": cmd},
        "session_id": "esc-du",
    })
    assert out1.strip()
    assert json.loads(out1)["decision"] == "warn"
    out2 = _run_pre_tool({
        "tool_name": "Bash",
        "tool_input": {"command": cmd},
        "session_id": "esc-du",
    })
    data2 = json.loads(out2)
    assert data2["decision"] == "block"
    assert "ESCALATED" in data2["reason"]


def test_session_ban_after_third_strike_on_block_pattern(tmp_path, monkeypatch):
    monkeypatch.setattr(_pt, "_session_rule_strikes_path", lambda sid: tmp_path / f"strikes-{sid}.json")
    monkeypatch.setattr(_pt, "_bash_counter_path", lambda sid: tmp_path / f"bash-{sid}.txt")
    cmd = "cat /etc/hosts"
    for i in range(3):
        out = _run_pre_tool({
            "tool_name": "Bash",
            "tool_input": {"command": cmd},
            "session_id": "ban-s1",
        })
        assert out.strip()
        data = json.loads(out)
        assert data["decision"] == "block"
    out4 = _run_pre_tool({
        "tool_name": "Bash",
        "tool_input": {"command": cmd},
        "session_id": "ban-s1",
    })
    data4 = json.loads(out4)
    assert data4["decision"] == "block"
    assert "SESSION-BAN" in data4["reason"]


def test_warns_native_web_search(monkeypatch):
    import willow.fylgja.events.pre_tool as pt

    monkeypatch.setattr(pt, "_NATIVE_WEB_SEARCH_BLOCK", False)
    result = check_native_web_block("WebSearch")
    assert result is not None
    decision, reason = result
    assert decision == "warn"
    assert "willow_web_search" in reason


def test_warns_native_web_fetch(monkeypatch):
    import willow.fylgja.events.pre_tool as pt

    monkeypatch.setattr(pt, "_NATIVE_WEB_FETCH_BLOCK", False)
    result = check_native_web_block("WebFetch")
    assert result is not None
    decision, reason = result
    assert decision == "warn"
    assert "willow_web_search" in reason or "willow_external" in reason


def test_blocks_native_web_search(monkeypatch):
    import willow.fylgja.events.pre_tool as pt

    monkeypatch.setattr(pt, "_NATIVE_WEB_SEARCH_BLOCK", True)
    result = check_native_web_block("WebSearch")
    assert result is not None
    decision, reason = result
    assert decision == "block"
    assert "willow_web_search" in reason


def test_blocks_native_web_fetch(monkeypatch):
    import willow.fylgja.events.pre_tool as pt

    monkeypatch.setattr(pt, "_NATIVE_WEB_FETCH_BLOCK", True)
    result = check_native_web_block("WebFetch")
    assert result is not None
    decision, reason = result
    assert decision == "block"
    assert "willow_web_fetch" in reason


def test_web_fetch_pre_tool_blocks():
    out = _run_pre_tool({
        "tool_name": "WebFetch",
        "tool_input": {"url": "https://example.com/article"},
        "session_id": "web-w1",
    })
    data = json.loads(out)
    assert data["decision"] == "block"
    assert "willow_web_fetch" in data["reason"] or "MCP" in data["reason"]


# ── Boot gate + Kart reuse (salvaged from #597) ────────────────────────────────


def test_boot_gate_blocks_without_sentinel(tmp_path, monkeypatch):
    missing = tmp_path / "willow-boot-done-willow.flag"
    monkeypatch.setattr(_pt, "BOOT_DONE", missing)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    reason = _pt.check_boot_gate("Bash", {"command": "echo hi"})
    assert reason is not None
    assert "Boot sentinel absent" in reason


def test_boot_gate_allows_read_boot_md(tmp_path, monkeypatch):
    missing = tmp_path / "willow-boot-done-willow.flag"
    monkeypatch.setattr(_pt, "BOOT_DONE", missing)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    assert _pt.check_boot_gate("Read", {"file_path": _pt._BOOT_MD_PATH}) is None


def test_boot_gate_allows_write_sentinel(tmp_path, monkeypatch):
    missing = tmp_path / "willow-boot-done-willow.flag"
    monkeypatch.setattr(_pt, "BOOT_DONE", missing)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    assert _pt.check_boot_gate("Write", {"file_path": str(missing)}) is None
    assert _pt.check_boot_gate("Write", {"path": str(missing)}) is None


def test_boot_gate_skipped_under_pytest(monkeypatch, tmp_path):
    missing = tmp_path / "willow-boot-done-willow.flag"
    monkeypatch.setattr(_pt, "BOOT_DONE", missing)
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_fylgja/test_pre_tool.py::test_x")
    assert _pt.check_boot_gate("Bash", {}) is None


def test_kart_reuse_blocks_duplicate_bash(tmp_path, monkeypatch):
    pending = tmp_path / "kart-pending.json"
    monkeypatch.setattr(_pt, "_kart_pending_path", lambda sid: pending)
    pending.write_text(json.dumps({
        "command": "ls -la /tmp",
        "task_id": "ABC123",
        "ts": time.time(),
    }))
    reason = _pt.check_kart_reuse(
        "Bash", {"command": "ls -la /tmp"}, "session-1",
    )
    assert reason is not None
    assert "Already submitted to Kart" in reason
    assert "ABC123" in reason


def test_kart_reuse_clears_on_kart_task_run(tmp_path, monkeypatch):
    pending = tmp_path / "kart-pending.json"
    monkeypatch.setattr(_pt, "_kart_pending_path", lambda sid: pending)
    pending.write_text(json.dumps({"command": "ls", "task_id": "X", "ts": time.time()}))
    assert _pt.check_kart_reuse("mcp__willow__kart_task_run", {}, "s1") is None
    assert not pending.exists()


def test_kart_reuse_allows_different_command(tmp_path, monkeypatch):
    pending = tmp_path / "kart-pending.json"
    monkeypatch.setattr(_pt, "_kart_pending_path", lambda sid: pending)
    pending.write_text(json.dumps({
        "command": "ls -la",
        "task_id": "ABC",
        "ts": time.time(),
    }))
    assert _pt.check_kart_reuse("Bash", {"command": "pwd"}, "s1") is None
