#!/usr/bin/env python3
"""
Session indexer — parses all Claude Code JSONL session files and writes:
  - per-session metadata to public.session_index
  - per-turn user messages to public.session_messages
Both tables live in willow_20.
"""
import json
import os
import glob
from datetime import datetime
from pathlib import Path

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("psycopg2 not installed — run: pip install psycopg2-binary")
    raise

DB_PARAMS = {
    "dbname": "willow_20",
    "user": os.environ.get("USER", ""),
}

SESSION_ROOT = str(Path.home() / ".claude" / "projects")

# Minimum user message length to store (filters system-injected noise)
MIN_MSG_LENGTH = 8


def classify_tool(name: str) -> str:
    if name in ("Bash",):
        return "Bash"
    if name in ("Read",):
        return "Read"
    if name in ("Edit",):
        return "Edit"
    if name in ("Write",):
        return "Write"
    if name in ("Glob", "Grep"):
        return name
    if name.startswith("mcp__willow__"):
        return "MCP_willow"
    if name.startswith("mcp__grove__") or name.startswith("mcp__claude_ai_Grove__"):
        return "MCP_grove"
    if name.startswith("mcp__"):
        return "MCP_other"
    if name in ("Agent",):
        return "Agent"
    if name in ("TaskCreate", "TaskUpdate", "TaskGet", "TaskList", "TaskOutput"):
        return "Task"
    return "other"


def extract_text(content) -> str:
    """Extract plain text from either a string or a list of content blocks."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                t = block.get("text", "").strip()
                if t:
                    parts.append(t)
        return "\n".join(parts).strip()
    return ""


def parse_session(filepath: str) -> dict | None:
    """Parse a JSONL session file and return metadata + messages."""
    session_id = Path(filepath).stem
    project_dir = Path(filepath).parent.name
    file_size = os.path.getsize(filepath)

    timestamps = []
    user_messages = []
    tool_calls = {}
    compaction_count = 0
    turn_index = 0

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

                ts = obj.get("timestamp")
                if ts:
                    timestamps.append(ts)

                obj_type = obj.get("type", "")

                if obj_type == "user":
                    msg = obj.get("message", {})
                    if msg.get("role") == "user":
                        text = extract_text(msg.get("content", ""))
                        # Skip system-injected blocks (hook output, task notifications, etc.)
                        if (
                            text
                            and len(text) >= MIN_MSG_LENGTH
                            and not text.startswith("[BOOT-REQUIRED]")
                            and not text.startswith("<task-notification>")
                            and not text.startswith("<local-command-caveat>")
                            and not text.startswith("This session is being continued")
                        ):
                            user_messages.append({
                                "session_id": session_id,
                                "turn_index": turn_index,
                                "timestamp": ts,
                                "text": text,
                                "uuid": obj.get("uuid", ""),
                                "project_dir": project_dir,
                            })
                            turn_index += 1

                elif obj_type == "assistant":
                    msg = obj.get("message", {})
                    content = msg.get("content", [])
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "tool_use":
                                name = item.get("name", "unknown")
                                cat = classify_tool(name)
                                tool_calls[cat] = tool_calls.get(cat, 0) + 1

                elif obj_type == "system":
                    if obj.get("subtype") == "compact_boundary":
                        compaction_count += 1

    except Exception as e:
        print(f"  ERROR parsing {filepath}: {e}")
        return None

    if not timestamps:
        return None

    timestamps.sort()
    started_at = timestamps[0]
    ended_at = timestamps[-1]

    try:
        t0 = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
        duration_minutes = (t1 - t0).total_seconds() / 60
    except Exception:
        duration_minutes = 0.0

    return {
        "session_id": session_id,
        "project_dir": project_dir,
        "file_path": filepath,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_minutes": round(duration_minutes, 2),
        "turn_count": turn_index,
        "user_message_count": len(user_messages),
        "tool_calls": json.dumps(tool_calls),
        "compaction_count": compaction_count,
        "file_size_bytes": file_size,
        "user_messages": user_messages,
    }


def create_tables(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.session_index (
                session_id          TEXT PRIMARY KEY,
                project_dir         TEXT,
                file_path           TEXT,
                started_at          TIMESTAMPTZ,
                ended_at            TIMESTAMPTZ,
                duration_minutes    FLOAT,
                turn_count          INT,
                user_message_count  INT,
                tool_calls          JSONB,
                compaction_count    INT,
                file_size_bytes     BIGINT,
                indexed_at          TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.session_messages (
                id              BIGSERIAL PRIMARY KEY,
                session_id      TEXT NOT NULL REFERENCES public.session_index(session_id) ON DELETE CASCADE,
                turn_index      INT NOT NULL,
                timestamp       TIMESTAMPTZ,
                text            TEXT NOT NULL,
                uuid            TEXT,
                project_dir     TEXT,
                indexed_at      TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (session_id, turn_index)
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS session_messages_text_idx
            ON public.session_messages USING gin(to_tsvector('english', text))
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS session_messages_project_idx
            ON public.session_messages (project_dir, timestamp DESC)
        """)
        conn.commit()
    print("[index] Tables session_index + session_messages ready.")


def upsert_sessions(conn, sessions: list[dict]):
    inserted = skipped = 0
    with conn.cursor() as cur:
        for s in sessions:
            try:
                cur.execute("""
                    INSERT INTO public.session_index
                        (session_id, project_dir, file_path, started_at, ended_at,
                         duration_minutes, turn_count, user_message_count, tool_calls,
                         compaction_count, file_size_bytes)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (session_id) DO UPDATE SET
                        file_path           = EXCLUDED.file_path,
                        started_at          = EXCLUDED.started_at,
                        ended_at            = EXCLUDED.ended_at,
                        duration_minutes    = EXCLUDED.duration_minutes,
                        turn_count          = EXCLUDED.turn_count,
                        user_message_count  = EXCLUDED.user_message_count,
                        tool_calls          = EXCLUDED.tool_calls,
                        compaction_count    = EXCLUDED.compaction_count,
                        file_size_bytes     = EXCLUDED.file_size_bytes,
                        indexed_at          = NOW()
                """, (
                    s["session_id"], s["project_dir"], s["file_path"],
                    s["started_at"], s["ended_at"], s["duration_minutes"],
                    s["turn_count"], s["user_message_count"], s["tool_calls"],
                    s["compaction_count"], s["file_size_bytes"],
                ))
                inserted += 1
            except Exception as e:
                print(f"  UPSERT ERROR {s['session_id']}: {e}")
                skipped += 1
        conn.commit()
    return inserted, skipped


def upsert_messages(conn, sessions: list[dict]):
    inserted = skipped = 0
    with conn.cursor() as cur:
        for s in sessions:
            for m in s.get("user_messages", []):
                try:
                    cur.execute("""
                        INSERT INTO public.session_messages
                            (session_id, turn_index, timestamp, text, uuid, project_dir)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (session_id, turn_index) DO UPDATE SET
                            text       = EXCLUDED.text,
                            timestamp  = EXCLUDED.timestamp,
                            indexed_at = NOW()
                    """, (
                        m["session_id"], m["turn_index"], m["timestamp"],
                        m["text"], m["uuid"], m["project_dir"],
                    ))
                    inserted += 1
                except Exception as e:
                    print(f"  MSG UPSERT ERROR {m['session_id']}:{m['turn_index']}: {e}")
                    skipped += 1
        conn.commit()
    return inserted, skipped


def main():
    print(f"[index] Scanning {SESSION_ROOT}...")
    files = glob.glob(os.path.join(SESSION_ROOT, "**", "*.jsonl"), recursive=True)
    print(f"[index] Found {len(files)} JSONL files.")

    conn = psycopg2.connect(**DB_PARAMS)
    create_tables(conn)

    sessions = []
    errors = 0
    for i, fp in enumerate(files):
        if (i + 1) % 50 == 0:
            print(f"  parsing {i+1}/{len(files)}...", flush=True)
        result = parse_session(fp)
        if result:
            sessions.append(result)
        else:
            errors += 1

    print(f"[index] Parsed {len(sessions)} sessions ({errors} errors). Upserting...")
    ins_s, skip_s = upsert_sessions(conn, sessions)
    ins_m, skip_m = upsert_messages(conn, sessions)
    conn.close()

    total_msgs = sum(len(s["user_messages"]) for s in sessions)
    print(f"[index] Sessions: {ins_s} upserted, {skip_s} errors.")
    print(f"[index] Messages: {ins_m}/{total_msgs} upserted, {skip_m} errors.")
    return sessions


if __name__ == "__main__":
    sessions = main()
    sessions.sort(key=lambda s: s["file_size_bytes"], reverse=True)
    print("\n[index] Top 10 by file size:")
    for s in sessions[:10]:
        mb = s["file_size_bytes"] / 1024 / 1024
        print(f"  {s['project_dir'][:30]}/{s['session_id'][:8]}  {mb:.1f}MB  {s['turn_count']} turns  {s['duration_minutes']:.0f}min  msgs={s['user_message_count']}")
