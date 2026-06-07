#!/usr/bin/env python3
# b17: ORC20  ΔΣ=42
"""
orchestrator.py — session context injector for willow-2.0.

Reads last session summary from the sessions table and prints it once
per boot-session. Subsequent prompts are silent.

Keyed on the sessions row id — resets automatically when session_close.py
writes a new row (new id = new content to show).

Also reads transcript depth from Claude Code hook stdin and injects a
<context-depth> warning when usage crosses the threshold, prompting the
agent to call context_save before the window fills.
"""
import json
import sqlite3
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from willow.fylgja.willow_home import willow_home

DB_PATH   = willow_home(_REPO) / "willow-2.0.db"
FLAG_FILE = Path("/tmp/willow-orchestrator-shown")

# Trigger at 70% of ~180k-token effective context window
_TOKEN_THRESHOLD = 126_000
_CHARS_PER_TOKEN = 4


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


def estimate_depth(transcript_path: str) -> int:
    """Return estimated token count from transcript JSONL. Returns 0 on failure."""
    try:
        text = Path(transcript_path).read_text(errors="ignore")
        return len(text) // _CHARS_PER_TOKEN
    except Exception:
        return 0


def main() -> int:
    # Read hook stdin (Claude Code passes JSON for UserPromptSubmit)
    hook_data: dict = {}
    try:
        raw = sys.stdin.read()
        if raw.strip():
            hook_data = json.loads(raw)
    except Exception:
        pass

    # Context depth check
    transcript_path = hook_data.get("transcript_path", "")
    if transcript_path:
        estimated_tokens = estimate_depth(transcript_path)
        if estimated_tokens >= _TOKEN_THRESHOLD:
            depth_pct = min(100, int(estimated_tokens / 180_000 * 100))
            print(
                f"<context-depth pct=\"{depth_pct}\" tokens_est=\"{estimated_tokens}\">"
                f"Context is {depth_pct}% full. Call context_save now with a structured summary "
                f"of current session state (decisions made, tasks in progress, key facts). "
                f"Keep working after saving — do not pause or ask permission."
                f"</context-depth>"
            )

    # Session summary injection (once per session)
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

    print("<orchestrator>")
    print(f"Last session: {created_at} (id={sid})")
    print(summary)
    print("</orchestrator>")
    mark_shown(sid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
