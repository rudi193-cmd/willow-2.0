#!/usr/bin/env python3
"""
Session content extractor — pulls user messages from all JSONL sessions and
inserts them as KB atoms in public.knowledge (project='sessions').
Feeds the existing embed backfill pipeline for semantic search.
"""
import json
import os
import glob
import hashlib
from datetime import datetime, timezone
from pathlib import Path

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    raise

DB_PARAMS = {
    "dbname": "willow_20",
    "user": os.environ.get("USER", ""),
}

SESSION_ROOT = str(Path.home() / ".claude" / "projects")

MIN_LENGTH = 30

SKIP_PREFIXES = (
    "Tool loaded.",
    "[SYSTEM NOTIFICATION",
    "This is an automated",
    "Summary:",
    "The conversation was summarized",
)


def should_skip(text: str) -> bool:
    if len(text) < MIN_LENGTH:
        return True
    t = text.strip()
    for prefix in SKIP_PREFIXES:
        if t.startswith(prefix):
            return True
    return False


def extract_user_messages(filepath: str) -> list[dict]:
    session_id = Path(filepath).stem
    project_dir = Path(filepath).parent.name
    messages = []

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if obj.get("type") == "user":
                    msg = obj.get("message", {})
                    if msg.get("role") == "user":
                        content = msg.get("content", "")
                        if isinstance(content, str):
                            text = content.strip()
                            if not should_skip(text):
                                ts = obj.get("timestamp", "")
                                date_str = ts[:10] if ts else "unknown"
                                msg_uuid = obj.get("uuid", "")
                                # Stable ID: hash of session_id + message uuid
                                raw_key = f"{session_id}:{msg_uuid or text[:100]}"
                                atom_id = "S" + hashlib.sha1(raw_key.encode()).hexdigest()[:7].upper()
                                messages.append({
                                    "atom_id": atom_id,
                                    "session_id": session_id,
                                    "project_dir": project_dir,
                                    "text": text,
                                    "timestamp": ts,
                                    "date_str": date_str,
                                })
    except Exception as e:
        print(f"  ERROR reading {filepath}: {e}")

    return messages


def make_title(msg: dict) -> str:
    snippet = msg["text"].replace("\n", " ").replace("\r", "")[:80]
    return f"Session {msg['date_str']} [{msg['session_id'][:8]}]: {snippet}"


def get_existing_ids(conn) -> set:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM public.knowledge WHERE project='sessions'")
        return {row[0] for row in cur.fetchall()}


def bulk_insert(conn, messages: list[dict], existing_ids: set) -> tuple[int, int]:
    inserted = 0
    skipped = 0
    now = datetime.now(timezone.utc)

    batch = []
    with conn.cursor() as cur:
        for msg in messages:
            if msg["atom_id"] in existing_ids:
                skipped += 1
                continue

            title = make_title(msg)
            summary = msg["text"]
            content_json = json.dumps({
                "source_id": msg["session_id"],
                "project_dir": msg["project_dir"],
                "message_date": msg["date_str"],
            })

            ts_str = msg["timestamp"]
            if ts_str:
                try:
                    created_at = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except Exception:
                    created_at = now
            else:
                created_at = now

            batch.append((
                msg["atom_id"],
                "sessions",          # project (domain)
                created_at,          # valid_at
                None,                # invalid_at
                created_at,          # created_at
                title,
                summary,
                content_json,        # content jsonb
                "session",           # source_type
                "general",           # category
                None,                # embedding (NULL — backfill will populate)
            ))
            existing_ids.add(msg["atom_id"])

            if len(batch) >= 500:
                _flush(cur, batch)
                conn.commit()
                inserted += len(batch)
                print(f"  +{inserted} atoms so far...", flush=True)
                batch = []

        if batch:
            _flush(cur, batch)
            conn.commit()
            inserted += len(batch)

    return inserted, skipped


def _flush(cur, batch):
    psycopg2.extras.execute_values(cur, """
        INSERT INTO public.knowledge
            (id, project, valid_at, invalid_at, created_at, title, summary, content,
             source_type, category, embedding)
        VALUES %s
        ON CONFLICT (id) DO NOTHING
    """, batch, template="(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)")


def main():
    print(f"[extractor] Scanning {SESSION_ROOT}...")
    files = glob.glob(os.path.join(SESSION_ROOT, "**", "*.jsonl"), recursive=True)
    print(f"[extractor] Found {len(files)} files.")

    conn = psycopg2.connect(**DB_PARAMS)
    print("[extractor] Loading existing session atom IDs...")
    existing_ids = get_existing_ids(conn)
    print(f"[extractor] {len(existing_ids)} existing (will skip).")

    all_messages = []
    for i, fp in enumerate(files):
        if (i + 1) % 50 == 0:
            print(f"  extracting {i+1}/{len(files)}...", flush=True)
        msgs = extract_user_messages(fp)
        all_messages.extend(msgs)

    print(f"[extractor] {len(all_messages)} user messages extracted.")
    print("[extractor] Inserting into public.knowledge...")
    inserted, skipped = bulk_insert(conn, all_messages, existing_ids)
    conn.close()

    print(f"[extractor] Done. {inserted} new atoms, {skipped} skipped.")
    return inserted


if __name__ == "__main__":
    main()
