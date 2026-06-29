"""Tests for W19NS — namespace scoping."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.pg_bridge import PgBridge


@pytest.fixture
def pg():
    bridge = PgBridge()
    with bridge.conn.cursor() as cur:
        cur.execute(
            "DELETE FROM knowledge WHERE project IN ('willow', 'saps1', 'global') "
            "AND id LIKE 'ns_test_%'"
        )
    bridge.conn.commit()
    return bridge


def test_put_uses_project(pg):
    pg.knowledge_put({"id": "ns_test_1", "project": "willow",
                       "title": "Alpha secret", "summary": "only in willow"})
    results = pg.knowledge_search("Alpha secret", project="willow")
    assert len(results) == 1


def test_search_scoped_to_project(pg):
    pg.knowledge_put({"id": "ns_test_2", "project": "willow",
                       "title": "willow doc", "summary": "belongs to willow"})
    pg.knowledge_put({"id": "ns_test_3", "project": "saps1",
                       "title": "saps1 doc", "summary": "belongs to saps1"})
    results_a = pg.knowledge_search("doc", project="willow")
    assert all(r["project"] == "willow" for r in results_a)


def test_search_without_project_returns_only_that_project(pg):
    pg.knowledge_put({"id": "ns_test_4", "project": "global",
                       "title": "global doc", "summary": "in global"})
    pg.knowledge_put({"id": "ns_test_5", "project": "willow",
                       "title": "willow doc", "summary": "in willow"})
    results = pg.knowledge_search("doc", project="global")
    assert all(r["project"] == "global" for r in results)


def test_default_project_is_global(pg):
    pg.knowledge_put({"id": "ns_test_6", "title": "no project set",
                       "summary": "should default to global"})
    with pg.conn.cursor() as cur:
        cur.execute("SELECT project FROM knowledge WHERE id = 'ns_test_6'")
        row = cur.fetchone()
    assert row[0] == "global"
