"""Tests for W19BT — bi-temporal edges."""
import sys
from pathlib import Path
from datetime import datetime, timezone
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.pg_bridge import PgBridge


@pytest.fixture
def pg():
    bridge = PgBridge()
    with bridge.conn.cursor() as cur:
        cur.execute("DELETE FROM knowledge WHERE id LIKE 'bt_test_%'")
    bridge.conn.commit()
    try:
        yield bridge
    finally:
        bridge.close()


def test_contradiction_closes_old_edge(pg):
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t1 = datetime(2026, 3, 1, tzinfo=timezone.utc)
    pg.knowledge_put({"id": "bt_test_1", "project": "global",
                       "title": "old fact", "valid_at": t0})
    pg.knowledge_close("bt_test_1", t1)
    with pg.conn.cursor() as cur:
        cur.execute("SELECT invalid_at FROM knowledge WHERE id = 'bt_test_1'")
        row = cur.fetchone()
    assert row[0] is not None


def test_closed_edge_excluded_from_search(pg):
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t1 = datetime(2026, 3, 1, tzinfo=timezone.utc)
    pg.knowledge_put({"id": "bt_test_2", "project": "global",
                       "title": "superseded fact", "summary": "old version", "valid_at": t0})
    pg.knowledge_close("bt_test_2", t1)
    results = pg.knowledge_search("superseded", project="global", include_invalid=False)
    assert len(results) == 0


def test_history_preserved_when_include_invalid(pg):
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t1 = datetime(2026, 3, 1, tzinfo=timezone.utc)
    pg.knowledge_put({"id": "bt_test_3", "project": "global",
                       "title": "archived fact", "summary": "history preserved", "valid_at": t0})
    pg.knowledge_close("bt_test_3", t1)
    results = pg.knowledge_search("archived", project="global", include_invalid=True)
    assert len(results) == 1
    assert results[0]["id"] == "bt_test_3"


def test_open_edge_visible_in_search(pg):
    pg.knowledge_put({"id": "bt_test_4", "project": "global",
                       "title": "current fact", "summary": "still valid"})
    results = pg.knowledge_search("current fact", project="global")
    assert len(results) == 1
