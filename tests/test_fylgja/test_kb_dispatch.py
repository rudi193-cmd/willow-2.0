"""Direct kb_search dispatch in the hook MCP client.

Regression guard for #628/#629: kb_search used to fall through to
_subprocess_call, which shells to a willow-mcp binary that doesn't exist —
every caller (sandbox/stone_soup, sandbox/rh_harness) silently degraded or,
for harnesses with no fallback of their own, silently returned nothing
(rh_harness's compare.py reported false PASS on empty-vs-empty). These tests
pin that kb_search now dispatches directly to PgBridge, with the same
lane-scope security and taint tagging as sap_mcp.py's real kb_search tool.
"""
import os
from unittest.mock import patch

os.environ.setdefault("WILLOW_AGENT_NAME", "hanuman")

import willow.fylgja._mcp as mcp


class _FakePg:
    def __init__(self, knowledge=None, jeles=None, opus=None):
        self._knowledge = knowledge if knowledge is not None else [
            {"id": "K1", "title": "hit", "project": "willow"},
        ]
        self._jeles = jeles if jeles is not None else []
        self._opus = opus if opus is not None else []
        self.promoted: list[str] = []

    def knowledge_search_semantic(self, query, **kw):
        return list(self._knowledge)

    def knowledge_search(self, query, **kw):
        return list(self._knowledge)

    def search_jeles_semantic(self, query, **kw):
        return list(self._jeles)

    def jeles_keyword_search(self, query, **kw):
        return list(self._jeles)

    def search_opus_semantic(self, query, **kw):
        return list(self._opus)

    def search_opus(self, query, **kw):
        return list(self._opus)

    def knowledge_expand_neighbors(self, seed_ids, **kw):
        return []

    def promote(self, atom_id):
        self.promoted.append(atom_id)


def test_kb_search_dispatches_direct_no_subprocess():
    fake = _FakePg()

    def _boom(*a, **k):
        raise AssertionError("subprocess fallback must not run for kb_search")

    with patch.object(mcp, "_get_pg", lambda: fake):
        with patch.object(mcp, "_subprocess_call", _boom):
            resp = mcp.call("kb_search", {
                "app_id": "hanuman",
                "query": "test query",
                "limit": 5,
            })

    assert resp.get("error") is None
    assert resp["total"] == 1
    assert resp["knowledge"][0]["id"] == "K1"
    assert "taint" in resp
    assert "lane_scope" in resp


def test_kb_search_no_pg_returns_error():
    with patch.object(mcp, "_get_pg", lambda: None):
        resp = mcp.call("kb_search", {"app_id": "hanuman", "query": "x"})
    assert resp["error"] == "pg_unavailable"


def test_kb_search_promotes_relevance_gated_hits():
    fake = _FakePg(knowledge=[{"id": "K1", "project": "willow", "_cosine_sim": 0.9}])
    with patch.object(mcp, "_get_pg", lambda: fake):
        with patch.dict(os.environ, {"WILLOW_PROMOTE_MODE": "relgate", "WILLOW_PROMOTE_RELGATE_FLOOR": "0.5"}):
            mcp.call("kb_search", {"app_id": "hanuman", "query": "x", "semantic": True})
    assert fake.promoted == ["K1"]


def test_kb_search_tags_jeles_and_opus_tables():
    fake = _FakePg(
        knowledge=[],
        jeles=[{"id": "J1", "project": "willow"}],
        opus=[{"id": "O1", "project": "willow"}],
    )
    with patch.object(mcp, "_get_pg", lambda: fake):
        resp = mcp.call("kb_search", {"app_id": "hanuman", "query": "x"})
    assert resp["jeles_atoms"][0]["_table"] == "jeles_atoms"
    assert resp["opus_atoms"][0]["_table"] == "opus_atoms"
