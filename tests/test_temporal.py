"""
# b17: W19TR  ΔΣ=42
Tests for W19TR — Temporal Replay.
"""
import os
from datetime import datetime, timezone, timedelta

os.environ.setdefault("WILLOW_PG_DB", "willow_20")


def test_knowledge_at_finds_valid_atom():
    from core.pg_bridge import PgBridge
    bridge = PgBridge()
    now = datetime.now(timezone.utc)
    past = now - timedelta(days=10)

    bridge.knowledge_put({
        "id": "tr_test_open",
        "project": "willow",
        "title": "temporal replay test open",
        "summary": "this atom is still valid",
        "valid_at": past,
    })
    results = bridge.knowledge_at("temporal replay test open", at_time=now)
    ids = [r["id"] for r in results]
    assert "tr_test_open" in ids

    with bridge.conn.cursor() as cur:
        cur.execute("DELETE FROM knowledge WHERE id = 'tr_test_open'")
    bridge.conn.commit()


def test_knowledge_at_excludes_closed_atom():
    from core.pg_bridge import PgBridge
    bridge = PgBridge()
    now = datetime.now(timezone.utc)
    opened = now - timedelta(days=20)
    closed_at = now - timedelta(days=5)

    bridge.knowledge_put({
        "id": "tr_test_closed",
        "project": "willow",
        "title": "temporal replay test closed",
        "summary": "this atom was closed",
        "valid_at": opened,
    })
    bridge.knowledge_close("tr_test_closed", closed_at)

    # Query at closed_at - 1 hour: should find it
    before_close = closed_at - timedelta(hours=1)
    results = bridge.knowledge_at("temporal replay test closed", at_time=before_close)
    assert any(r["id"] == "tr_test_closed" for r in results)

    # Query now (after close): should NOT find it
    results = bridge.knowledge_at("temporal replay test closed", at_time=now)
    assert not any(r["id"] == "tr_test_closed" for r in results)

    with bridge.conn.cursor() as cur:
        cur.execute("DELETE FROM knowledge WHERE id = 'tr_test_open'")
    bridge.conn.commit()


def test_knowledge_at_project_filter():
    from core.pg_bridge import PgBridge
    bridge = PgBridge()
    now = datetime.now(timezone.utc)

    bridge.knowledge_put({
        "id": "tr_proj_a",
        "project": "willow",
        "title": "project filter atom alpha",
        "summary": "in project a",
    })
    bridge.knowledge_put({
        "id": "tr_proj_b",
        "project": "saps1",
        "title": "project filter atom alpha",
        "summary": "in project b",
    })
    results = bridge.knowledge_at("project filter atom alpha", at_time=now, project="willow")
    ids = [r["id"] for r in results]
    assert "tr_proj_a" in ids
    assert "tr_proj_b" not in ids

    with bridge.conn.cursor() as cur:
        cur.execute("DELETE FROM knowledge WHERE id IN ('tr_proj_a', 'tr_proj_b')")
    bridge.conn.commit()
