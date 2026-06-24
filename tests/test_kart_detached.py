"""Tests for core/kart_detached.py — the detached (no-timeout) execution lane.

The lane exists because the kart daemon SIGKILLs every task at KART_DAEMON_TIMEOUT
(default 30 min). These tests run in plain (non-bwrap) mode via WILLOW_KART_NO_BWRAP
so they are deterministic and bwrap-independent.
"""
import json
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("WILLOW_PG_DB", "willow_20_test")

from core import kart_detached  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_root(tmp_path, monkeypatch):
    # No bwrap (plain shell) + a throwaway registry dir so tests never touch ~/.willow.
    monkeypatch.setenv("WILLOW_KART_NO_BWRAP", "1")
    monkeypatch.setenv("WILLOW_HOME", str(tmp_path))
    # detached_root() prefers willow_home(); force the env fallback for hermeticity.
    monkeypatch.setattr(
        kart_detached, "detached_root",
        lambda: _mkroot(tmp_path),
    )


def _mkroot(tmp_path):
    d = Path(tmp_path) / "kart-detached"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _wait(task_id, *, want=("completed", "failed", "died"), timeout=15.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = kart_detached.detached_status(task_id)
        if last and last.get("state") in want:
            return last
        time.sleep(0.1)
    return last


def test_new_task_id_shape():
    tid = kart_detached.new_task_id()
    assert len(tid) == 8 and tid == tid.upper()


def test_launch_and_complete():
    handle = kart_detached.launch_detached("echo detached-lane-ok && sleep 0.2")
    assert handle["detached"] is True
    assert handle["state"] == "running"
    tid = handle["task_id"]
    assert kart_detached.is_detached(tid)

    st = _wait(tid)
    assert st is not None
    assert st["state"] == "completed", st
    assert st["returncode"] == 0
    assert "detached-lane-ok" in st["log_tail"]
    assert st.get("elapsed_s") is not None


def test_failing_job_reports_failed_with_rc():
    handle = kart_detached.launch_detached("echo boom; exit 3")
    st = _wait(handle["task_id"])
    assert st["state"] == "failed", st
    assert st["returncode"] == 3
    assert "boom" in st["log_tail"]


def test_status_unknown_id_returns_none():
    assert kart_detached.detached_status("ZZZZ9999") is None
    assert kart_detached.is_detached("ZZZZ9999") is False


def test_no_timeout_kill_beyond_poll_window():
    """A job longer than the daemon's poll timeout still completes — the whole point.

    We don't wait 30 min; we assert the lane imposes no subprocess timeout by running
    past the 2s grace/poll cadence used elsewhere and confirming clean completion.
    """
    handle = kart_detached.launch_detached("sleep 3 && echo survived")
    # Still running shortly after launch (not killed, not instantly done).
    time.sleep(1.0)
    mid = kart_detached.detached_status(handle["task_id"])
    assert mid["state"] == "running", mid
    st = _wait(handle["task_id"], timeout=20.0)
    assert st["state"] == "completed", st
    assert "survived" in st["log_tail"]


def test_meta_persisted():
    handle = kart_detached.launch_detached("true")
    _wait(handle["task_id"])
    meta = json.loads(
        (kart_detached.detached_root() / handle["task_id"] / "meta.json").read_text()
    )
    assert meta["task_id"] == handle["task_id"]
    assert "supervisor_pid" in meta
