"""tests/test_human_required.py"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.human_required import enqueue, list_items, resolve, seed_defaults, stats
from core.pg_bridge import PgBridge, run_migrations


@pytest.fixture(scope="module")
def pg():
    os.environ.setdefault("WILLOW_PG_DB", "willow_20_test")
    bridge = PgBridge()
    run_migrations(bridge.conn)
    yield bridge
    bridge.close()


def test_enqueue_list_resolve(pg):
    title = f"test human queue {pg.gen_id(6)}"
    source_ref = f"test-{pg.gen_id(6)}"
    added = enqueue(
        pg.conn,
        kind="needs_review",
        title=title,
        summary="integration test",
        priority="normal",
        source_agent="test",
        source_ref=source_ref,
    )
    assert added["status"] == "added"
    item_id = added["id"]

    dup = enqueue(
        pg.conn,
        kind="needs_review",
        title=title,
        summary="duplicate",
        source_ref=source_ref,
    )
    assert dup["status"] == "duplicate"

    rows = list_items(pg.conn, status="open", kind="needs_review", limit=50)
    assert any(r["id"] == item_id for r in rows)

    closed = resolve(pg.conn, item_id, resolved_by="test", status="resolved", note="done")
    assert closed["updated"] is True

    summary = stats(pg.conn)
    assert "open_total" in summary


def test_seed_defaults_idempotent(pg):
    first = seed_defaults(pg.conn)
    second = seed_defaults(pg.conn)
    assert first["attempted"] == second["attempted"]
    assert second["duplicates"] >= first["added"]
