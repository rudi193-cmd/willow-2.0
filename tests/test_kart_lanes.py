"""Kart lane separation — fast vs batch queue isolation."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("WILLOW_PG_DB", "willow_20_test")

from core.kart_lanes import (
    KART_LANE_BATCH,
    KART_LANE_FAST,
    KART_WORKER_MODE_ALL,
    KART_WORKER_MODE_BATCH,
    KART_WORKER_MODE_FAST,
    fast_worker_slots,
    normalize_lane,
    reaper_alignment_warning,
    worker_mode,
)
from core.pg_bridge import PgBridge


def test_normalize_lane_defaults_and_rejects():
    assert normalize_lane(None) == KART_LANE_FAST
    assert normalize_lane("") == KART_LANE_FAST
    assert normalize_lane("fast") == KART_LANE_FAST
    assert normalize_lane("batch") == KART_LANE_BATCH
    with pytest.raises(ValueError, match="unknown kart lane"):
        normalize_lane("gpu")


def test_worker_mode_defaults_fast(monkeypatch):
    monkeypatch.delenv("KART_WORKER_LANE", raising=False)
    assert worker_mode() == KART_WORKER_MODE_FAST


def test_worker_mode_batch(monkeypatch):
    monkeypatch.setenv("KART_WORKER_LANE", "batch")
    assert worker_mode() == KART_WORKER_MODE_BATCH


def test_worker_mode_all_legacy(monkeypatch):
    monkeypatch.setenv("KART_WORKER_LANE", "all")
    assert worker_mode() == KART_WORKER_MODE_ALL


def test_fast_worker_slots_default(monkeypatch):
    monkeypatch.delenv("KART_FAST_WORKERS", raising=False)
    assert fast_worker_slots() == 3


def test_fast_worker_slots_env(monkeypatch):
    monkeypatch.setenv("KART_FAST_WORKERS", "5")
    assert fast_worker_slots() == 5


def test_reaper_alignment_warning_ok(monkeypatch):
    monkeypatch.setenv("KART_DAEMON_TIMEOUT", "1800")
    monkeypatch.setenv("KART_STALE_SECONDS", "3600")
    assert reaper_alignment_warning() is None


def test_reaper_alignment_warning_misconfigured(monkeypatch):
    monkeypatch.setenv("KART_DAEMON_TIMEOUT", "1800")
    monkeypatch.setenv("KART_STALE_SECONDS", "1900")
    msg = reaper_alignment_warning()
    assert msg is not None
    assert "KART_STALE_SECONDS" in msg


@pytest.fixture(scope="module")
def pg():
    bridge = PgBridge()
    yield bridge
    bridge.close()


def test_claim_respects_lane_filter(pg):
    agent = "lane_test"
    fast_id = pg.submit_task("echo fast", submitted_by="test", agent=agent, lane="fast")
    batch_id = pg.submit_task("echo batch", submitted_by="test", agent=agent, lane="batch")
    assert fast_id and batch_id

    claimed_fast = pg.claim_kart_tasks(agent=agent, limit=5, lane=KART_LANE_FAST)
    assert [r["id"] for r in claimed_fast] == [fast_id]

    # batch row still pending
    pending_batch = pg.pending_tasks(agent=agent, lane=KART_LANE_BATCH)
    assert any(r["id"] == batch_id for r in pending_batch)

    claimed_batch = pg.claim_kart_tasks(agent=agent, limit=5, lane=KART_LANE_BATCH)
    assert [r["id"] for r in claimed_batch] == [batch_id]

    for tid in (fast_id, batch_id):
        pg.task_complete(tid, {"stdout": "ok", "returncode": 0}, "completed")


def test_kart_task_run_lane_does_not_wait_on_batch(pg, monkeypatch):
    """tasks_by_status(lane=fast) must ignore a running batch task."""
    agent = "lane_poll_test"
    batch_id = pg.submit_task("sleep 999", submitted_by="test", agent=agent, lane="batch")
    claimed = pg.claim_kart_tasks(agent=agent, limit=1, lane=KART_LANE_BATCH)
    assert claimed and claimed[0]["id"] == batch_id

    running_all = pg.tasks_by_status(agent=agent, statuses=["running"], limit=5)
    running_fast = pg.tasks_by_status(
        agent=agent, statuses=["running"], limit=5, lane=KART_LANE_FAST
    )
    assert len(running_all) == 1
    assert running_fast == []

    pg.task_complete(batch_id, {"cancelled": True}, "failed")


def test_kart_queue_stats_lane_fields(pg):
    agent = "lane_stats_test"
    fast_id = pg.submit_task("echo stats-fast", submitted_by="test", agent=agent, lane="fast")
    batch_id = pg.submit_task("echo stats-batch", submitted_by="test", agent=agent, lane="batch")
    assert fast_id and batch_id
    stats = pg.kart_queue_stats(agent=agent)
    assert stats["pending_fast"] >= 1
    assert stats["pending_batch"] >= 1
    assert "oldest_pending_fast_s" in stats
    assert "oldest_pending_batch_s" in stats
    for tid in (fast_id, batch_id):
        pg.task_complete(tid, {"stdout": "ok", "returncode": 0}, "completed")
