"""
willow/ranking — Hybrid retrieval and ranking for the Willow KB.
b17: RANK1  ΔΣ=42

Provides:
  - hybrid_search:    pgvector cosine + BM25 RRF fusion over knowledge table
  - temporal_rerank:  half-life recency boost as a post-processing step
  - bm25_search:      pure BM25 keyword search (useful for standalone use)

Ported and adapted from m4cd4r4/claude-echoes (MIT), which proved the
pattern on LongMemEval: BM25 + pgvector RRF is the single highest-leverage
retrieval improvement (+7-10 points over pure cosine), especially for
rare-term and temporal queries.

Key decisions vs. claude-echoes:
  - Willow's knowledge table uses `title` + `summary` as the searchable text
    surface (claude-echoes uses full verbatim `content`). BM25 is built over
    the concatenation of those two fields.
  - The GIN tsvector index already exists on Willow's `knowledge` table
    (idx_knowledge_fts if present); we also use raw SQL `to_tsvector` as a
    fallback since the BM25 index is computed in-process.
  - RRF k=60 from Cormack et al. 2009 — same constant claude-echoes uses.
  - `project` and `fork_id` filters flow through both legs of the search.
  - `weight` column on knowledge rows is respected as a post-RRF multiplier.
"""

from willow.ranking.hybrid import hybrid_search, temporal_rerank, bm25_search

__all__ = ["hybrid_search", "temporal_rerank", "bm25_search"]
