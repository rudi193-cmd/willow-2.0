#!/usr/bin/env python3
"""
pg_completeness_gate.py — Assert ≥ threshold completeness on key Postgres tables.
b17: A8074  ΔΣ=42

Default threshold: 96%. Exit 0 if all checks pass, 1 otherwise.

Metrics are intentional: raw "embedding IS NOT NULL / all rows" on knowledge is
dominated by tombstoned (invalid_at) atoms and is not used as the gate metric.

Usage:
  python3 scripts/pg_completeness_gate.py [--threshold 96]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.pg_bridge import PgBridge

# Must match scripts/willow_embed_backfill.py
_SKIP_PROJECTS = (
    "session-turn",
    "conversation",
    "file_location",
    "die-namic-index",
    "willow_index",
    "sessions",
    "telemetry",
    "training",
)
_MIN_TEXT = 20


def _skip_sql() -> str:
    return ", ".join(f"'{p}'" for p in _SKIP_PROJECTS)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=96.0, help="Minimum pass %% per check")
    args = ap.parse_args()
    thr: float = args.threshold
    skip_in = _skip_sql()

    pg = PgBridge()
    c = pg.conn.cursor()
    failures: list[str] = []

    def check(name: str, sql: str) -> tuple[float, str]:
        c.execute(sql)
        row = c.fetchone()
        raw = row[0] if row else None
        # NULL % usually means 0-row denominator — treat as satisfied.
        pct = float(raw) if raw is not None else 100.0
        detail = row[1] if row and len(row) > 1 else ""
        ok = pct >= thr
        if not ok:
            failures.append(f"{name}: {pct:.4f}% < {thr}% {detail}")
        return pct, detail

    print(f"=== pg completeness gate (threshold {thr}%) ===\n")

    # 1) Knowledge: valid rows that need semantic search vectors (long enough text)
    pct, _ = check(
        "knowledge_embed_semantic",
        f"""
        WITH base AS (
          SELECT embedding IS NOT NULL AS has_e,
                 length(trim(coalesce(title,'')||' '||coalesce(summary,''))) AS txtlen
          FROM public.knowledge
          WHERE invalid_at IS NULL AND project NOT IN ({skip_in})
        )
        SELECT 100.0 * count(*) FILTER (WHERE txtlen >= {_MIN_TEXT} AND has_e) / NULLIF(count(*) FILTER (WHERE txtlen >= {_MIN_TEXT}), 0),
               '(' || count(*) FILTER (WHERE txtlen >= {_MIN_TEXT})::text || ' rows)'
        FROM base
        """,
    )
    print(f"  knowledge_embed_semantic     {pct:.4f}%  (valid, not skipped-project, text>={_MIN_TEXT} chars)")

    # 2) Knowledge: valid rows — embedded OR exempt (short text) OR skipped-project bucket
    pct, _ = check(
        "knowledge_valid_satisfied",
        f"""
        SELECT 100.0 * count(*) FILTER (WHERE
                 embedding IS NOT NULL
              OR length(trim(coalesce(title,'')||' '||coalesce(summary,''))) < {_MIN_TEXT}
              OR project IN ({skip_in})
            ) / NULLIF(count(*), 0),
               '(' || count(*)::text || ' valid rows)'
        FROM public.knowledge
        WHERE invalid_at IS NULL
        """,
    )
    print(f"  knowledge_valid_satisfied   {pct:.4f}%  (emb OR short-text OR skipped-project)")

    # 3) Tables with embedding column
    for table in ("jeles_atoms", "opus_atoms"):
        c.execute(f"SELECT count(*) FROM public.{table}")
        n = c.fetchone()[0]
        if n == 0:
            print(f"  {table:28}  (empty — skip)")
            continue
        pct, _ = check(
            f"{table}_embedding",
            f"""
            SELECT 100.0 * count(embedding) / NULLIF(count(*), 0), '(' || count(*)::text || ' rows)'
            FROM public.{table}
            """,
        )
        print(f"  {table + '_embedding':28} {pct:.4f}%")

    # 4) Relational tables: non-null on key fields (skip when table empty)
    relational: list[tuple[str, str, str]] = [
        (
            "binder_edges",
            "binder_edges_endpoints",
            "SELECT 100.0 * count(*) FILTER (WHERE source_atom IS NOT NULL AND target_atom IS NOT NULL) / NULLIF(count(*), 0), '(' || count(*)::text || ' rows)' FROM public.binder_edges",
        ),
        (
            "tasks",
            "tasks_nonempty",
            "SELECT 100.0 * count(*) FILTER (WHERE task IS NOT NULL AND length(trim(task)) > 0) / NULLIF(count(*), 0), '(' || count(*)::text || ' rows)' FROM public.tasks",
        ),
        (
            "jeles_sessions",
            "jeles_sessions_path",
            "SELECT 100.0 * count(*) FILTER (WHERE jsonl_path IS NOT NULL AND length(trim(jsonl_path)) > 0) / NULLIF(count(*), 0), '(' || count(*)::text || ' rows)' FROM public.jeles_sessions",
        ),
        (
            "frank_ledger",
            "frank_ledger_content",
            "SELECT 100.0 * count(*) FILTER (WHERE content IS NOT NULL) / NULLIF(count(*), 0), '(' || count(*)::text || ' rows)' FROM public.frank_ledger",
        ),
        (
            "agents",
            "agents_name_present",
            "SELECT 100.0 * count(*) FILTER (WHERE name IS NOT NULL AND length(trim(name)) > 0) / NULLIF(count(*), 0), '(' || count(*)::text || ' rows)' FROM public.agents",
        ),
        (
            "grove_links",
            "grove_links_required",
            "SELECT 100.0 * count(*) FILTER (WHERE sean_table IS NOT NULL AND length(trim(sean_table)) > 0 "
            "AND sean_record_id IS NOT NULL AND length(trim(sean_record_id)) > 0 "
            "AND grove_message_id IS NOT NULL) / NULLIF(count(*), 0), '(' || count(*)::text || ' rows)' FROM public.grove_links",
        ),
        (
            "session_index",
            "session_index_paths",
            "SELECT 100.0 * count(*) FILTER (WHERE session_id IS NOT NULL AND length(trim(session_id)) > 0 "
            "AND file_path IS NOT NULL AND length(trim(file_path)) > 0) / NULLIF(count(*), 0), "
            "'(' || count(*)::text || ' rows)' FROM public.session_index",
        ),
        (
            "sean_edges",
            "sean_edges_endpoints",
            "SELECT 100.0 * count(*) FILTER (WHERE willow_atom_id IS NOT NULL AND length(trim(willow_atom_id)) > 0 "
            "AND sean_table IS NOT NULL AND sean_record_id IS NOT NULL) / NULLIF(count(*), 0), "
            "'(' || count(*)::text || ' rows)' FROM public.sean_edges",
        ),
        (
            "edges",
            "edges_endpoints",
            "SELECT 100.0 * count(*) FILTER (WHERE from_id IS NOT NULL AND to_id IS NOT NULL AND relation IS NOT NULL) "
            "/ NULLIF(count(*), 0), '(' || count(*)::text || ' rows)' FROM public.edges",
        ),
        (
            "hook_registry",
            "hook_registry_required",
            "SELECT 100.0 * count(*) FILTER (WHERE name IS NOT NULL AND length(trim(handler_path)) > 0) "
            "/ NULLIF(count(*), 0), '(' || count(*)::text || ' rows)' FROM public.hook_registry",
        ),
        (
            "ratifications",
            "ratifications_required",
            "SELECT 100.0 * count(*) FILTER (WHERE agent IS NOT NULL AND jsonl_id IS NOT NULL AND ratified_at IS NOT NULL) "
            "/ NULLIF(count(*), 0), '(' || count(*)::text || ' rows)' FROM public.ratifications",
        ),
    ]
    for table, metric_name, sql in relational:
        c.execute(f"SELECT count(*) FROM public.{table}")
        nrows = c.fetchone()[0]
        if nrows == 0:
            print(f"  {metric_name:28} (empty table — skip)")
            continue
        pct, _ = check(metric_name, sql)
        print(f"  {metric_name:28} {pct:.4f}%")

    c.close()
    pg.conn.close()

    if failures:
        print("\nFAILURES:")
        for f in failures:
            print(" ", f)
        return 1
    print(f"\nPASS — all checks ≥ {thr}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
