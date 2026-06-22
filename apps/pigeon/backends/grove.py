"""
Grove internal mail backend for Pigeon.
b17: 1284BC7D  ΔΣ=42

Reads Grove messages via grove_db (direct Postgres).
Channels surface as "mailboxes" — each channel is a perch thread list.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

from apps.pigeon.backends.base import MailBackend

_GROVE_ROOT = Path(os.environ.get("GROVE_ROOT", Path(__file__).parent.parent.parent.parent / "safe-app-willow-grove"))
if _GROVE_ROOT.exists() and str(_GROVE_ROOT) not in sys.path:
    sys.path.insert(0, str(_GROVE_ROOT))


class GroveBackend(MailBackend):
    def list_threads(self) -> list[dict]:
        try:
            import grove_db
            conn = grove_db.get_connection()
            cur  = conn.cursor()
            cur.execute("""
                SELECT m.id, m.sender, m.content, m.created_at, c.name
                FROM grove.messages m
                JOIN grove.channels c ON c.id = m.channel_id
                WHERE m.is_deleted = 0
                ORDER BY m.created_at DESC
                LIMIT 50
            """)
            rows = cur.fetchall()
            return [
                {
                    "id":      str(row[0]),
                    "from":    row[1],
                    "subject": f"[#{row[4]}] {row[2][:60]}",
                    "date":    str(row[3])[:16],
                    "snippet": row[2][:120],
                }
                for row in rows
            ]
        except Exception as exc:
            return [{"id": "err", "from": "grove", "subject": str(exc), "date": "", "snippet": ""}]

    def get_thread(self, thread_id: str) -> str:
        try:
            import grove_db
            conn = grove_db.get_connection()
            cur  = conn.cursor()
            cur.execute(
                "SELECT sender, content, created_at FROM grove.messages WHERE id = %s",
                (int(thread_id),),
            )
            row = cur.fetchone()
            if not row:
                return "Message not found."
            return f"[bold]{row[0]}[/bold]  {row[2]}\n\n{row[1]}"
        except Exception as exc:
            return f"Error loading message: {exc}"
