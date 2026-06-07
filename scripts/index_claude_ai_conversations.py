#!/usr/bin/env python3
# b17: 51721  ΔΣ=42
"""
index_claude_ai_conversations.py — Index Claude.ai conversations.json into opus.atoms.

Reads human messages from Claude.ai export format (conversations.json),
filters to length > 20 chars, and ingests into Postgres opus_atoms.

Kill-safe: progress tracked in ~/.willow/claude_ai_index_log.db. Resume-safe.

Usage:
    python3 scripts/index_claude_ai_conversations.py [--input /path/to/conversations.json]
    python3 scripts/index_claude_ai_conversations.py --dry-run
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))
from core.pg_bridge import PgBridge
from willow.fylgja.willow_home import willow_home

DEFAULT_INPUT = Path.home() / "inbox" / "conversations.json"
LOG_DB        = willow_home(_REPO) / "claude_ai_index_log.db"
DOMAIN        = "hanuman/corpus/claude-ai"
DEPTH         = 1
MIN_LENGTH    = 20
DEFAULT_BATCH = 100


def init_log(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS indexed_messages (
            key        TEXT PRIMARY KEY,
            atom_id    TEXT,
            indexed_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()


def already_indexed(conn):
    return {r[0] for r in conn.execute("SELECT key FROM indexed_messages")}


def extract_messages(data):
    """Yield (key, conversation_name, text) for each human message."""
    for convo in data:
        convo_uuid = convo.get("uuid", "")
        convo_name = convo.get("name", "")
        for msg in convo.get("chat_messages", []):
            if msg.get("sender") != "human":
                continue
            msg_uuid = msg.get("uuid", "")
            text = msg.get("text", "") or ""
            # Also check content array for text blocks
            if not text:
                for block in msg.get("content", []) or []:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text += block.get("text", "")
            text = text.strip()
            if len(text) < MIN_LENGTH:
                continue
            key = f"{convo_uuid}:{msg_uuid}" if msg_uuid else f"{convo_uuid}:{text[:40]}"
            yield key, convo_name, text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",      type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--dry-run",    action="store_true")
    parser.add_argument("--no-embed",   action="store_true", help="Skip embeddings (fast)")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH)
    args = parser.parse_args()

    if not args.input.exists():
        print(f"ERROR: {args.input} not found", flush=True)
        sys.exit(1)

    data = json.loads(args.input.read_text())
    print(f"[index] loaded {len(data)} conversations", flush=True)

    log = sqlite3.connect(str(LOG_DB))
    init_log(log)
    done = already_indexed(log)
    print(f"[index] already indexed: {len(done)}", flush=True)

    candidates = [
        (key, name, text)
        for key, name, text in extract_messages(data)
        if key not in done
    ]
    print(f"[index] candidates: {len(candidates)}", flush=True)

    if args.dry_run:
        print("[index] dry-run — first 3 samples:")
        for key, name, text in candidates[:3]:
            print(f"  [{key[:16]}] [{name}] {text[:120]!r}")
        log.close()
        return

    pg = PgBridge()
    pg._ensure_conn()
    ingested = errors = 0

    for key, convo_name, text in candidates:
        try:
            if args.no_embed:
                atom_id = pg.gen_id(8)
                with pg.conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO opus_atoms (id, content, domain, depth, source_session)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (atom_id, text, DOMAIN, DEPTH, convo_name))
                pg.conn.commit()
            else:
                atom_id = pg.ingest_opus_atom(
                    content=text,
                    domain=DOMAIN,
                    depth=DEPTH,
                    source_session=convo_name,
                )

            log.execute(
                "INSERT OR IGNORE INTO indexed_messages (key, atom_id) VALUES (?, ?)",
                (key, atom_id),
            )
            ingested += 1

            if ingested % args.batch_size == 0:
                log.commit()
                print(f"[index] {ingested}/{len(candidates)} ingested  ({errors} errors)", flush=True)

        except Exception as e:
            errors += 1
            print(f"[index] ERROR [{key[:16]}]: {e}", flush=True)
            if errors > 50:
                print("[index] error threshold — stopping", flush=True)
                break

    log.commit()
    log.close()
    print(f"[index] done — {ingested} ingested, {errors} errors", flush=True)


if __name__ == "__main__":
    main()
