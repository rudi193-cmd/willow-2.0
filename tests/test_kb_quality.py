from core.kb_quality import canonical_quality_check
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

