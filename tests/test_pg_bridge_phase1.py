"""
Integration tests for Phase 1 PgBridge additions.
Covers: edges, agents_list_from_db, jeles_atom_get, binder_files_list,
binder_edges_list, binder_edge_update_status, ratifications_list,
hook_registry_list, hook_executions_read, ledger_verify, task_complete,
promote_knowledge_tier.
Requires a live Postgres DB (willow_20_test).
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.pg_bridge import PgBridge, run_migrations


@pytest.fixture(scope="module")
def pg():
    # PgBridge reads WILLOW_PG_DB from env; default to willow_20_test for isolation
    os.environ.setdefault("WILLOW_PG_DB", "willow_20_test")
    b = PgBridge()
    # Ensure migrations have run (test DB schema may predate migration additions)
    run_migrations(b.conn)
    yield b
    b.close()


# ── Edges ─────────────────────────────────────────────────────────────────────

def test_edge_add_and_list(pg):
    from_id  = f"FROM-{pg.gen_id(6)}"
    to_id    = f"TO-{pg.gen_id(6)}"
    result   = pg.edge_add(from_id, to_id, "tests", agent="test")
    assert result.get("status") == "added"

    edges = pg.edge_list(from_id=from_id)
    assert any(e["from_id"] == from_id and e["to_id"] == to_id for e in edges)


def test_edge_add_idempotent(pg):
    from_id = f"IDEM-{pg.gen_id(6)}"
    to_id   = f"IDEM-{pg.gen_id(6)}"
    pg.edge_add(from_id, to_id, "tests")
    r2 = pg.edge_add(from_id, to_id, "tests")
    assert "error" not in r2


def test_edge_list_by_to_id(pg):
    to_id  = f"TARG-{pg.gen_id(6)}"
    pg.edge_add(f"SRC1-{pg.gen_id(4)}", to_id, "points_at")
    pg.edge_add(f"SRC2-{pg.gen_id(4)}", to_id, "points_at")
    edges = pg.edge_list(to_id=to_id)
    assert len(edges) >= 2


# ── Agents registry ───────────────────────────────────────────────────────────

def test_agents_list_from_db(pg):
    pg.agent_create("test_phase1_agent", trust="WORKER", role="integration test")
    agents = pg.agents_list_from_db()
    assert isinstance(agents, list)
    assert any(a["name"] == "test_phase1_agent" for a in agents)


# ── Jeles atom get ────────────────────────────────────────────────────────────

def test_jeles_atom_get(pg):
    # Insert directly to bypass the Jeles gate (gate is a quality filter, not the
    # method under test here — we're testing jeles_atom_get read path).
    atom_id = pg.gen_id(8)
    reg     = pg.jeles_register_jsonl("test", "/tmp/phase1.jsonl", f"sess-{pg.gen_id(6)}")
    with pg.conn.cursor() as cur:
        cur.execute(
            "INSERT INTO jeles_atoms (id, jsonl_id, agent, content, title) "
            "VALUES (%s, %s, 'test', 'Phase 1 integration atom', 'Phase1 Test')",
            (atom_id, reg["id"]),
        )
    pg.conn.commit()

    fetched = pg.jeles_atom_get(atom_id)
    assert fetched is not None
    assert fetched["id"] == atom_id
    assert fetched["title"] == "Phase1 Test"


def test_jeles_atom_get_missing(pg):
    assert pg.jeles_atom_get("NOTEXIST-XYZ") is None


# ── Binder reads ──────────────────────────────────────────────────────────────

def test_binder_files_list(pg):
    pg.binder_file("test", f"jsonl-{pg.gen_id(6)}", "/tmp/binder_test")
    files = pg.binder_files_list(agent="test")
    assert len(files) >= 1


def test_binder_edges_list_and_update(pg):
    src = f"ATOM-{pg.gen_id(6)}"
    tgt = f"ATOM-{pg.gen_id(6)}"
    pg.binder_propose_edge("test", src, tgt, "relates_to")

    edges = pg.binder_edges_list(agent="test")
    assert any(e["source_atom"] == src for e in edges)

    edge_id = next(e["id"] for e in edges if e["source_atom"] == src)
    result  = pg.binder_edge_update_status(edge_id, "approved")
    assert result["updated"] is True

    approved = pg.binder_edges_list(status="approved")
    assert any(e["id"] == edge_id for e in approved)


# ── Ratifications ─────────────────────────────────────────────────────────────

def test_ratifications_list(pg):
    jid = f"jsonl-rat-{pg.gen_id(6)}"
    pg.ratify("test", jid, approve=True)
    rows = pg.ratifications_list(agent="test")
    assert any(r["jsonl_id"] == jid for r in rows)


# ── Hook registry ─────────────────────────────────────────────────────────────

def test_hook_registry_list_returns_list(pg):
    rows = pg.hook_registry_list(active_only=False)
    assert isinstance(rows, list)


def test_hook_executions_read_returns_list(pg):
    rows = pg.hook_executions_read(limit=5)
    assert isinstance(rows, list)


# ── Ledger verify ─────────────────────────────────────────────────────────────

def test_ledger_verify_clean_chain(pg):
    pg.ledger_append("test_phase1", "smoke_test", {"run": "phase1"})
    result = pg.ledger_verify()
    assert result["valid"] is True
    assert result["count"] >= 1


# ── Task complete ─────────────────────────────────────────────────────────────

def test_task_complete(pg):
    task_id = pg.submit_task("echo phase1 test", submitted_by="test", agent="test")
    assert task_id is not None
    # pending_tasks() atomically claims the task (pending → running) before we can complete it
    claimed = pg.pending_tasks(agent="test", limit=10)
    assert any(t["id"] == task_id for t in claimed), "task was not claimed by pending_tasks"
    ok = pg.task_complete(task_id, {"stdout": "phase1 test"}, "completed")
    assert ok is True
    row = pg.task_status(task_id)
    assert row["status"] == "completed"


# ── Promote knowledge tier ────────────────────────────────────────────────────

def test_promote_knowledge_tier(pg):
    atom_id = pg.ingest_atom(
        "Phase1 Tier Test", "summary for tier promotion",
        tier="frontier", confidence=0.80,
    )
    assert atom_id is not None
    result = pg.promote_knowledge_tier(atom_id, "contested")
    assert result.get("promoted") is True
    row = pg.knowledge_get(atom_id)
    assert row["tier"] == "contested"
