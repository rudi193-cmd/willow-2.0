from core.kb_quality import (
    canonical_quality_check,
    graph_readiness_check,
    route_stop_session_memory,
    search_readiness_check,
    session_summary_quality_check,
)
from core.pg_bridge import PgBridge


def test_canonical_quality_accepts_specific_provenanced_atom():
    result = canonical_quality_check(
        title="Kart stale-running recovery contract",
        summary=(
            "Kart marks stale running tasks as failed when their updated_at timestamp "
            "exceeds the configured orphan threshold, preserving queue liveness."
        ),
        content={"evidence": "docs/audits/KART_DEEP_AUDIT_2026-06-04.md"},
        source_type="audit",
        source_id="kart-audit",
        confidence=0.95,
    )

    assert result["satisfied"] is True
    assert result["flags"] == []


def test_canonical_quality_blocks_thin_unprovenanced_atoms():
    result = canonical_quality_check(
        title="TODO",
        summary="placeholder",
        content={},
        source_type="mcp",
        source_id="",
        confidence=0.70,
    )

    assert result["satisfied"] is False
    expected = {
        "title_too_short",
        "summary_too_thin",
        "placeholder_text",
        "low_confidence",
        "missing_provenance",
    }
    assert expected <= set(result["flags"])


def test_search_readiness_blocks_search_noise():
    result = search_readiness_check(
        title="Benchmark community node shard",
        summary="Synthetic benchmark placeholder used for community detection evaluation corpus.",
        content={"search_noise": True},
        source_type="benchmark",
        source_id="conv-49",
        confidence=0.95,
    )
    assert result["satisfied"] is False
    assert "search_noise" in result["flags"]


def test_search_readiness_blocks_title_collision():
    result = search_readiness_check(
        title="Operator handoff summary",
        summary="Closed webhook auth review and queued Pangolin config follow-up for operator decision.",
        content={"evidence": "handoff-2026-06-09"},
        source_type="session",
        source_id="handoff-2026-06-09",
        confidence=0.9,
        title_collision_count=3,
    )
    assert result["satisfied"] is False
    assert "title_collision" in result["flags"]


def test_graph_readiness_allows_benchmark_exemption():
    result = graph_readiness_check(
        degree=1,
        content={"search_noise": True},
        source_type="benchmark",
    )
    assert result["satisfied"] is True
    assert result["exempt"] is True


def test_graph_readiness_flags_low_degree_operator_atoms():
    result = graph_readiness_check(
        degree=1,
        content={"evidence": "ops/handoff.md"},
        source_type="session",
    )
    assert result["satisfied"] is False
    assert "low_degree" in result["flags"]


def test_rich_embedding_text_includes_metadata_fields():
    pg = PgBridge.__new__(PgBridge)
    text = pg._knowledge_embedding_text({
        "title": "Binder edge retrieval",
        "summary": "Graph neighbor expansion uses public.edges to recover adjacent atoms.",
        "source_type": "intake",
        "category": "retrieval",
        "content": {
            "keywords": ["binder", "public.edges"],
            "tags": ["fleet-memory"],
            "evidence": "docs/audits/FLEET_MEMORY_AUDIT_2026-06-07.md",
        },
    })

    assert "Binder edge retrieval" in text
    assert "public.edges" in text
    assert "fleet-memory" in text
    assert "FLEET_MEMORY_AUDIT" in text


def test_session_summary_quality_requires_provenance():
    bad = session_summary_quality_check(
        title="session abc123 · clean",
        summary="short",
        source_id="",
        confidence=0.9,
    )
    assert bad["satisfied"] is False

    good = session_summary_quality_check(
        title="session abc123 · clean",
        summary=(
            "Closed BKT wiring PRs and tagged v2026.06.2 after CI passed on master."
        ),
        source_id="sess-abc123",
        confidence=0.9,
    )
    assert good["satisfied"] is True


def test_route_stop_session_memory_friction_to_intake():
    assert route_stop_session_memory(
        "friction",
        title="session abc · friction",
        summary="Repeated blocked bash attempts on shell work during the session.",
        source_id="sess-1",
        confidence=0.65,
    ) == "intake"


def test_route_stop_session_memory_clean_thin_to_intake():
    assert route_stop_session_memory(
        "clean",
        title="session abc · clean",
        summary="ok",
        source_id="sess-1",
        confidence=0.9,
    ) == "intake"


def test_ingest_atom_blocks_bad_canonical_before_write():
    pg = PgBridge.__new__(PgBridge)

    atom_id = pg.ingest_atom(
        title="Bad",
        summary="placeholder",
        source_type="mcp",
        source_id="",
        tier="canonical",
        confidence=0.70,
    )

    assert atom_id is None
    assert "canonical_quality_gate" in pg._last_ingest_error
