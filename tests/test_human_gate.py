"""tests/test_human_gate.py"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.human_attestation import create as create_attestation, list_records
from core.human_required import check_write_gate, enqueue, operator_load_state
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
    attestations = pg.human_attestation_list(subject_id=atom_id)
    assert attestations
    assert attestations[0]["subject_id"] == atom_id
    assert attestations[0]["status"] == "attested"


def test_check_write_gate_warn_mode(pg, monkeypatch):
    monkeypatch.setenv("WILLOW_HUMAN_GATE", "warn")
    gate = check_write_gate(pg.conn, "edge_write", consent=False)
    assert gate.get("allowed") is True
    assert gate.get("warning")


def test_operator_load_state_high_with_unassigned_high_item(pg):
    enqueue(
        pg.conn,
        kind="operator_overload",
        title="operator overloaded in test",
        summary="High-priority operator decision load should alter routing.",
        priority="high",
        source_ref=f"load-{pg.gen_id(4)}",
        source_agent="test",
    )

    state = operator_load_state(pg.conn)
    assert state["level"] == "high"
    assert state["routing"] == "defer_optional_decisions"
    assert state["high_unassigned"] >= 1


def test_human_attestation_create_and_list(pg):
    subject_id = f"ATT-{pg.gen_id(4)}"
    created = create_attestation(
        pg.conn,
        subject_id=subject_id,
        subject_type="edge",
        attested_by="sean",
        agent="test",
        statement="Reviewed edge evidence and attested it.",
        evidence_ref="test:evidence",
    )
    assert created["subject_id"] == subject_id

    rows = list_records(pg.conn, subject_id=subject_id, subject_type="edge")
    assert len(rows) == 1
    assert rows[0]["attested_by"] == "sean"
