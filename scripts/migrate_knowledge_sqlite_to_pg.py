#!/usr/bin/env python3
"""
migrate_knowledge_sqlite_to_pg.py — Migrate knowledge atoms from SQLite → Postgres.

Reads from a SQLite knowledge.db (desktop or legacy willow.db) and upserts into
the live Postgres knowledge table.

Collision strategy: skip if Postgres atom is newer, overwrite if SQLite atom is newer
(comparison on valid_at).

Postgres-only columns with no SQLite equivalent:
  - embedding:   left NULL (backfill separately)
  - tier:        defaults to 'observed'
  - confidence:  defaults to 1.0

Usage:
    python scripts/migrate_knowledge_sqlite_to_pg.py \\
        --source /path/to/knowledge.db \\
        [--batch-size 1000] \\
        [--dry-run] \\
        [--project FILTER]

Set WILLOW_PG_DB / WILLOW_PG_USER / WILLOW_PG_HOST as needed (see pg_bridge.py).
"""
import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg2
import psycopg2.extras

_UPSERT = """
INSERT INTO knowledge (
    id, project, valid_at, invalid_at, created_at,
    title, summary, content, source_type, category,
    visit_count, weight, last_visited, fork_id,
    tier, confidence
)
VALUES %s
ON CONFLICT (id) DO UPDATE SET
    project      = EXCLUDED.project,
    valid_at     = EXCLUDED.valid_at,
    invalid_at   = EXCLUDED.invalid_at,
    title        = EXCLUDED.title,
    summary      = EXCLUDED.summary,
    content      = EXCLUDED.content,
    source_type  = EXCLUDED.source_type,
    category     = EXCLUDED.category,
    visit_count  = EXCLUDED.visit_count,
    weight       = EXCLUDED.weight,
    last_visited = EXCLUDED.last_visited,
    fork_id      = EXCLUDED.fork_id,
    tier         = EXCLUDED.tier,
    confidence   = EXCLUDED.confidence
WHERE EXCLUDED.valid_at > knowledge.valid_at
"""


def _pg_connect() -> psycopg2.extensions.connection:
    return psycopg2.connect(
        dbname=os.environ.get("WILLOW_PG_DB", "willow_20"),
        user=os.environ.get("WILLOW_PG_USER", os.environ.get("USER", "")),
        host=os.environ.get("WILLOW_PG_HOST") or None,
        port=os.environ.get("WILLOW_PG_PORT") or None,
        connect_timeout=10,
    )


def _parse_content(raw) -> str:
    """Ensure content is valid JSON string for JSONB insert."""
    if raw is None:
        return json.dumps(None)
    if isinstance(raw, (dict, list)):
        return json.dumps(raw, default=str)
    try:
        parsed = json.loads(raw)
        return json.dumps(parsed, default=str)
    except (json.JSONDecodeError, TypeError):
        return json.dumps({"raw": str(raw)})


def _row_to_tuple(row: dict) -> tuple:
    return (
        row["id"],
        row.get("project") or "global",
        row.get("valid_at"),
        row.get("invalid_at"),
        row.get("created_at"),
        row.get("title"),
        row.get("summary"),
        psycopg2.extras.Json(json.loads(_parse_content(row.get("content")))),
        row.get("source_type"),
        row.get("category"),
        row.get("visit_count") or 0,
        row.get("weight") or 1.0,
        row.get("last_visited"),
        row.get("fork_id"),
        row.get("tier") or "observed",
        row.get("confidence") if row.get("confidence") is not None else 1.0,
    )


def migrate(source: Path, batch_size: int, dry_run: bool, project_filter: str | None):
    if not source.exists():
        print(f"ERROR: source not found: {source}", file=sys.stderr)
        sys.exit(1)

    sqlite_conn = sqlite3.connect(f"file:{source}?mode=ro&immutable=1", uri=True)
    sqlite_conn.row_factory = sqlite3.Row

    cur = sqlite_conn.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(f"Tables: {tables}")

    count_sql = "SELECT COUNT(*) FROM knowledge WHERE invalid_at IS NULL"
    params: list = []
    if project_filter:
        count_sql += " AND project = ?"
        params.append(project_filter)
    total = cur.execute(count_sql, params).fetchone()[0]
    print(f"Source: {source}  ({total:,} valid atoms{f', project={project_filter}' if project_filter else ''})")

    if dry_run:
        print("[dry-run] No data will be written.")

    pg = _pg_connect() if not dry_run else None

    select_sql = "SELECT * FROM knowledge WHERE invalid_at IS NULL"
    if project_filter:
        select_sql += " AND project = ?"
    select_sql += " ORDER BY valid_at ASC"

    rows_read = 0
    rows_upserted = 0
    batch: list[tuple] = []
    t0 = time.time()

    def flush():
        nonlocal rows_upserted
        if not batch or dry_run:
            rows_upserted += len(batch)
            return
        with pg.cursor() as pgcur:
            psycopg2.extras.execute_values(pgcur, _UPSERT, batch, template=None, page_size=batch_size)
        pg.commit()
        rows_upserted += len(batch)

    for row in cur.execute(select_sql, params):
        d = dict(row)
        try:
            batch.append(_row_to_tuple(d))
        except Exception as e:
            print(f"  SKIP {d.get('id')}: {e}", file=sys.stderr)
            continue

        rows_read += 1
        if len(batch) >= batch_size:
            flush()
            batch.clear()
            elapsed = time.time() - t0
            pct = rows_read / total * 100 if total else 0
            rate = rows_read / elapsed if elapsed > 0 else 0
            eta = (total - rows_read) / rate if rate > 0 else 0
            print(f"  {rows_read:>8,}/{total:,} ({pct:.1f}%)  {rate:.0f} rows/s  ETA {eta:.0f}s")

    if batch:
        flush()
        batch.clear()

    elapsed = time.time() - t0
    print(f"\nDone. {rows_upserted:,} rows {'would be ' if dry_run else ''}upserted in {elapsed:.1f}s.")

    sqlite_conn.close()
    if pg:
        pg.close()


def probe(source: Path):
    """Print table names and row counts for a SQLite file."""
    if not source.exists():
        print(f"MISSING: {source}")
        return
    size_mb = source.stat().st_size / (1024 * 1024)
    print(f"File size: {size_mb:.2f} MB")
    conn = sqlite3.connect(f"file:{source}?mode=ro&immutable=1", uri=True)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(f"{source}")
    print(f"  Tables: {tables}")
    for t in tables:
        try:
            n = conn.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
            cols = [d[0] for d in conn.execute(f"SELECT * FROM [{t}] LIMIT 0").description]
            print(f"  {t}: {n:,} rows  cols={cols}")
        except Exception as e:
            print(f"  {t}: ERROR {e}")
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite knowledge → Postgres")
    parser.add_argument("--source", required=True, help="Path to source SQLite knowledge.db")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--dry-run", action="store_true", help="Read only, no writes")
    parser.add_argument("--project", default=None, help="Migrate only this project namespace")
    parser.add_argument("--probe", action="store_true", help="Print schema and row counts, then exit")
    args = parser.parse_args()

    if args.probe:
        probe(Path(args.source))
        return

    migrate(
        source=Path(args.source),
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        project_filter=args.project,
    )


if __name__ == "__main__":
    main()
