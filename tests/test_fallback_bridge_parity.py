"""Fallback-bridge read-lane parity with PgBridge.

Regression tests for the 2026-07-04 claude-science bug report
(~/Desktop/Nest/willow_mcp_bug_report.md): every kb/jeles/cmb read tool
crashed in the sqlite snapshot lane because SqliteBridge methods were
missing or had narrower signatures than PgBridge, and sap_mcp passes
arguments positionally via run_in_executor.

Two layers:
1. Signature parity — for the read-lane surface sap_mcp calls on
   whichever bridge is live, every PgBridge parameter must exist on the
   fallback in the same position. This is the exact failure class the
   report documents (kb_get: "takes from 2 to 5 positional arguments
   but 6 were given").
2. Functional — each method runs against a real temp sqlite DB with the
   full argument shape sap_mcp uses and returns the seeded rows.
"""
import inspect

import pytest

from core.graceful import DegradedBridge
from core.sqlite_bridge import SqliteBridge

# Read-lane methods sap_mcp calls on the active bridge (kb_search, kb_get,
# kb_at, mem_jeles_search, willow_find, cmb_get/list/search, opus search).
READ_LANE_METHODS = [
    "knowledge_search",
    "knowledge_get",
    "knowledge_at",
    "jeles_keyword_search",
    "search_jeles_semantic",
    "cmb_get",
    "cmb_list",
    "cmb_search",
    "search_opus",
]


def _pg_bridge_cls():
    pg_bridge = pytest.importorskip("core.pg_bridge")
    return pg_bridge.PgBridge


@pytest.mark.parametrize("method", READ_LANE_METHODS)
def test_sqlite_bridge_signature_parity(method):
    pg_fn = getattr(_pg_bridge_cls(), method)
    sq_fn = getattr(SqliteBridge, method, None)
    assert sq_fn is not None, f"SqliteBridge missing read-lane method {method}"
    pg_params = list(inspect.signature(pg_fn).parameters)
    sq_params = list(inspect.signature(sq_fn).parameters)
    # Positional order must match exactly for the pg prefix: sap_mcp calls
    # via run_in_executor with positional args, so a fallback param that is
    # missing or in a different slot TypeErrors at call time.
    assert sq_params[: len(pg_params)] == pg_params, (
        f"{method}: SqliteBridge params {sq_params} do not start with "
        f"PgBridge params {pg_params}"
    )


def test_degraded_bridge_knowledge_get_accepts_lane_scope():
    pg_params = list(
        inspect.signature(_pg_bridge_cls().knowledge_get).parameters
    )
    dg_params = list(inspect.signature(DegradedBridge.knowledge_get).parameters)
    assert dg_params[: len(pg_params)] == pg_params


# ── Functional: real temp DB, sap_mcp-shaped calls ─────────────────────────────


@pytest.fixture
def db(tmp_path):
    bridge = SqliteBridge(path=tmp_path / "parity.db")
    yield bridge
    bridge.close()


def test_knowledge_get_positional_call_shape(db):
    # Exact call shape of sap_mcp kb_get: five positional args after self.
    db.knowledge_put({"id": "KGET1", "title": "atom", "summary": "s"})
    atom = db.knowledge_get("KGET1", False, False, None, None)
    assert atom is not None and atom["id"] == "KGET1"


def test_knowledge_at_accepts_lane_scope(db):
    from datetime import datetime, timezone

    db.knowledge_put({"id": "KAT1", "title": "temporal atom", "summary": "s"})
    rows = db.knowledge_at(
        "temporal", datetime.now(timezone.utc), None, 20, None
    )
    assert any(r["id"] == "KAT1" for r in rows)


def test_jeles_keyword_search_returns_seeded_atom(db):
    db.jeles_extract_atom("willow", "J1", "quantum entanglement notes",
                          title="quantum")
    rows = db.jeles_keyword_search("quantum", limit=20,
                                   include_sensitive=False)
    assert rows and "quantum" in (rows[0]["title"] or rows[0]["content"])


def test_search_jeles_semantic_degrades_to_keyword(db):
    db.jeles_extract_atom("willow", "J2", "genomics pipeline findings",
                          title="genomics")
    rows = db.search_jeles_semantic("genomics", limit=20, days_ago=None,
                                    include_sensitive=False)
    assert rows and "genomics" in (rows[0]["title"] or rows[0]["content"])
    # days_ago window: a fresh atom survives a 7-day window
    rows = db.search_jeles_semantic("genomics", limit=20, days_ago=7,
                                    include_sensitive=False)
    assert rows


def test_cmb_get_list_search_roundtrip(db):
    db.cmb_put("CMB01", {"entry": "cosmic background note", "domain": "meta"})
    atom = db.cmb_get("CMB01")
    assert atom is not None and atom["content"]["entry"] == "cosmic background note"
    assert db.cmb_get("MISSING") is None
    listed = db.cmb_list(None, 20)
    assert any(r["id"] == "CMB01" for r in listed)
    found = db.cmb_search("cosmic", 20)
    assert any(r["id"] == "CMB01" for r in found)


def test_search_opus_accepts_include_sensitive(db):
    db.ingest_opus_atom("opus parity content", agent="willow")
    rows = db.search_opus("parity", 20, False)
    assert rows and "parity" in rows[0]["content"]
