#!/usr/bin/env python3
# b17: ORC20  ΔΣ=42
"""
orchestrator.py — session context injector for willow-2.0.

Reads last session summary from the sessions table and prints it once
per boot-session. Subsequent prompts are silent.

Keyed on the sessions row id — resets automatically when session_close.py
writes a new row (new id = new content to show).
"""
import sqlite3
import sys
from pathlib import Path

DB_PATH   = Path.home() / ".willow" / "willow-2.0.db"
FLAG_FILE = Path("/tmp/willow-orchestrator-shown")


def last_session(conn: sqlite3.Connection) -> tuple | None:
    cur = conn.execute(
        "SELECT id, summary, created_at FROM sessions ORDER BY created_at DESC LIMIT 1"
    )
    return cur.fetchone()


def already_shown(session_id: str) -> bool:
    if FLAG_FILE.exists():
        return FLAG_FILE.read_text().strip() == session_id
    return False


def mark_shown(session_id: str) -> None:
    FLAG_FILE.write_text(session_id)


def main() -> int:
    if not DB_PATH.exists():
        return 0

    try:
        conn = sqlite3.connect(str(DB_PATH))
        row = last_session(conn)
        conn.close()
    except Exception as e:
        print(f"# Orchestrator error: {e}", file=sys.stderr)
        return 0

    if not row:
        if not already_shown("__clean__"):
            print("<orchestrator>No prior session. Clean slate.</orchestrator>")
            mark_shown("__clean__")
        return 0

    sid, summary, created_at = row
    if already_shown(sid):
        return 0

    print(f"<orchestrator>")
    print(f"Last session: {created_at} (id={sid})")
    print(summary)
    print(f"</orchestrator>")
    mark_shown(sid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
