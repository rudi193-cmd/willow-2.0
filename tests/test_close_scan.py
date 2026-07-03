"""Tests for willow.fylgja.close_scan — the mechanized /shutdown pre-scan."""
import json

import pytest

from willow.fylgja import close_scan


# ---------------------------------------------------------------------------
# PR-thread reconciliation
# ---------------------------------------------------------------------------

def _fake_pr_states(states: dict):
    def fake(number: str, repo_root):
        return states.get(number, {"state": "UNKNOWN", "detail": "no such pr"})
    return fake


def test_merged_pr_thread_dropped(monkeypatch, tmp_path):
    monkeypatch.setattr(close_scan, "_pr_state", _fake_pr_states({
        "682": {"state": "MERGED", "merged_at": "2026-07-03T07:00:00Z"},
    }))
    result = close_scan.reconcile_pr_threads(
        ["Boot digest diet merged (#682)"], tmp_path)
    assert result["keep"] == []
    assert len(result["drop"]) == 1
    assert "#682 MERGED" in result["drop"][0]["reason"]


def test_open_pr_thread_kept_with_status(monkeypatch, tmp_path):
    monkeypatch.setattr(close_scan, "_pr_state", _fake_pr_states({
        "700": {"state": "OPEN", "draft": False, "title": "wip"},
    }))
    result = close_scan.reconcile_pr_threads(["PR #700 needs review"], tmp_path)
    assert result["drop"] == []
    assert result["keep"][0]["pr_status"]["#700"]["state"] == "OPEN"


def test_unknown_pr_state_never_drops(monkeypatch, tmp_path):
    monkeypatch.setattr(close_scan, "_pr_state", _fake_pr_states({}))
    result = close_scan.reconcile_pr_threads(["follow-up on #999"], tmp_path)
    assert result["drop"] == []
    assert len(result["keep"]) == 1


def test_cross_repo_ref_not_resolved_here(monkeypatch, tmp_path):
    monkeypatch.setattr(
        close_scan, "_pr_state",
        lambda *a, **k: pytest.fail("repo#N refs must not hit gh for this repo"))
    result = close_scan.reconcile_pr_threads(
        ["almanac-template#2 vs pass-4 Jeles discovery undecided"], tmp_path)
    assert result["no_pr_ref"] == ["almanac-template#2 vs pass-4 Jeles discovery undecided"]


def test_thread_without_pr_ref_passes_through(monkeypatch, tmp_path):
    monkeypatch.setattr(
        close_scan, "_pr_state",
        lambda *a, **k: pytest.fail("gh must not be called without a PR ref"))
    result = close_scan.reconcile_pr_threads(["WCE scenarios not started"], tmp_path)
    assert result["no_pr_ref"] == ["WCE scenarios not started"]


def test_mixed_refs_kept_when_any_pr_open(monkeypatch, tmp_path):
    monkeypatch.setattr(close_scan, "_pr_state", _fake_pr_states({
        "1": {"state": "MERGED"},
        "2": {"state": "OPEN"},
    }))
    result = close_scan.reconcile_pr_threads(["#1 merged, follow-up in #2"], tmp_path)
    assert result["drop"] == []
    assert len(result["keep"]) == 1


def test_pr_state_queried_once_per_number(monkeypatch, tmp_path):
    calls = []

    def counting(number, repo_root):
        calls.append(number)
        return {"state": "OPEN"}

    monkeypatch.setattr(close_scan, "_pr_state", counting)
    close_scan.reconcile_pr_threads(["#5 first", "#5 again", "also #5"], tmp_path)
    assert calls == ["5"]


# ---------------------------------------------------------------------------
# Open-thread extraction
# ---------------------------------------------------------------------------

def test_v2_open_threads_parsed():
    content = (
        "## Open Threads\n\n"
        "- **[label]** — first thread #12\n"
        "- second thread\n\n"
        "## What We Agreed On\n- x\n"
    )
    threads = close_scan._v2_open_threads(content)
    assert len(threads) == 2
    assert "#12" in threads[0]


def test_v2_open_threads_none_bullet_skipped():
    content = "## Open Threads\n\n- none\n\n## Next\n"
    assert close_scan._v2_open_threads(content) == []


def test_latest_open_threads_prefers_v3_block(monkeypatch, tmp_path):
    agent = "testagent"
    dest = tmp_path / agent
    dest.mkdir()
    block = {
        "format": "v3",
        "claims": [{"id": "c1", "text": "open thread from v3", "kind": "prose"}],
    }
    (dest / f"session_handoff-2026-07-03a_{agent}.md").write_text(
        "## Open Threads\n- stale v2 bullet\n\n```json\n"
        + json.dumps(block) + "\n```\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(close_scan, "handoff_dir", lambda a: tmp_path / a)
    assert close_scan.latest_open_threads(agent) == ["open thread from v3"]


def test_latest_open_threads_missing_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(close_scan, "handoff_dir", lambda a: tmp_path / "absent")
    assert close_scan.latest_open_threads("nobody") == []


# ---------------------------------------------------------------------------
# Process flags
# ---------------------------------------------------------------------------

def _flag_store(monkeypatch, tmp_path, records):
    monkeypatch.setenv("WILLOW_STORE_ROOT", str(tmp_path))
    from core import soil

    for rid, rec in records.items():
        soil.put("testagent/flags", rid, rec)
    return soil


def test_dead_pid_flag_reported_not_closed_on_dry_run(monkeypatch, tmp_path):
    soil = _flag_store(monkeypatch, tmp_path, {
        "process-dead": {"flag_state": "running", "title": "old job", "pid": 2 ** 22 + 12345},
    })
    result = close_scan.scan_process_flags("testagent", apply=False)
    assert [e["id"] for e in result["closed"]] == ["process-dead"]
    assert soil.get("testagent/flags", "process-dead")["flag_state"] == "running"


def test_dead_pid_flag_closed_with_apply(monkeypatch, tmp_path):
    soil = _flag_store(monkeypatch, tmp_path, {
        "process-dead": {"flag_state": "running", "title": "old job", "pid": 2 ** 22 + 12345},
    })
    result = close_scan.scan_process_flags("testagent", apply=True)
    assert [e["id"] for e in result["closed"]] == ["process-dead"]
    updated = soil.get("testagent/flags", "process-dead")
    assert updated["flag_state"] == "complete"
    assert updated["resolved_by"] == "close_scan"


def test_live_pid_flag_stays_running(monkeypatch, tmp_path):
    _flag_store(monkeypatch, tmp_path, {
        "process-live": {"flag_state": "running", "title": "this test", "pid": 1},
    })
    result = close_scan.scan_process_flags("testagent", apply=True)
    assert [e["id"] for e in result["still_running"]] == ["process-live"]
    assert result["closed"] == []


def test_flag_without_pid_is_ambiguous_with_log_tail(monkeypatch, tmp_path):
    log = tmp_path / "job.log"
    log.write_text("line1\nline2\ndone\n", encoding="utf-8")
    _flag_store(monkeypatch, tmp_path, {
        "process-logonly": {
            "flag_state": "open", "title": "log job", "note": f"log at {log}",
        },
    })
    result = close_scan.scan_process_flags("testagent", apply=True)
    assert [e["id"] for e in result["ambiguous"]] == ["process-logonly"]
    assert result["ambiguous"][0]["log_tail"].endswith("done")


def test_non_process_and_closed_flags_ignored(monkeypatch, tmp_path):
    _flag_store(monkeypatch, tmp_path, {
        "flag-other": {"flag_state": "open", "title": "not a process flag"},
        "process-done": {"flag_state": "complete", "title": "already closed", "pid": 1},
    })
    result = close_scan.scan_process_flags("testagent", apply=True)
    assert result["closed"] == []
    assert result["still_running"] == []
    assert result["ambiguous"] == []


def test_soil_all_records_survives_bare_string_rows(monkeypatch):
    from core import soil

    class FakeStore:
        def list(self, collection):
            return ["bare string row", {"id": "real", "flag_state": "open"}]

    monkeypatch.setattr(soil, "_get_store", FakeStore)
    records = soil.all_records("any/flags")
    assert len(records) == 2
    assert records[0] == {"value": "bare string row", "_id": None}
    assert records[1]["_id"] == "real"


# ---------------------------------------------------------------------------
# MEMORY.md lint
# ---------------------------------------------------------------------------

def test_memory_lint_flags_entries_without_atom_id(tmp_path):
    md = tmp_path / "MEMORY.md"
    md.write_text(
        "# Memory index\n\n"
        "- [Has ID](a.md) — something (KB 4F24F8F5)\n"
        "- [No ID](b.md) — something else\n",
        encoding="utf-8",
    )
    result = close_scan.lint_memory_index(md)
    assert result["entries"] == 2
    assert result["missing_atom_id"] == ["No ID"]


def test_memory_lint_missing_file_is_empty(tmp_path):
    result = close_scan.lint_memory_index(tmp_path / "absent.md")
    assert result == {"entries": 0, "missing_atom_id": []}


# ---------------------------------------------------------------------------
# run_scan integration shape
# ---------------------------------------------------------------------------

def test_run_scan_shape_never_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("WILLOW_STORE_ROOT", str(tmp_path))
    monkeypatch.setattr(close_scan, "handoff_dir", lambda a: tmp_path / "none")
    monkeypatch.setattr(
        close_scan, "default_memory_index", lambda root: tmp_path / "absent.md")
    result = close_scan.run_scan("testagent", tmp_path, apply=False)
    assert set(result) == {"agent", "generated_at", "applied", "flags", "threads", "memory"}
    assert result["applied"] is False
