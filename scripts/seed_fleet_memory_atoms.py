#!/usr/bin/env python3
"""Seed canonical KB atoms for fleet-memory gold-set gaps (idempotent by title)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.pg_bridge import PgBridge  # noqa: E402

ATOMS = [
    {
        "title": "Kart stale-running blocks kart_task_run fallback",
        "summary": (
            "Kart orphan recovery: tasks stuck in status=running with result IS NULL "
            "suppress kart_task_run fallback because the poll loop waits for zero running rows. "
            "reap_stale_tasks(max_age_seconds=3600) marks aged running tasks failed with "
            "error=orphaned_running_reaped. Operational fix: run reap before kart_task_run "
            "when fleet_status.kart.stale_running > 0."
        ),
        "category": "operations",
        "source_type": "audit",
        "source_id": "docs/audits/KART_DEEP_AUDIT_2026-06-04.md",
        "keywords": [
            "kart stale-running",
            "orphaned running",
            "kart_task_run",
            "reap_stale_tasks",
            "task queue",
        ],
        "tags": ["kart", "fleet-memory", "canonical"],
        "content": {
            "evidence": "docs/audits/KART_DEEP_AUDIT_2026-06-04.md",
            "finding": "F1",
        },
    },
    {
        "title": "Binder edges sync to public.edges for graph retrieval",
        "summary": (
            "Approved binder edges are mirrored into Postgres public.edges via "
            "binder_promote_edge_to_postgres on mem_binder_edge_update(approved). "
            "kb_search(expand_neighbors=true) performs one-hop expansion over public.edges "
            "after semantic/keyword hits. Backfill: scripts/binder_backfill_postgres_edges.py."
        ),
        "category": "retrieval",
        "source_type": "audit",
        "source_id": "docs/audits/FLEET_MEMORY_AUDIT_2026-06-07.md",
        "keywords": [
            "binder edge linking",
            "public.edges",
            "graph neighbor expansion",
            "kb_search expand_neighbors",
        ],
        "tags": ["binder", "edges", "fleet-memory", "canonical"],
        "content": {
            "evidence": "docs/audits/FLEET_MEMORY_AUDIT_2026-06-07.md",
            "wiring": "C2+C3",
        },
    },
]


def main() -> int:
    pg = PgBridge()
    results = []
    try:
        for atom in ATOMS:
            existing = pg.knowledge_search(atom["title"], limit=5)
            if any(a.get("title") == atom["title"] for a in existing):
                results.append({"title": atom["title"], "status": "exists"})
                continue
            atom_id = pg.ingest_atom(
                title=atom["title"],
                summary=atom["summary"],
                source_type=atom["source_type"],
                source_id=atom["source_id"],
                category=atom["category"],
                domain="willow",
                keywords=atom["keywords"],
                tags=atom["tags"],
                tier="canonical",
                confidence=0.95,
            )
            if atom_id:
                with pg.conn.cursor() as cur:
                    cur.execute(
                        "UPDATE knowledge SET content = content || %s::jsonb WHERE id = %s",
                        (json.dumps(atom["content"]), atom_id),
                    )
                pg.conn.commit()
            results.append({
                "title": atom["title"],
                "status": "ingested" if atom_id else "failed",
                "id": atom_id,
                "error": getattr(pg, "_last_ingest_error", None),
            })
    finally:
        pg.close()
    print(json.dumps({"results": results}, indent=2))
    return 0 if all(r.get("status") in {"exists", "ingested"} for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
