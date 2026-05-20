"""Tests for sap.core.memory_gate.check_candidate.

b17: 559B3
ΔΣ=42
"""

from __future__ import annotations

import json


from sap.core.memory_gate import check_candidate


class _FakePg:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def knowledge_search(self, query: str, project=None, limit=20, include_invalid=False):
        del query, limit, include_invalid
        if project:
            return [r for r in self._rows if r.get("project") == project]
        return list(self._rows)


class _FakeStore:
    def __init__(self, hits: list[dict]) -> None:
        self._hits = hits

    def search(self, collection: str, query: str, after=None):
        del collection, after
        tokens = query.lower().split()
        out = []
        for h in self._hits:
            blob = json.dumps(h).lower()
            if tokens and all(t in blob for t in tokens):
                out.append(h)
        return out


def test_redundant_exact_title_kb():
    pg = _FakePg(
        [
            {"id": "AAA", "title": "Same Title", "summary": "older body", "project": "hanuman"},
        ]
    )
    out = check_candidate(
        title="Same Title",
        summary="new",
        domain="hanuman",
        store=None,
        pg=pg,
        collection="hanuman/atoms",
    )
    assert "REDUNDANT" in out["flags"]
    assert "duplicate" in out["recommendation"].lower()


def test_no_pg_no_store_clean():
    out = check_candidate(
        title="Unique XYZ Title",
        summary="hello",
        domain=None,
        store=None,
        pg=None,
        collection="hanuman/atoms",
    )
    assert out["flags"] == []
    assert "reasonable" in out["recommendation"].lower()


def test_dark_flag_on_protected_phrase():
    out = check_candidate(
        title="Note",
        summary="identity protection required for F.",
        domain=None,
        store=None,
        pg=None,
        collection="hanuman/atoms",
    )
    assert "DARK" in out["flags"]


def test_soil_redundant():
    store = _FakeStore([{"id": "f1", "title": "Pinned", "summary": "x"}])
    out = check_candidate(
        title="Pinned",
        summary="y",
        domain=None,
        store=store,
        pg=_FakePg([]),
        collection="hanuman/atoms",
    )
    assert "REDUNDANT" in out["flags"]
