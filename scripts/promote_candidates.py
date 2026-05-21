#!/usr/bin/env python3
"""
scripts/promote_candidates.py — Promote high-confidence semantic candidates to KB.

Reads needs_review atoms above a confidence threshold from willow-2.0.db,
ingests them into public.knowledge (Postgres), and marks them promoted.

Usage:
    python3 scripts/promote_candidates.py [--min-confidence 0.8] [--dry-run]
"""
import argparse
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.pg_bridge import PgBridge

DEFAULT_DB = Path(os.environ.get("WILLOW_20_DB", "~/.willow/willow-2.0.db")).expanduser()
AGENT = os.environ.get("WILLOW_AGENT_NAME", "hanuman")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_candidates(db_path: Path, min_conf: float) -> list[dict]:
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        """
        SELECT id, collection, data FROM records
        WHERE collection = 'atoms/session_semantic_candidates'
          AND json_extract(data, '$.needs_review') = 1
          AND json_extract(data, '$.confidence') >= ?
        ORDER BY json_extract(data, '$.confidence') DESC
        """,
        (min_conf,),
    ).fetchall()
    conn.close()
    return [{"id": r[0], "collection": r[1], **json.loads(r[2])} for r in rows]


def mark_promoted(db_path: Path, atom_ids: list[str]) -> None:
    conn = sqlite3.connect(str(db_path))
    for aid in atom_ids:
        data_row = conn.execute("SELECT data FROM records WHERE id = ?", (aid,)).fetchone()
        if not data_row:
            continue
        d = json.loads(data_row[0])
        d["needs_review"] = False
        d["promoted_at"] = _now()
        conn.execute(
            "UPDATE records SET data = ?, updated_at = datetime('now') WHERE id = ?",
            (json.dumps(d), aid),
        )
    conn.commit()
    conn.close()


def promote(candidates: list[dict], pg: PgBridge, dry_run: bool) -> list[str]:
    promoted_ids = []
    for c in candidates:
        payload = c.get("payload", {})
        evidence = payload.get("evidence", c.get("summary", ""))
        session_id = payload.get("session_id", "unknown")
        source_file = payload.get("source_file", "")
        conf = c.get("confidence", 0.0)

        title = f"[session:{session_id[:8]}] {evidence[:80]}"
        summary = evidence[:500]

        if dry_run:
            print(f"  DRY [{conf:.2f}] {title[:100]}")
            promoted_ids.append(c["id"])
            continue

        atom_id = str(uuid.uuid4())[:12]
        try:
            pg.conn.cursor().execute(
                """
                INSERT INTO public.knowledge
                  (id, title, summary, content, category, project,
                   valid_at, confidence, source_type)
                VALUES (%s, %s, %s, %s, %s, %s, now(), %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    atom_id,
                    title,
                    summary,
                    json.dumps({
                        "evidence": evidence,
                        "session_id": session_id,
                        "source_file": source_file,
                        "promoted_from": c.get("id", ""),
                        "agent": AGENT,
                    }),
                    "session_extract",
                    "willow-2.0",
                    conf,
                    "session_promote",
                ),
            )
            pg.conn.commit()
            print(f"  ✅ [{conf:.2f}] {title[:100]}")
            promoted_ids.append(c["id"])
        except Exception as e:
            pg.conn.rollback()
            print(f"  ❌ [{conf:.2f}] {title[:80]} — {e}")

    return promoted_ids


def main():
    ap = argparse.ArgumentParser(description="Promote high-confidence candidates to KB.")
    ap.add_argument("--db-path", default=str(DEFAULT_DB))
    ap.add_argument("--min-confidence", type=float, default=0.8)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db = Path(args.db_path).expanduser()
    candidates = load_candidates(db, args.min_confidence)
    print(f"Found {len(candidates)} candidates >= {args.min_confidence} confidence\n")

    if not candidates:
        return

    pg = PgBridge()
    promoted = promote(candidates, pg, args.dry_run)

    if not args.dry_run and promoted:
        mark_promoted(db, promoted)
        print(f"\nPromoted {len(promoted)} atoms to KB, marked promoted in local DB.")
    elif args.dry_run:
        print(f"\n{len(promoted)} would be promoted (dry run).")


if __name__ == "__main__":
    main()
