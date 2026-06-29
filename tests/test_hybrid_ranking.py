"""
tests/test_hybrid_ranking.py — Unit tests for willow/ranking/hybrid.py.
b17: RANK1  ΔΣ=42

All DB interactions are mocked. Does not require a live Postgres or Ollama.
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch


sys.path.insert(0, str(Path(__file__).parent.parent))

from willow.ranking.hybrid import (
    _tokenize,
    _row_text,
    _build_bm25,
    _bm25_search,
    _rrf_fuse,
    _retrieval_weight_factor,
    _apply_lexical_coverage_bias,
    temporal_rerank,
    hybrid_search,
    bm25_search,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _atom(id: str, title: str = "", summary: str = "",
          weight: float = 1.0, created_at=None) -> dict:
    return {
        "id": id,
        "title": title,
        "summary": summary,
        "weight": weight,
        "created_at": created_at or datetime.now(timezone.utc),
        "project": "global",
        "valid_at": datetime.now(timezone.utc),
        "invalid_at": None,
        "source_type": "test",
        "category": None,
        "visit_count": 0,
        "last_visited": None,
        "fork_id": None,
        "embedding": None,
        "content": None,
    }


def _mock_pg(knowledge_rows: list[dict] | None = None):
    """Return a MagicMock PgBridge that returns given rows for any DB call."""
    pg = MagicMock()
    pg._ensure_conn.return_value = None

    # Mock the cursor context manager
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_cursor.fetchall.return_value = knowledge_rows or []
    pg.conn.cursor.return_value = mock_cursor

    # knowledge_search fallback
    pg.knowledge_search.return_value = knowledge_rows or []

    return pg


# ── Tokenizer ─────────────────────────────────────────────────────────────────

class TestTokenize:
    def test_basic_split(self):
        tokens = _tokenize("hello world")
        assert "hello" in tokens
        assert "world" in tokens

    def test_lowercases(self):
        tokens = _tokenize("Hello WORLD")
        assert "hello" in tokens
        assert "world" in tokens

    def test_drops_short(self):
        tokens = _tokenize("a bb ccc")
        assert "a" not in tokens
        assert "bb" in tokens
        assert "ccc" in tokens

    def test_drops_long(self):
        long_tok = "a" * 31
        tokens = _tokenize(long_tok)
        assert long_tok not in tokens

    def test_empty_string(self):
        assert _tokenize("") == []

    def test_none_like_empty(self):
        # _tokenize("") is the safe call; None is handled by callers via `or ""`
        assert _tokenize("") == []

    def test_strips_punctuation(self):
        tokens = _tokenize("hello, world!")
        assert "hello" in tokens
        assert "world" in tokens

    def test_numbers_kept(self):
        tokens = _tokenize("project123 foo")
        assert "project123" in tokens


# ── Row text extractor ────────────────────────────────────────────────────────

class TestRowText:
    def test_both_fields(self):
        row = {"title": "foo", "summary": "bar"}
        assert "foo" in _row_text(row)
        assert "bar" in _row_text(row)

    def test_missing_summary(self):
        row = {"title": "foo", "summary": None}
        assert _row_text(row) == "foo"

    def test_missing_title(self):
        row = {"title": None, "summary": "bar"}
        assert _row_text(row) == "bar"

    def test_empty_row(self):
        row = {}
        assert _row_text(row) == ""

    def test_content_keywords_are_searchable(self):
        row = {"title": "BKT wiring", "summary": "", "content": {"keywords": ["boot", "shutdown"]}}
        text = _row_text(row)
        assert "BKT wiring" in text
        assert "boot" in text
        assert "shutdown" in text


class TestBuildBm25:
    def test_falls_back_to_builtin_lexical_ranker(self):
        rows = [
            {"title": "BKT wiring", "summary": "boot shutdown hooks"},
            {"title": "unrelated", "summary": "other words"},
        ]
        with patch.dict(sys.modules, {"rank_bm25": None}):
            ranker = _build_bm25(rows)
        scores = ranker.get_scores(["bkt", "boot", "shutdown"])
        assert scores[0] > scores[1]


# ── RRF fusion ────────────────────────────────────────────────────────────────

class TestRrfFuse:
    def test_shared_doc_scores_highest(self):
        shared = _atom("SHARED", title="shared doc")
        only_a = _atom("ONLY_A", title="only in list a")
        only_b = _atom("ONLY_B", title="only in list b")
        fused = _rrf_fuse([[shared, only_a], [shared, only_b]])
        ids = [r["id"] for r in fused]
        assert ids[0] == "SHARED", "shared doc should rank first via RRF"

    def test_all_docs_included(self):
        a = _atom("A")
        b = _atom("B")
        c = _atom("C")
        fused = _rrf_fuse([[a, b], [b, c]])
        ids = {r["id"] for r in fused}
        assert ids == {"A", "B", "C"}

    def test_empty_lists(self):
        assert _rrf_fuse([[], []]) == []

    def test_single_list(self):
        a = _atom("A")
        b = _atom("B")
        fused = _rrf_fuse([[a, b]])
        assert [r["id"] for r in fused] == ["A", "B"]

    def test_rrf_score_field_added(self):
        a = _atom("A")
        fused = _rrf_fuse([[a]])
        assert "_rrf_score" in fused[0]
        assert fused[0]["_rrf_score"] > 0.0

    def test_weight_multiplier_applied(self):
        """Atom with weight=2.0 should outscore identical atom with weight=1.0."""
        heavy = _atom("HEAVY", weight=2.0)
        light = _atom("LIGHT", weight=1.0)
        # Both appear at rank 0 in their own lists
        fused = _rrf_fuse([[heavy], [light]])
        ids = [r["id"] for r in fused]
        assert ids[0] == "HEAVY"

    def test_weight_col_false_ignores_weight(self):
        heavy = _atom("HEAVY", weight=100.0)
        light = _atom("LIGHT", weight=1.0)
        # Both appear at same rank — without weight col, scores should be equal
        _rrf_fuse([[heavy, light], [heavy, light]], weight_col=False)
        # HEAVY is first in both lists, so it gets a higher RRF score anyway;
        # but if we put them at equal ranks the scores must be equal
        both_equal = _rrf_fuse([[heavy], [light]], weight_col=False)
        scores = [r["_rrf_score"] for r in both_equal]
        assert abs(scores[0] - scores[1]) < 1e-9, "without weight_col, scores equal"

    def test_rrf_formula_k60(self):
        """Verify 1/(60+1) = 0.01639... for rank-0 doc."""
        a = _atom("A")
        fused = _rrf_fuse([[a]])
        expected = 1.0 / (60 + 0 + 1)  # rank=0, k=60
        assert abs(fused[0]["_rrf_score"] - expected) < 1e-9

    def test_log_mode_dampens_heavy_weight(self):
        heavy = _atom("HEAVY", weight=4.0)
        light = _atom("LIGHT", weight=1.0)
        fused_full = _rrf_fuse([[heavy], [light]], weight_mode="full")
        fused_log = _rrf_fuse([[heavy], [light]], weight_mode="log")
        assert fused_full[0]["id"] == "HEAVY"
        assert fused_log[0]["_rrf_score"] < fused_full[0]["_rrf_score"]

    def test_cap_mode_clamps_weight(self):
        heavy = _atom("HEAVY", weight=4.0)
        fused = _rrf_fuse([[heavy]], weight_mode="cap", weight_cap=2.0)
        base = 1.0 / 61
        assert abs(fused[0]["_rrf_score"] - base * 2.0) < 1e-9

    def test_cosine_bypass_ignores_weight_when_similar(self):
        cold = _atom("COLD", weight=4.0)
        cold["_cosine_sim"] = 0.7
        warm = _atom("WARM", weight=1.0)
        fused_full = _rrf_fuse([[cold], [warm]], weight_mode="full")
        fused_bypass = _rrf_fuse(
            [[cold], [warm]],
            weight_mode="cosine_bypass",
            weight_cap=2.0,
            cosine_bypass=0.55,
        )
        assert fused_full[0]["id"] == "COLD"
        # Bypass removes the 4x weight advantage on the high-cosine atom
        full_ratio = fused_full[0]["_rrf_score"] / fused_full[1]["_rrf_score"]
        bypass_ratio = fused_bypass[0]["_rrf_score"] / fused_bypass[1]["_rrf_score"]
        assert bypass_ratio < full_ratio


class TestRetrievalWeightFactor:
    def test_off_returns_one(self):
        assert _retrieval_weight_factor(_atom("A", weight=5.0), "off") == 1.0

    def test_log_dampening(self):
        assert _retrieval_weight_factor(_atom("A", weight=1.0), "log") == 1.0
        assert _retrieval_weight_factor(_atom("A", weight=2.0), "log") > 1.0
        assert _retrieval_weight_factor(_atom("A", weight=4.0), "log") < 4.0

    def test_cosine_bypass_high_sim(self):
        row = _atom("A", weight=4.0)
        row["_cosine_sim"] = 0.6
        assert _retrieval_weight_factor(row, "cosine_bypass", cosine_bypass=0.55) == 1.0


class TestLexicalCoverageBias:
    def test_exact_query_coverage_beats_partial_generic_match(self):
        exact = _atom("BKT", title="BKT wiring sequence",
                      summary="boot shutdown hook insertion points")
        generic = _atom("BOOT", title="boot shutdown",
                        summary="generic session handoff")
        exact["_rrf_score"] = 0.06
        generic["_rrf_score"] = 0.10

        ranked = _apply_lexical_coverage_bias(
            [generic, exact], ["bkt", "boot", "shutdown", "wiring"]
        )

        assert ranked[0]["id"] == "BKT"
        assert ranked[0]["_lexical_coverage"] == 1.0
        assert ranked[0]["_hybrid_score"] > ranked[1]["_hybrid_score"]

    def test_empty_query_tokens_leave_results_unchanged(self):
        row = _atom("A")
        assert _apply_lexical_coverage_bias([row], []) == [row]


# ── Temporal re-ranking ───────────────────────────────────────────────────────

class TestTemporalRerank:
    def test_recent_atom_scores_higher(self):
        now = datetime.now(timezone.utc)
        recent = _atom("RECENT", created_at=now - timedelta(days=1))
        old = _atom("OLD", created_at=now - timedelta(days=365))
        # Give them equal RRF scores first
        recent["_rrf_score"] = 0.5
        old["_rrf_score"] = 0.5
        reranked = temporal_rerank([recent, old], decay_days=30.0)
        assert reranked[0]["id"] == "RECENT"

    def test_returns_all_results(self):
        atoms = [_atom(f"A{i}") for i in range(5)]
        for a in atoms:
            a["_rrf_score"] = 0.1
        reranked = temporal_rerank(atoms)
        assert len(reranked) == 5

    def test_empty_input(self):
        assert temporal_rerank([]) == []

    def test_blended_score_field_added(self):
        a = _atom("A")
        a["_rrf_score"] = 0.5
        reranked = temporal_rerank([a])
        assert "_blended_score" in reranked[0]
        assert "_temporal_score" in reranked[0]

    def test_temporal_score_range(self):
        now = datetime.now(timezone.utc)
        # Just-written atom: score should be close to 1.0
        brand_new = _atom("NEW", created_at=now)
        brand_new["_rrf_score"] = 0.5
        reranked = temporal_rerank([brand_new], decay_days=30.0)
        assert reranked[0]["_temporal_score"] > 0.99, "brand new atom ~ 1.0"

        # 30-day-old atom: score should be ~0.5
        month_old = _atom("OLD", created_at=now - timedelta(days=30))
        month_old["_rrf_score"] = 0.5
        reranked2 = temporal_rerank([month_old], decay_days=30.0)
        assert abs(reranked2[0]["_temporal_score"] - 0.5) < 0.01, "30-day = 0.5 half-life"

    def test_no_timestamp_gets_midpoint(self):
        a = _atom("A")
        a["_rrf_score"] = 0.5
        a["created_at"] = None
        a["valid_at"] = None
        reranked = temporal_rerank([a])
        assert reranked[0]["_temporal_score"] == 0.5, "no timestamp → 0.5 midpoint"

    def test_weight_15_default(self):
        """Default temporal_weight=0.15 should be conservative."""
        now = datetime.now(timezone.utc)
        high_rrf = _atom("HIGH", created_at=now - timedelta(days=100))
        low_rrf = _atom("LOW", created_at=now)
        high_rrf["_rrf_score"] = 1.0
        low_rrf["_rrf_score"] = 0.0
        reranked = temporal_rerank([high_rrf, low_rrf], temporal_weight=0.15)
        # High RRF atom should still win despite being older
        assert reranked[0]["id"] == "HIGH"


# ── hybrid_search integration (DB mocked) ─────────────────────────────────────

class TestHybridSearch:
    def _pgvec_rows(self):
        return [
            _atom("VEC1", title="vector result"),
            _atom("VEC2", title="another vector"),
        ]

    def _bm25_rows(self):
        return [
            _atom("BM1", title="bm25 keyword match"),
            _atom("VEC1", title="vector result"),  # overlap with vec leg
        ]

    def test_falls_back_to_ilike_when_no_embed_and_no_bm25(self):
        pg = _mock_pg([_atom("A", title="test result")])
        with patch("core.pg_bridge.embed", return_value=None), \
             patch("willow.ranking.hybrid._bm25_search",
                   side_effect=ImportError("no rank_bm25")):
            hybrid_search("test query", pg)
        # Should have called the fallback
        pg.knowledge_search.assert_called_once()

    def test_returns_list(self):
        pg = _mock_pg([_atom("A")])
        with patch("core.pg_bridge.embed", return_value=None):
            results = hybrid_search("anything", pg)
        assert isinstance(results, list)

    def test_rrf_score_on_results(self):
        rows = [_atom("A", title="result"), _atom("B", title="result too")]
        pg = _mock_pg(rows)
        fake_vec = [0.1] * 768

        with patch("core.pg_bridge.embed", return_value=fake_vec), \
             patch("willow.ranking.hybrid._pgvector_search_raw",
                   return_value=rows), \
             patch("willow.ranking.hybrid._bm25_search",
                   return_value=list(reversed(rows))):
            results = hybrid_search("test", pg)

        assert all("_rrf_score" in r for r in results)

    def test_shared_doc_promoted(self):
        shared = _atom("SHARED", title="shared")
        only_vec = _atom("ONLY_VEC", title="vector only")
        only_bm25 = _atom("ONLY_BM25", title="bm25 only")
        fake_vec = [0.1] * 768

        pg = _mock_pg([shared, only_vec])
        with patch("core.pg_bridge.embed", return_value=fake_vec), \
             patch("willow.ranking.hybrid._pgvector_search_raw",
                   return_value=[shared, only_vec]), \
             patch("willow.ranking.hybrid._bm25_search",
                   return_value=[shared, only_bm25]):
            results = hybrid_search("query", pg)

        ids = [r["id"] for r in results]
        assert ids[0] == "SHARED", "shared doc should rank first"

    def test_limit_respected(self):
        rows = [_atom(f"R{i}") for i in range(20)]
        fake_vec = [0.1] * 768

        pg = _mock_pg(rows)
        with patch("core.pg_bridge.embed", return_value=fake_vec), \
             patch("willow.ranking.hybrid._pgvector_search_raw",
                   return_value=rows), \
             patch("willow.ranking.hybrid._bm25_search",
                   return_value=rows):
            results = hybrid_search("query", pg, limit=5)

        assert len(results) <= 5

    def test_temporal_flag_adds_blended_score(self):
        now = datetime.now(timezone.utc)
        rows = [_atom("A", created_at=now - timedelta(days=5))]
        fake_vec = [0.1] * 768

        pg = _mock_pg(rows)
        with patch("core.pg_bridge.embed", return_value=fake_vec), \
             patch("willow.ranking.hybrid._pgvector_search_raw",
                   return_value=rows), \
             patch("willow.ranking.hybrid._bm25_search", return_value=rows):
            results = hybrid_search("query", pg, temporal=True)

        assert all("_blended_score" in r for r in results)

    def test_vec_only_when_bm25_unavailable(self):
        rows = [_atom("A"), _atom("B")]
        fake_vec = [0.1] * 768

        pg = _mock_pg(rows)
        with patch("core.pg_bridge.embed", return_value=fake_vec), \
             patch("willow.ranking.hybrid._pgvector_search_raw",
                   return_value=rows), \
             patch("willow.ranking.hybrid._bm25_search",
                   side_effect=ImportError("no rank_bm25")):
            results = hybrid_search("query", pg)

        assert isinstance(results, list)
        # Should have results from vector leg
        assert len(results) > 0

    def test_bm25_only_when_embed_fails(self):
        rows = [_atom("A", title="keyword"), _atom("B", title="keyword too")]
        pg = _mock_pg(rows)

        with patch("core.pg_bridge.embed", return_value=None), \
             patch("willow.ranking.hybrid._bm25_search", return_value=rows):
            results = hybrid_search("keyword", pg)

        assert isinstance(results, list)

    def test_bm25_fetches_token_matched_candidates(self):
        rows = [
            _atom("BKT", title="BKT wiring sequence",
                  summary="boot shutdown hook insertion points"),
            _atom("BOOT", title="shutdown"),
        ]
        pg = _mock_pg(rows)
        fake_bm25 = MagicMock()
        fake_bm25.get_scores.return_value = [3.0, 1.0]

        with patch("willow.ranking.hybrid._build_bm25", return_value=fake_bm25):
            results = _bm25_search(
                pg, ["bkt", "boot", "shutdown", "wiring"],
                project=None, fork_id=None, include_invalid=False, wide_k=10,
            )

        sql, params = pg.conn.cursor.return_value.execute.call_args.args
        assert "ILIKE" in sql
        assert "%bkt%" in params
        assert results[0]["id"] == "BKT"


# ── bm25_search standalone ───────────────────────────────────────────────────

class TestBm25SearchStandalone:
    def test_returns_list(self):
        pg = _mock_pg([_atom("A", title="keyword result")])
        with patch("willow.ranking.hybrid._bm25_search",
                   return_value=[_atom("A", title="keyword result")]):
            results = bm25_search("keyword", pg)
        assert isinstance(results, list)

    def test_empty_query_returns_empty(self):
        pg = _mock_pg()
        results = bm25_search("", pg)
        assert results == []

    def test_fallback_when_no_rank_bm25(self):
        pg = _mock_pg([_atom("A")])
        with patch("willow.ranking.hybrid._bm25_search",
                   side_effect=ImportError("no rank_bm25")):
            bm25_search("test", pg)
        pg.knowledge_search.assert_called_once()
