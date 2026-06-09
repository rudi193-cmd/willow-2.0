"""tests/test_human_gate.py"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.human_required import check_write_gate
from core.pg_bridge import PgBridge, run_migrations


@pytest.fixture()
def pg(monkeypatch):
    monkeypatch.setenv("WILLOW_PG_DB", "willow_20_test")
    monkeypatch.setenv("WILLOW_HUMAN_GATE", "enforce")
    bridge = PgBridge()
    run_migrations(bridge.conn)
    yield bridge
    bridge.close()


def test_edge_add_blocked_without_consent(pg):
    from_id = f"GATE-FROM-{pg.gen_id(4)}"
    to_id = f"GATE-TO-{pg.gen_id(4)}"
    blocked = pg.edge_add(from_id, to_id, "tests", agent="test")
    assert blocked.get("error") == "human_gate_blocked"
    assert blocked.get("required") == "consent"

    allowed = pg.edge_add(from_id, to_id, "tests", agent="test", human_consent=True)
    assert allowed.get("status") == "added"


def test_promote_elevated_blocked_without_attestation(pg):
    atom_id = pg.gen_id(8)
    with pg.conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO knowledge (id, project, title, summary, source_type, content, tier)
            VALUES (%s, 'test', 'gate atom', 'summary', 'mcp', '{}', 'frontier')
            """,
            (atom_id,),
        )
    pg.conn.commit()

    blocked = pg.promote_knowledge_tier(atom_id, "canonical", agent="test")
    assert blocked.get("error") == "human_gate_blocked"
    assert blocked.get("required") == "attestation"

    allowed = pg.promote_knowledge_tier(
        atom_id, "canonical", agent="test", human_attestation=True
    )
    assert allowed.get("promoted") is True


def test_check_write_gate_warn_mode(pg, monkeypatch):
    monkeypatch.setenv("WILLOW_HUMAN_GATE", "warn")
    gate = check_write_gate(pg.conn, "edge_write", consent=False)
    assert gate.get("allowed") is True
    assert gate.get("warning")
