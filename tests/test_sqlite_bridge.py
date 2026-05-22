"""Tests for SqliteBridge — full API parity with PgBridge."""
import json
import pytest
from core.sqlite_bridge import SqliteBridge


@pytest.fixture
def db(tmp_path):
    bridge = SqliteBridge(path=tmp_path / "test.db")
    yield bridge
    bridge.close()


# ── Stats ──────────────────────────────────────────────────────────────────────

def test_stats_returns_counts(db):
    stats = db.stats()
    assert "knowledge" in stats
    assert stats["knowledge"] == 0


# ── Knowledge ──────────────────────────────────────────────────────────────────

def test_knowledge_put_and_search(db):
    db.knowledge_put({"id": "TEST1", "title": "Willow test atom", "summary": "hello world"})
    results = db.knowledge_search("Willow test")
    assert any(r["id"] == "TEST1" for r in results)


def test_knowledge_put_upsert(db):
    db.knowledge_put({"id": "UP1", "title": "Original", "summary": "v1"})
    db.knowledge_put({"id": "UP1", "title": "Updated", "summary": "v2"})
    results = db.knowledge_search("Updated")
    assert results[0]["title"] == "Updated"


def test_knowledge_put_returns_id(db):
    atom_id = db.knowledge_put({"id": "RET1", "title": "Return test"})
    assert atom_id == "RET1"


def test_ingest_atom(db):
    atom_id = db.ingest_atom("Test title", "Test summary", domain="test")
    assert atom_id is not None
    results = db.knowledge_search("Test title")
    assert any(r["id"] == atom_id for r in results)


def test_knowledge_search_respects_invalid(db):
    db.knowledge_put({"id": "VALID", "title": "Valid atom", "summary": "active"})
    db.knowledge_put({"id": "INVAL", "title": "Invalid atom", "summary": "expired",
                      "invalid_at": "2020-01-01T00:00:00+00:00"})
    results = db.knowledge_search("atom", include_invalid=False)
    ids = [r["id"] for r in results]
    assert "VALID" in ids
    assert "INVAL" not in ids


def test_increment_visit(db):
    db.knowledge_put({"id": "VIS1", "title": "Visit test"})
    db.increment_visit("VIS1")
    from core.sqlite_bridge import _lock
    with _lock:
        cur = db.conn.execute("SELECT visit_count FROM knowledge WHERE id = 'VIS1'")
        count = cur.fetchone()[0]
    assert count == 1


# ── CMB ────────────────────────────────────────────────────────────────────────

def test_cmb_put(db):
    db.cmb_put("CMB1", {"event": "system_birth"})
    with db.conn:
        cur = db.conn.execute("SELECT content FROM cmb_atoms WHERE id = 'CMB1'")
        row = cur.fetchone()
    assert row is not None
    assert json.loads(row[0])["event"] == "system_birth"


def test_cmb_put_idempotent(db):
    db.cmb_put("CMB2", {"event": "first"})
    db.cmb_put("CMB2", {"event": "second"})  # should be ignored
    with db.conn:
        cur = db.conn.execute("SELECT COUNT(*) FROM cmb_atoms WHERE id = 'CMB2'")
        count = cur.fetchone()[0]
    assert count == 1


# ── Tasks ──────────────────────────────────────────────────────────────────────

def test_submit_and_status(db):
    task_id = db.submit_task("run something", submitted_by="test", agent="kart")
    assert task_id is not None
    status = db.task_status(task_id)
    assert status["status"] == "pending"
    assert status["task"] == "run something"


def test_pending_tasks(db):
    db.submit_task("task one", agent="kart")
    db.submit_task("task two", agent="kart")
    pending = db.pending_tasks(agent="kart")
    assert len(pending) >= 2


def test_task_status_not_found(db):
    assert db.task_status("NOTEXIST") is None


# ── Ledger ─────────────────────────────────────────────────────────────────────

def test_ledger_append_and_read(db):
    db.ledger_append("test", "install", {"version": "1.9"})
    entries = db.ledger_read()
    assert len(entries) >= 1
    assert entries[0]["event_type"] == "install"


def test_ledger_verify_valid(db):
    db.ledger_append("test", "event_a", {"x": 1})
    db.ledger_append("test", "event_b", {"x": 2})
    result = db.ledger_verify()
    assert result["valid"] is True
    assert result["count"] == 2


def test_ledger_verify_empty(db):
    result = db.ledger_verify()
    assert result["valid"] is True
    assert result["count"] == 0


# ── JELES ──────────────────────────────────────────────────────────────────────

def test_jeles_register(db):
    result = db.jeles_register_jsonl("hanuman", "/tmp/test.jsonl", "sess-001")
    assert "id" in result
    assert result["status"] == "registered"


# ── Feedback ───────────────────────────────────────────────────────────────────

def test_feedback_write_and_read(db):
    db.opus_feedback_write("test", "Never mock the database")
    feedback = db.opus_feedback(domain="test")
    assert any(f["content"] == "Never mock the database" for f in feedback)


# ── Tier / schema parity (P2.1 + P2.2) ────────────────────────────────────────

def test_ingest_atom_tier_confidence(db):
    atom_id = db.ingest_atom("Tier test", "summary", tier="canonical", confidence=0.95)
    results = db.knowledge_search("Tier test")
    row = next(r for r in results if r["id"] == atom_id)
    assert row["tier"] == "canonical"
    assert row["confidence"] == pytest.approx(0.95)


def test_knowledge_search_tier_filter(db):
    db.ingest_atom("Frontier atom", "f summary", tier="frontier")
    db.ingest_atom("Canonical atom", "c summary", tier="canonical")
    frontier = db.knowledge_search("atom", tier="frontier")
    ids = [r["id"] for r in frontier]
    assert all(db.knowledge_search("atom", tier="frontier")[0]["tier"] == "frontier" for r in frontier)
    canonical = db.knowledge_search("atom", tier="canonical")
    assert all(r["tier"] == "canonical" for r in canonical)


def test_promote_knowledge_tier(db):
    atom_id = db.ingest_atom("Promote me", "summary", tier="frontier")
    result = db.promote_knowledge_tier(atom_id, "canonical")
    assert result["promoted"] is True
    row = db.knowledge_get(atom_id)
    assert row["tier"] == "canonical"


def test_jeles_atom_get(db):
    result = db.jeles_register_jsonl("hanuman", "/tmp/x.jsonl", "sess-xyz")
    db.jeles_extract_atom("hanuman", result["id"], "atom content", title="Test Atom")
    atoms = db._query("SELECT id FROM jeles_atoms LIMIT 1")
    atom_id = atoms[0]["id"]
    fetched = db.jeles_atom_get(atom_id)
    assert fetched is not None
    assert fetched["id"] == atom_id


def test_jeles_invalidate_atom(db):
    db.jeles_register_jsonl("hanuman", "/tmp/y.jsonl", "sess-abc")
    sessions = db._query("SELECT id FROM jeles_sessions LIMIT 1")
    db.jeles_extract_atom("hanuman", sessions[0]["id"], "invalidate me")
    atoms = db._query("SELECT id FROM jeles_atoms ORDER BY created_at DESC LIMIT 1")
    atom_id = atoms[0]["id"]
    result = db.jeles_invalidate_atom(atom_id, "test reason")
    assert result["invalidated"] is True
    row = db.jeles_atom_get(atom_id)
    assert row["invalid_at"] is not None


def test_binder_list_files(db):
    db.binder_file("hanuman", "jsonl-001", "/tmp/dest")
    files = db.binder_files_list(agent="hanuman")
    assert len(files) >= 1


def test_binder_list_and_update_edges(db):
    db.binder_propose_edge("hanuman", "A1", "B1", "relates_to")
    edges = db.binder_edges_list(agent="hanuman")
    assert len(edges) >= 1
    edge_id = edges[0]["id"]
    result = db.binder_edge_update_status(edge_id, "approved")
    assert result["updated"] is True
    updated = db.binder_edges_list(status="approved")
    assert any(e["id"] == edge_id for e in updated)


def test_ratifications_list(db):
    db.ratify("hanuman", "jsonl-ratify", approve=True)
    rows = db.ratifications_list(agent="hanuman")
    assert len(rows) >= 1
    assert rows[0]["agent"] == "hanuman"


def test_agents_list_from_db(db):
    db.agent_create("test_agent", trust="WORKER", role="test")
    agents = db.agents_list_from_db()
    assert any(a["name"] == "test_agent" for a in agents)


# ── Context manager ────────────────────────────────────────────────────────────

def test_context_manager(tmp_path):
    with SqliteBridge(path=tmp_path / "ctx.db") as db:
        db.knowledge_put({"id": "CTX1", "title": "Context test"})
        results = db.knowledge_search("Context test")
        assert len(results) == 1
