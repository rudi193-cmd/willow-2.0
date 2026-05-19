#!/usr/bin/env python3
# b17: 51721  ΔΣ=42
"""
index_session_prompts.py — Index raw session prompts into opus.atoms.

Reads human prompts from claude_sessions_all.db, filters to length > 80 chars,
and ingests them into Postgres opus_atoms for phrase search via opus_search.

Kill-safe: progress tracked in ~/.willow/corpus_index_log.db. Resume-safe.

Usage:
    python3 scripts/index_session_prompts.py [--dry-run] [--batch-size 50] [--limit N]
"""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.pg_bridge import PgBridge

SESSIONS_DB = Path.home() / ".willow" / "claude_sessions_all.db"
LOG_DB      = Path.home() / ".willow" / "corpus_index_log.db"
DOMAIN      = "hanuman/corpus"
DEPTH       = 1
MIN_LENGTH  = 80
DEFAULT_BATCH = 100


def init_log(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS indexed_prompts (
            key        TEXT PRIMARY KEY,
            atom_id    TEXT,
            indexed_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()


def already_indexed(conn):
    return {r[0] for r in conn.execute("SELECT key FROM indexed_prompts")}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run",    action="store_true", help="Preview without writing")
    parser.add_argument("--no-embed",   action="store_true", help="Skip embeddings (fast bulk insert)")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH)
    parser.add_argument("--limit",      type=int, default=0, help="Cap rows (0=all)")
    args = parser.parse_args()

    if not SESSIONS_DB.exists():
        print(f"ERROR: {SESSIONS_DB} not found", flush=True)
        sys.exit(1)

    src = sqlite3.connect(str(SESSIONS_DB))
    log = sqlite3.connect(str(LOG_DB))
    init_log(log)

    done = already_indexed(log)
    print(f"[index] already indexed: {len(done)}", flush=True)

    sql = """
        SELECT id, uuid, session_id, prompt_text
        FROM prompts
        WHERE LENGTH(prompt_text) > ?
          AND (is_meta = 0 OR is_meta IS NULL)
        ORDER BY id
    """
    if args.limit:
        sql += f" LIMIT {args.limit}"

    rows = src.execute(sql, (MIN_LENGTH,)).fetchall()

    # Use uuid as dedup key; fall back to str(id) if uuid is NULL
    candidates = [
        (str(uuid) if uuid else str(row_id), session_id, prompt_text)
        for row_id, uuid, session_id, prompt_text in rows
    ]
    candidates = [(key, sid, text) for key, sid, text in candidates if key not in done]

    print(f"[index] candidates: {len(candidates)}", flush=True)

    if args.dry_run:
        print("[index] dry-run — first 3 samples:")
        for key, sid, text in candidates[:3]:
            print(f"  [{key[:8]}] {text[:120]!r}")
        src.close()
        log.close()
        return

    pg = PgBridge()
    pg._ensure_conn()
    ingested = errors = 0
    import uuid as _uuid

    for key, session_id, prompt_text in candidates:
        try:
            atom_id = pg.gen_id(8)

            if args.no_embed:
                # Fast path: insert without embedding; embed backfill runs separately
                with pg.conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO opus_atoms (id, content, domain, depth, source_session)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (atom_id, prompt_text, DOMAIN, DEPTH, session_id))
                pg.conn.commit()
            else:
                atom_id = pg.ingest_opus_atom(
                    content=prompt_text,
                    domain=DOMAIN,
                    depth=DEPTH,
                    source_session=session_id,
                )

            log.execute(
                "INSERT OR IGNORE INTO indexed_prompts (key, atom_id) VALUES (?, ?)",
                (key, atom_id),
            )
            ingested += 1

            if ingested % args.batch_size == 0:
                log.commit()
                print(f"[index] {ingested}/{len(candidates)} ingested  ({errors} errors)", flush=True)

        except Exception as e:
            errors += 1
            print(f"[index] ERROR [{key[:8]}]: {e}", flush=True)
            if errors > 100:
                print("[index] error threshold hit — stopping", flush=True)
                break

    log.commit()
    src.close()
    log.close()
    print(f"[index] done — {ingested} ingested, {errors} errors", flush=True)


if __name__ == "__main__":
    main()
