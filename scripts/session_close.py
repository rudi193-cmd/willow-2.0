#!/usr/bin/env python3
# b17: SC220  ΔΣ=42
"""
session_close.py — write session summary to sessions table at close time.

Finds the most recently modified JSONL in the Claude sessions dir,
pulls atoms from records for that session, and writes a summary row
to the sessions table so the next session's orchestrator has context.

Wire as a Stop hook in .claude/settings.json.
"""
import json
import sqlite3
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from willow.fylgja.willow_home import willow_home

_REPO_SLUG   = str(Path(__file__).parent.resolve()).replace("/", "-").replace(".", "-")
SESSIONS_DIR = Path.home() / ".claude" / "projects" / _REPO_SLUG
DB_PATH      = willow_home(_REPO) / "willow-2.0.db"


def latest_session_id() -> str | None:
    files = sorted(SESSIONS_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0].stem if files else None


def pull_atoms(conn: sqlite3.Connection, session_id: str) -> dict:
    meta = gap = None
    candidates = []

    cur = conn.execute(
        "SELECT data FROM records WHERE collection = 'atoms/session_metadata' AND data LIKE ?",
        (f'%{session_id}%',),
    )
    row = cur.fetchone()
    if row:
        meta = json.loads(row[0])

    cur = conn.execute(
        "SELECT data FROM records WHERE collection = 'atoms/session_gaps' AND data LIKE ?",
        (f'%{session_id}%',),
    )
    row = cur.fetchone()
    if row:
        gap = json.loads(row[0])

    cur = conn.execute(
        "SELECT json_extract(data, '$.summary') FROM records "
        "WHERE collection = 'atoms/session_semantic_candidates' AND data LIKE ? "
        "ORDER BY created_at DESC LIMIT 8",
        (f'%{session_id}%',),
    )
    candidates = [r[0] for r in cur.fetchall() if r[0]]

    # also pull smart_home / ledger_design atoms written this session
    cur = conn.execute(
        "SELECT collection, json_extract(data,'$.title'), json_extract(data,'$.summary') "
        "FROM records WHERE collection NOT LIKE 'atoms/%' ORDER BY created_at DESC LIMIT 10"
    )
    domain_atoms = [(r[0], r[1] or '', r[2] or '') for r in cur.fetchall()]

    return {"meta": meta, "gap": gap, "candidates": candidates, "domain": domain_atoms}


def build_summary(session_id: str, atoms: dict) -> str:
    lines = []

    meta = atoms.get("meta", {})
    if meta:
        payload = meta.get("payload", meta)
        counts = payload.get("counts", {})
        tw = payload.get("time_window", {})
        lines.append(f"Session: {session_id}")
        if tw.get("first_timestamp"):
            lines.append(f"Time: {tw['first_timestamp'][:16]} → {(tw.get('last_timestamp') or '')[:16]}")
        lines.append(f"Tool calls: {counts.get('tool_calls', '?')} | Hook errors: {payload.get('derived_signals', {}).get('hook_non_blocking_error_count', 0)}")

    gap = atoms.get("gap", {})
    if gap:
        payload = gap.get("payload", gap)
        gaps = payload.get("gaps", [])
        if gaps:
            lines.append(f"Gaps: {'; '.join(gaps)}")

    domain = atoms.get("domain", [])
    if domain:
        lines.append("Built:")
        for collection, title, summary in domain[:6]:
            lines.append(f"  [{collection}] {title} — {summary[:80]}")

    candidates = atoms.get("candidates", [])
    if candidates:
        lines.append("Key moments:")
        for c in candidates[:5]:
            lines.append(f"  - {c[:100]}")

    return "\n".join(lines) if lines else f"Session {session_id} — no structured atoms found."


def already_closed(conn: sqlite3.Connection, session_id: str) -> bool:
    cur = conn.execute("SELECT 1 FROM sessions WHERE id = ?", (session_id,))
    return cur.fetchone() is not None


def write_summary(conn: sqlite3.Connection, session_id: str, summary: str) -> None:
    conn.execute(
        "INSERT INTO sessions (id, summary) VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET summary=excluded.summary",
        (session_id, summary),
    )
    conn.commit()


def main() -> int:
    if not DB_PATH.exists():
        print("session_close.py: DB not found — skipping", file=sys.stderr)
        return 0

    session_id = latest_session_id()
    if not session_id:
        print("session_close.py: no session JSONL found — skipping", file=sys.stderr)
        return 0

    try:
        conn = sqlite3.connect(str(DB_PATH))

        if already_closed(conn, session_id):
            conn.close()
            return 0

        atoms   = pull_atoms(conn, session_id)
        summary = build_summary(session_id, atoms)
        write_summary(conn, session_id, summary)
        conn.close()
        print(f"session_close.py: wrote summary for {session_id}", file=sys.stderr)
    except Exception as e:
        print(f"session_close.py: error — {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
