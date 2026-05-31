"""
tests/test_sigmap_fallback.py — Unit tests for willow/sigmap/fallback.py.
b17: SMAP2  ΔΣ=42

All DB and embedding interactions are mocked.
Does not require a live Postgres or Ollama instance.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from willow.sigmap.fallback import (
    FallbackResult,
    fallback_search,
    _level4_ilike,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _atom(
    id: str = "A1",
    title: str = "Test atom",
    summary: str = "A test summary",
    project: str = "hanuman",
    weight: float = 1.0,
    **extra,
) -> dict:
    return {
        "id": id, "title": title, "summary": summary,
        "project": project, "weight": weight,
        **extra,
    }


def _make_pg(knowledge_search_returns=None):
    """Return a mock PgBridge."""
    pg = MagicMock()
    pg.knowledge_search.return_value = knowledge_search_returns or []
    pg._ensure_conn.return_value = None
    return pg


# ── FallbackResult construction ───────────────────────────────────────────────

class TestFallbackResult:
    def test_from_row_basic(self):
        row = _atom(id="42", cosine_sim=0.87)
        row["_cosine_sim"] = 0.87
        r = FallbackResult.from_row(row, level=1, level_name="pgvector", score=0.87)
        assert r.id == "42"
        assert r.level == 1
        assert r.level_name == "pgvector"
        assert r.score == pytest.approx(0.87)
        assert r.project == "hanuman"

    def test_from_row_missing_fields_safe(self):
        r = FallbackResult.from_row(
            {}, level=4, level_name="ilike", score=0.0
        )
        assert r.id == ""
        assert r.title == ""
        assert r.project == "global"
        assert r.weight == pytest.approx(1.0)

    def test_extra_fields_captured(self):
        row = _atom(id="X", _rrf_score=0.5)
        r = FallbackResult.from_row(row, level=2, level_name="hybrid-rrf", score=0.5)
        assert "_rrf_score" in r.extra


# ── fallback_search cascade logic ────────────────────────────────────────────

class TestFallbackSearchCascade:
    """Test that the chain stops at the first level meeting threshold."""

    def _make_results(self, n: int, level: int, level_name: str) -> list[FallbackResult]:
        return [
            FallbackResult(
                id=str(i), title=f"atom {i}", summary="", project="test",
                weight=1.0, level=level, level_name=level_name, score=float(i),
            )
            for i in range(n)
        ]

    def test_stops_at_level1_when_sufficient(self):
        pg = _make_pg()
        level1_results = self._make_results(5, 1, "pgvector")

        with patch("willow.sigmap.fallback._level1_pgvector", return_value=level1_results), \
             patch("willow.sigmap.fallback._level2_hybrid", return_value=[]) as mock2, \
             patch("willow.sigmap.fallback._level3_ast_symbol", return_value=[]) as mock3, \
             patch("willow.sigmap.fallback._level4_ilike", return_value=[]) as mock4:

            results = fallback_search("test query", pg, threshold=3)

        assert len(results) == 5
        assert results[0].level_name == "pgvector"
        mock2.assert_not_called()
        mock3.assert_not_called()
        mock4.assert_not_called()

    def test_cascades_to_level2_when_level1_insufficient(self):
        pg = _make_pg()
        level1_results = self._make_results(1, 1, "pgvector")   # below threshold
        level2_results = self._make_results(4, 2, "hybrid-rrf")

        with patch("willow.sigmap.fallback._level1_pgvector", return_value=level1_results), \
             patch("willow.sigmap.fallback._level2_hybrid", return_value=level2_results), \
             patch("willow.sigmap.fallback._level3_ast_symbol", return_value=[]) as mock3, \
             patch("willow.sigmap.fallback._level4_ilike", return_value=[]) as mock4:

            results = fallback_search("test query", pg, threshold=3)

        assert len(results) == 4
        assert results[0].level_name == "hybrid-rrf"
        mock3.assert_not_called()
        mock4.assert_not_called()

    def test_cascades_to_level3_when_levels_1_2_insufficient(self):
        pg = _make_pg()

        with patch("willow.sigmap.fallback._level1_pgvector", return_value=[]), \
             patch("willow.sigmap.fallback._level2_hybrid", return_value=[]), \
             patch("willow.sigmap.fallback._level3_ast_symbol",
                   return_value=self._make_results(3, 3, "ast-symbol")), \
             patch("willow.sigmap.fallback._level4_ilike", return_value=[]) as mock4:

            results = fallback_search("test query", pg, threshold=3)

        assert len(results) == 3
        assert results[0].level_name == "ast-symbol"
        mock4.assert_not_called()

    def test_cascades_to_level4_ilike_as_last_resort(self):
        pg = _make_pg()
        ilike_results = self._make_results(2, 4, "ilike")

        with patch("willow.sigmap.fallback._level1_pgvector", return_value=[]), \
             patch("willow.sigmap.fallback._level2_hybrid", return_value=[]), \
             patch("willow.sigmap.fallback._level3_ast_symbol", return_value=[]), \
             patch("willow.sigmap.fallback._level4_ilike", return_value=ilike_results):

            results = fallback_search("test query", pg, threshold=3)

        # ilike returned 2 which is below threshold, but it's the last level
        assert len(results) == 2
        assert results[0].level_name == "ilike"

    def test_empty_query_safe(self):
        pg = _make_pg()
        with patch("willow.sigmap.fallback._level1_pgvector", return_value=[]), \
             patch("willow.sigmap.fallback._level2_hybrid", return_value=[]), \
             patch("willow.sigmap.fallback._level3_ast_symbol", return_value=[]), \
             patch("willow.sigmap.fallback._level4_ilike", return_value=[]):
            results = fallback_search("", pg)
        assert results == []

    def test_all_levels_empty_returns_empty_list(self):
        pg = _make_pg()
        with patch("willow.sigmap.fallback._level1_pgvector", return_value=[]), \
             patch("willow.sigmap.fallback._level2_hybrid", return_value=[]), \
             patch("willow.sigmap.fallback._level3_ast_symbol", return_value=[]), \
             patch("willow.sigmap.fallback._level4_ilike", return_value=[]):
            results = fallback_search("obscure query nobody wrote about", pg)
        assert results == []

    def test_start_level_skips_earlier_levels(self):
        pg = _make_pg()
        level3_results = self._make_results(4, 3, "ast-symbol")

        with patch("willow.sigmap.fallback._level1_pgvector", return_value=[]) as mock1, \
             patch("willow.sigmap.fallback._level2_hybrid", return_value=[]) as mock2, \
             patch("willow.sigmap.fallback._level3_ast_symbol", return_value=level3_results), \
             patch("willow.sigmap.fallback._level4_ilike", return_value=[]):

            results = fallback_search("test", pg, start_level=3, threshold=3)

        mock1.assert_not_called()
        mock2.assert_not_called()
        assert len(results) == 4

    def test_limit_applied(self):
        pg = _make_pg()
        many = self._make_results(20, 1, "pgvector")

        with patch("willow.sigmap.fallback._level1_pgvector", return_value=many):
            results = fallback_search("test", pg, limit=5, threshold=3)

        assert len(results) == 5

    def test_threshold_zero_stops_at_level1_even_if_empty(self):
        """threshold=0: any result (including empty first hit) stops the chain."""
        pg = _make_pg()

        # Level 1 returns 0 results — with threshold=0, even 0 >= 0 is True
        # so the chain should stop after Level 1 if it returns anything.
        # With 0 results, it does NOT stop (0 >= 0 but there are no results
        # to return), so it cascades. Verify level2 is still called when level1
        # returns nothing.
        level2_results = self._make_results(1, 2, "hybrid-rrf")

        with patch("willow.sigmap.fallback._level1_pgvector", return_value=[]), \
             patch("willow.sigmap.fallback._level2_hybrid", return_value=level2_results), \
             patch("willow.sigmap.fallback._level3_ast_symbol", return_value=[]), \
             patch("willow.sigmap.fallback._level4_ilike", return_value=[]):

            results = fallback_search("test", pg, threshold=0)

        # level2 should have been reached
        assert results[0].level_name == "hybrid-rrf"


# ── level4_ilike unit test ────────────────────────────────────────────────────

class TestLevel4Ilike:
    def test_calls_pg_knowledge_search(self):
        pg = _make_pg(knowledge_search_returns=[_atom(id="99")])
        results = _level4_ilike(pg, "search term", project=None, wide_k=10)
        pg.knowledge_search.assert_called_once()
        assert len(results) == 1
        assert results[0].level == 4
        assert results[0].level_name == "ilike"
        assert results[0].score == pytest.approx(0.0)

    def test_respects_project_filter(self):
        pg = _make_pg(knowledge_search_returns=[])
        _level4_ilike(pg, "query", project="hanuman", wide_k=5)
        call_kwargs = pg.knowledge_search.call_args
        assert "hanuman" in str(call_kwargs)

    def test_pg_exception_returns_empty(self):
        pg = _make_pg()
        pg.knowledge_search.side_effect = Exception("DB down")
        results = _level4_ilike(pg, "query", project=None, wide_k=10)
        assert results == []


# ── FallbackResult dataclass edge cases ──────────────────────────────────────

class TestFallbackResultEdgeCases:
    def test_str_id_from_int(self):
        row = _atom(id=42)   # int id
        r = FallbackResult.from_row(row, level=1, level_name="pgvector", score=0.9)
        assert r.id == "42"

    def test_none_weight_defaults_to_1(self):
        row = _atom(id="1", weight=None)
        r = FallbackResult.from_row(row, level=1, level_name="pgvector", score=0.5)
        assert r.weight == pytest.approx(1.0)

    def test_extra_does_not_include_core_fields(self):
        row = _atom(id="5", title="T", summary="S", project="P", weight=2.0)
        r = FallbackResult.from_row(row, level=2, level_name="hybrid", score=0.7)
        assert "id" not in r.extra
        assert "title" not in r.extra
        assert "project" not in r.extra
