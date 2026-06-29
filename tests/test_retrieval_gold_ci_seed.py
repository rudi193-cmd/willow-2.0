"""CI retrieval gold seed — idempotent fixture for willow_20_test."""
from __future__ import annotations

import pytest

from core.pg_bridge import PgBridge, try_connect
from willow.bench.retrieval_gold_ci import CI_GOLD_PATH, load_ci_fixture, run_ci_gold_set, seed_ci_gold


def test_ci_fixture_loads():
    fixture = load_ci_fixture()
    assert len(fixture.get("seed_atoms") or []) >= 7
    assert len(fixture.get("queries") or []) >= 7
    assert fixture["min_pass_ratio"] == 1.0


@pytest.mark.slow
def test_seed_ci_gold_idempotent():
    if try_connect() is None:
        pytest.skip("Postgres unavailable")
    pg = PgBridge()
    try:
        first = seed_ci_gold(pg, path=CI_GOLD_PATH)
        second = seed_ci_gold(pg, path=CI_GOLD_PATH)
        assert first >= 7
        assert second >= 7
        report = run_ci_gold_set(pg, path=CI_GOLD_PATH)
        assert report["pass"], report
        assert report["ratio"] == 1.0
    finally:
        pg.close()
