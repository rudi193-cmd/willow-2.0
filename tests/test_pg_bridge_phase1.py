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

from core.pg_bridge import PgBridge

# Session conftest init_pg_schema + PgBridge pool boot already apply migrations.
pytestmark = pytest.mark.timeout(180)


@pytest.fixture(scope="module")
def pg():
    # PgBridge reads WILLOW_PG_DB from env; default to willow_20_test for isolation
    os.environ.setdefault("WILLOW_PG_DB", "willow_20_test")
    b = PgBridge()
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
    assert result.get("postgres_edge", {}).get("status") == "added"

    pg_edges = pg.edge_list(from_id=src)
    assert any(e["to_id"] == tgt for e in pg_edges)

    approved = pg.binder_edges_list(status="approved")
    assert any(e["id"] == edge_id for e in approved)


def test_knowledge_search_excludes_search_noise(pg):
    noisy_id = pg.ingest_atom(
        title="benchmark noise atom",
        summary="revelation benchmark fixture",
        source_type="test",
        category="benchmark",
    )
    with pg.conn.cursor() as cur:
        cur.execute(
            "UPDATE knowledge SET content = content || '{\"search_noise\": true}'::jsonb WHERE id = %s",
            (noisy_id,),
        )
    pg.conn.commit()
    hits = pg.knowledge_search("benchmark noise atom", limit=10)
    assert not any(h["id"] == noisy_id for h in hits)


def test_knowledge_expand_neighbors(pg):
    a = pg.ingest_atom(title="seed A", summary="neighbor test seed", source_type="test")
    b = pg.ingest_atom(title="seed B", summary="neighbor test target", source_type="test")
    pg.edge_add(a, b, "relates_to", agent="test")
    neighbors = pg.knowledge_expand_neighbors([a], limit=5)
    assert any(n["id"] == b for n in neighbors)


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


# ── Kart queue (Phase 0) ──────────────────────────────────────────────────────

def test_pending_tasks_does_not_claim(pg):
    task_id = pg.submit_task("echo read-only pending", submitted_by="test", agent="test")
    assert task_id is not None
    listed = pg.pending_tasks(agent="test", limit=20)
    assert any(t["id"] == task_id for t in listed)
    row = pg.task_status(task_id)
    assert row["status"] == "pending"
    pg.claim_kart_tasks(agent="test", limit=20)
    pg.task_complete(task_id, {"ok": True}, "completed")


def test_reap_stale_tasks(pg):
    task_id = pg.submit_task("echo stale reap", submitted_by="test", agent="test")
    with pg.conn.cursor() as cur:
        cur.execute(
            """
            UPDATE tasks
            SET status = 'running', updated_at = now() - interval '2 hours'
            WHERE id = %s
            """,
            (task_id,),
        )
    pg.conn.commit()
    reaped = pg.reap_stale_tasks(max_age_seconds=3600, agent="test")
    assert task_id in reaped
    row = pg.task_status(task_id)
    assert row["status"] == "failed"
    assert row["result"].get("error") == "orphaned_running_reaped"


# ── Task complete ─────────────────────────────────────────────────────────────

def test_task_complete(pg):
    task_id = pg.submit_task("echo phase1 test", submitted_by="test", agent="test")
    assert task_id is not None
    pending = pg.pending_tasks(agent="test", limit=10)
    assert any(t["id"] == task_id for t in pending), "task should appear in read-only pending list"
    claimed = pg.claim_kart_tasks(agent="test", limit=10)
    assert any(t["id"] == task_id for t in claimed), "task was not claimed by claim_kart_tasks"
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
