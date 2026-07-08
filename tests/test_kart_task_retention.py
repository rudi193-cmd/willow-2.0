"""Kart task retention — prune old terminal rows."""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("WILLOW_PG_DB", "willow_20_test")

from core.pg_bridge import PgBridge


@pytest.fixture(scope="module")
def pg():
    bridge = PgBridge()
    yield bridge
    bridge.close()


def _insert_terminal(pg, task_id: str, status: str, age_days: int) -> None:
    ts = datetime.now(timezone.utc) - timedelta(days=age_days)
    pg._ensure_conn()
    with pg.conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO tasks (id, task, submitted_by, agent, status, lane, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (task_id, "echo old", "test", "retention_test", status, "fast", ts, ts),
        )
    pg.conn.commit()


def test_prune_completed_tasks_deletes_old_terminal(pg):
    old_ok = "RTOLD001"
    recent = "RTNEW001"
    _insert_terminal(pg, old_ok, "completed", age_days=10)
    _insert_terminal(pg, recent, "completed", age_days=1)
    deleted = pg.prune_completed_tasks(days=7, agent="retention_test", limit=100)
    assert deleted >= 1
    rows = pg.tasks_by_status(agent="retention_test", statuses=["completed"], limit=10)
    ids = {r["id"] for r in rows}
    assert old_ok not in ids
    assert recent in ids
    for tid in ids:
        pg.conn.cursor().execute("DELETE FROM tasks WHERE id=%s", (tid,))
    pg.conn.commit()
