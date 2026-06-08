"""Live Postgres gold-query gate for hybrid retrieval."""
from __future__ import annotations

import pytest

from core.pg_bridge import PgBridge, try_connect
from willow.bench.retrieval_gold import GoldQuery, hit_rank, load_gold_queries


def test_gold_query_fixture_loads():
    queries, min_pass_ratio = load_gold_queries()
    assert len(queries) >= 7
    assert 0 < min_pass_ratio <= 1


def test_hit_rank_matches_id_or_title_fragment():
    query = GoldQuery(
        id="sample",
        query="binder edges",
        expect_ids=("ABC123",),
        expect_title_contains=("public.edges",),
        k=3,
        semantic=True,
    )
    assert hit_rank([{"id": "ZZZ", "title": "other"}], query) is None
    assert hit_rank([{"id": "ABC123", "title": "x"}], query) == 1
    assert hit_rank(
        [{"id": "ZZZ", "title": "Binder edges sync to public.edges"}],
        query,
    ) == 1


@pytest.mark.slow
def test_retrieval_gold_set_meets_gate():
    if try_connect() is None:
        pytest.skip("Postgres unavailable")
    pg = PgBridge()
    try:
        from willow.bench.retrieval_gold import run_gold_set

        report = run_gold_set(pg)
    finally:
        pg.close()
    assert report["total"] >= 7
    assert report["pass"], report
