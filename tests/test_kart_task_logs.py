"""Tests for KP7/S10 — durable per-task Kart log artifacts."""
import json
from pathlib import Path

import pytest

from core.kart_execute import execute_task_row
from core.kart_sandbox import KART_LOG_RETENTION, _prune_task_logs, write_task_log


@pytest.fixture
def logs_home(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_HOME", str(tmp_path))
    # willow_home() resolution prefers WILLOW_HOME; keep the test hermetic
    monkeypatch.setenv("WILLOW_KART_NO_BWRAP", "1")
    return tmp_path


def test_write_task_log_contents(logs_home):
    result = {
        "returncode": 1,
        "stdout": "clipped",
        "stderr": "boom",
        "elapsed_s": 0.1,
        "sandbox": "plain",
        "sandbox_manifest": {"allow_net": False, "tmpfs": ["/tmp"]},
    }
    log_dir = write_task_log(
        "TASK-123", "echo hi && false", "failed", result,
        full_stdout="full stdout text", full_stderr="full stderr text",
    )
    assert log_dir is not None
    files = {p.name for p in Path(log_dir).iterdir()}
    assert files == {"meta.json", "stdout.log", "stderr.log"}
    meta = json.loads((Path(log_dir) / "meta.json").read_text())
    assert meta["task_id"] == "TASK-123"
    assert meta["status"] == "failed"
    assert meta["returncode"] == 1
    assert "env_keys" in meta and isinstance(meta["env_keys"], list)
    # env VALUES must never appear in the artifact
    assert "PATH=" not in (Path(log_dir) / "meta.json").read_text()
    assert (Path(log_dir) / "stdout.log").read_text() == "full stdout text"


def test_write_task_log_sanitizes_id(logs_home):
    log_dir = write_task_log("../escape/../X", "cmd", "failed", {"returncode": 1})
    assert log_dir is not None
    assert ".." not in log_dir
    assert log_dir.endswith("escapeX") or "escape" in log_dir


def test_execute_task_row_failure_writes_artifact(logs_home):
    status, result = execute_task_row(
        {"id": "FAIL-1", "task": "false", "goal": None}, pg=None
    )
    assert status == "failed"
    assert "log_dir" in result
    assert "_full_stdout" not in result and "_full_stderr" not in result
    meta = json.loads(
        (Path(result["log_dir"]) / "meta.json").read_text()
    )
    assert meta["task_id"] == "FAIL-1"


def test_execute_task_row_success_skips_artifact(logs_home):
    status, result = execute_task_row(
        {"id": "OK-1", "task": "echo ok", "goal": None}, pg=None
    )
    assert status == "completed"
    assert "log_dir" not in result
    assert "_full_stdout" not in result and "_full_stderr" not in result


def test_execute_task_row_log_all_env(logs_home, monkeypatch):
    monkeypatch.setenv("WILLOW_KART_LOG_ALL", "1")
    status, result = execute_task_row(
        {"id": "OK-2", "task": "echo always", "goal": None}, pg=None
    )
    assert status == "completed"
    assert "log_dir" in result


def test_prune_keeps_newest(tmp_path):
    import os
    import time
    for i in range(KART_LOG_RETENTION + 10):
        d = tmp_path / f"task-{i:04d}"
        d.mkdir()
        os.utime(d, (time.time() + i, time.time() + i))
    _prune_task_logs(tmp_path)
    remaining = sorted(p.name for p in tmp_path.iterdir())
    assert len(remaining) == KART_LOG_RETENTION
    assert remaining[0] == "task-0010"
