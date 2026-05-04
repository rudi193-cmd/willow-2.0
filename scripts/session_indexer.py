#!/usr/bin/env python3
"""
Session indexer — parses all Claude Code JSONL session files and writes
per-session metadata to public.session_index in willow_19.
"""
import json
import os
import glob
import re
from datetime import datetime, timezone
from pathlib import Path

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("psycopg2 not installed — run: pip install psycopg2-binary")
    raise

DB_PARAMS = {
    "dbname": "willow_19",
    "user": "sean-campbell",
}

SESSION_ROOT = "/home/sean-campbell/.claude/projects"

# Tool name classifier — maps MCP tool names to short categories
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


def parse_session(filepath: str) -> dict | None:
    """Parse a JSONL session file and return metadata dict."""
    session_id = Path(filepath).stem
    project_dir = Path(filepath).parent.name
    file_size = os.path.getsize(filepath)

    timestamps = []
    user_messages = []
    tool_calls = {}
    compaction_count = 0
    turn_count = 0

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

                # User turns
                if obj_type == "user":
                    msg = obj.get("message", {})
                    if msg.get("role") == "user":
                        content = msg.get("content", "")
                        if isinstance(content, str) and content.strip():
                            turn_count += 1
                            user_messages.append({
                                "text": content.strip(),
                                "timestamp": ts,
                                "uuid": obj.get("uuid"),
                            })

                # Assistant turns — count tool calls
                elif obj_type == "assistant":
                    msg = obj.get("message", {})
                    content = msg.get("content", [])
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "tool_use":
                                name = item.get("name", "unknown")
                                cat = classify_tool(name)
                                tool_calls[cat] = tool_calls.get(cat, 0) + 1

                # Compaction events
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
        "turn_count": turn_count,
        "user_message_count": len(user_messages),
        "tool_calls": json.dumps(tool_calls),
        "compaction_count": compaction_count,
        "file_size_bytes": file_size,
        "user_messages": user_messages,  # returned but not stored in index table
    }


def create_table(conn):
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
        conn.commit()
    print("[index] Table public.session_index ready.")


def upsert_sessions(conn, sessions: list[dict]):
    inserted = 0
    skipped = 0
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


def main():
    print(f"[index] Scanning {SESSION_ROOT}...")
    files = glob.glob(os.path.join(SESSION_ROOT, "**", "*.jsonl"), recursive=True)
    print(f"[index] Found {len(files)} JSONL files.")

    conn = psycopg2.connect(**DB_PARAMS)
    create_table(conn)

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
    inserted, skipped = upsert_sessions(conn, sessions)
    conn.close()

    print(f"[index] Done. {inserted} upserted, {skipped} errors.")
    return sessions


if __name__ == "__main__":
    sessions = main()
    # Print top 10 largest sessions
    sessions.sort(key=lambda s: s["file_size_bytes"], reverse=True)
    print("\n[index] Top 10 by file size:")
    for s in sessions[:10]:
        mb = s["file_size_bytes"] / 1024 / 1024
        print(f"  {s['project_dir']}/{s['session_id'][:8]}  {mb:.1f}MB  {s['turn_count']} turns  {s['duration_minutes']:.0f}min  compactions={s['compaction_count']}")
