"""Kart batch lane visibility — session tools surface batch without blocking."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("WILLOW_PG_DB", "willow_20_test")

from core.kart_lanes import KART_LANE_FAST
from core.pg_bridge import PgBridge


@pytest.fixture(scope="module")
def pg():
    bridge = PgBridge()
    yield bridge
    bridge.close()


def test_agent_task_list_includes_lane_queue(pg):
    agent = "batch_vis_test"
    fast_id = pg.submit_task("echo fast", submitted_by="test", agent=agent, lane="fast")
    batch_id = pg.submit_task("echo batch", submitted_by="test", agent=agent, lane="batch")
    assert fast_id and batch_id

    pending_fast = pg.pending_tasks(agent, limit=10, lane=KART_LANE_FAST)
    stats = pg.kart_queue_stats(agent)
    assert int(stats.get("pending_fast") or 0) >= 1
    assert int(stats.get("pending_batch") or 0) >= 1
    assert any(r["id"] == fast_id for r in pending_fast)

    for tid in (fast_id, batch_id):
        pg.task_complete(tid, {"stdout": "ok", "returncode": 0}, "completed")
