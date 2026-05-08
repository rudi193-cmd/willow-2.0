#!/usr/bin/env python3
"""
willow_embed_backfill.py — Backfill NULL embeddings across Postgres tables.
b17: SEM01  ΔΣ=42

Run by Kart when queued via willow_embed_backfill task. Processes knowledge,
opus_atoms, and jeles_atoms in batches of 100 with 50ms sleep between batches.
Safe to interrupt and restart — re-queries NULL each pass.

Usage:
    python3 scripts/willow_embed_backfill.py [--limit N] [--dry-run]
"""
import argparse
import collections
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.embedder import embed
from core.pg_bridge import PgBridge
from core.willow_store import WillowStore

BATCH_SIZE = 100
SLEEP_S = 0.05
MAX_EMBED_CHARS = 6000  # nomic-embed-text context limit (~8192 tokens)
PROGRESS_COLLECTION = "hanuman/tasks"
PROGRESS_ID = "embed_backfill_progress"


RATE_WINDOW = collections.deque(maxlen=10)  # (timestamp, done_count) for rolling rate


def _write_progress(store: WillowStore, table: str, done: int, total: int, started_at: float) -> None:
    now = time.time()
    elapsed = now - started_at
    rate = done / elapsed if elapsed > 0 else 0

    RATE_WINDOW.append((now, done))
    if len(RATE_WINDOW) >= 2:
        dt = RATE_WINDOW[-1][0] - RATE_WINDOW[0][0]
        dc = RATE_WINDOW[-1][1] - RATE_WINDOW[0][1]
        rate_recent = dc / dt if dt > 0 else rate
    else:
        rate_recent = rate

    display_rate = rate_recent if rate_recent > 0 else rate
    remaining = (total - done) / display_rate if display_rate > 0 else 0
    store.put(PROGRESS_COLLECTION, {
        "id": PROGRESS_ID,
        "task": "willow_embed_backfill",
        "table": table,
        "atoms_done": done,
        "total": total,
        "pct": round(100 * done / total, 1) if total else 0,
        "rate_per_sec": round(rate, 2),
        "rate_recent": round(rate_recent, 2),
        "eta_seconds": int(remaining),
        "eta_human": f"{int(remaining // 3600)}h {int((remaining % 3600) // 60)}m",
        "started_at": datetime.fromtimestamp(started_at, tz=timezone.utc).isoformat(),
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    })


def _backfill_table(pg: PgBridge, store: WillowStore, table: str, text_expr: str,
                    dry_run: bool, limit: int, total_offset: int, grand_total: int,
                    started_at: float, extra_filter: str | None = None) -> int:
    """Backfill NULL embeddings for one table. Returns count of rows processed.

    Lock discipline: read tx commits before embed(); UPDATE is a single-row tx.
    No connection is held open during Ollama calls.
    """
    processed = 0
    skipped_ids: set = set()  # avoid re-querying atoms that failed this run
    where = "embedding IS NULL"
    if extra_filter:
        where += f" AND {extra_filter}"

    while True:
        # Phase 1: fetch IDs only, commit immediately to release the read tx.
        pg._ensure_conn()
        with pg.conn.cursor() as cur:
            skip_clause = f" AND id != ALL(%s)" if skipped_ids else ""
            cur.execute(
                f"SELECT id FROM {table} WHERE {where}{skip_clause} ORDER BY created_at DESC LIMIT %s",
                ([list(skipped_ids), BATCH_SIZE] if skipped_ids else [BATCH_SIZE]),
            )
            ids = [r[0] for r in cur.fetchall()]
        pg.conn.commit()

        if not ids:
            break

        batch_done = 0
        for row_id in ids:
            if limit and processed >= limit:
                return processed
            if dry_run:
                processed += 1
                batch_done += 1
                continue

            # Phase 2: fetch text in a short read tx, commit immediately.
            pg._ensure_conn()
            with pg.conn.cursor() as cur:
                cur.execute(f"SELECT {text_expr} FROM {table} WHERE id = %s", (row_id,))
                row = cur.fetchone()
            pg.conn.commit()

            if not row:
                continue
            text = row[0]

            # Phase 3: embed with no connection held.
            vec = None
            for attempt in range(3):
                vec = embed((text or "")[:MAX_EMBED_CHARS])
                if vec is not None:
                    break
                print(f"  [{table}] {row_id}: Ollama unavailable (attempt {attempt+1}/3) — retrying in 5s", flush=True)
                time.sleep(5)
            if vec is None:
                print(f"  [{table}] {row_id}: embed failed after 3 attempts — skipping", flush=True)
                skipped_ids.add(row_id)
                processed += 1  # count as processed so progress doesn't stall
                batch_done += 1
                continue

            # Phase 4: single-row UPDATE, commit immediately.
            vec_str = str(vec)
            pg._ensure_conn()
            with pg.conn.cursor() as cur:
                cur.execute(
                    f"UPDATE {table} SET embedding = %s::vector WHERE id = %s",
                    (vec_str, row_id),
                )
            pg.conn.commit()
            processed += 1
            batch_done += 1

        print(f"  [{table}] +{batch_done} embedded (total {processed})", flush=True)
        _write_progress(store, table, total_offset + processed, grand_total, started_at)
        time.sleep(SLEEP_S)

    return processed


def main():
    parser = argparse.ArgumentParser(description="Backfill NULL embeddings")
    parser.add_argument("--limit", type=int, default=0, help="Max rows per table (0 = unlimited)")
    parser.add_argument("--dry-run", action="store_true", help="Count rows without writing")
    args = parser.parse_args()

    pg = PgBridge()
    store = WillowStore()

    tables = [
        ("knowledge",   "COALESCE(title, '') || ' ' || COALESCE(summary, '')",
         "invalid_at IS NULL AND project NOT IN ('session-turn', 'conversation', 'file_location', 'die-namic-index', 'willow_index', 'global')"),
        ("opus_atoms",  "content", None),
        ("jeles_atoms", "COALESCE(title, '') || ' ' || content", None),
    ]

    # Count grand total for progress reporting
    grand_total = 0
    table_counts = []
    for table, text_expr, extra_filter in tables:
        where = "embedding IS NULL"
        if extra_filter:
            where += f" AND {extra_filter}"
        with pg.conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}")
            null_count = cur.fetchone()[0]
        table_counts.append((table, text_expr, extra_filter, null_count))
        grand_total += null_count

    started_at = time.time()
    total_offset = 0
    total = 0

    for table, text_expr, extra_filter, null_count in table_counts:
        if null_count == 0:
            print(f"[{table}] 0 NULL embeddings — skipping", flush=True)
            continue

        print(f"[{table}] {null_count} NULL embeddings — backfilling...", flush=True)
        n = _backfill_table(pg, store, table, text_expr, args.dry_run, args.limit,
                            total_offset, grand_total, started_at, extra_filter)
        total_offset += n
        total += n
        print(f"[{table}] done: {n} rows {'would be ' if args.dry_run else ''}processed", flush=True)

    # Final progress record
    if not args.dry_run and grand_total > 0:
        _write_progress(store, "done", total, grand_total, started_at)

    print(f"\n[backfill] total: {total} rows processed", flush=True)


if __name__ == "__main__":
    main()
