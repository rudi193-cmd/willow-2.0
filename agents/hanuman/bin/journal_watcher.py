#!/usr/bin/env python3
"""
journal_watcher.py — Watch journal_entries for ::saga tag, fire responder.
b17: JOUR1  ΔΣ=42

Polls journal_entries for new entries that contain ::saga and haven't been
responded to yet. Fires journal_responder for each.

Run as a long-lived service (systemd or fleet).
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, _ROOT)

import urllib.request

from core.pg_bridge import PgBridge

SAGA_TAG = "::saga"
POLL_INTERVAL = int(os.environ.get("JOURNAL_WATCHER_INTERVAL", "10"))  # seconds
GROVE_URL = os.environ.get("GROVE_HEALTH_URL", "http://localhost:7777/health")
_RESPONDER = os.path.join(os.path.dirname(__file__), "journal_responder.py")

_GROVE_ERROR = """
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   GROVE IS NOT RUNNING                                           ║
║                                                                  ║
║   journal_watcher requires Grove to be active.                   ║
║   Start Grove before using the journal system.                   ║
║                                                                  ║
║   Check:  curl http://localhost:7777/health                      ║
║   Start:  ./willow.sh grove_serve   (or see grove startup docs)  ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
""".strip()


def _grove_alive() -> bool:
    try:
        with urllib.request.urlopen(GROVE_URL, timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def _pending_entries(pg: PgBridge) -> list[str]:
    """Return IDs of entries that contain ::saga and haven't been responded to."""
    with pg.conn.cursor() as cur:
        cur.execute(
            """
            SELECT id FROM journal_entries
            WHERE content ILIKE %s
              AND (metadata->>'saga_responded') IS DISTINCT FROM 'true'
            ORDER BY written_at ASC
            """,
            (f"%{SAGA_TAG}%",),
        )
        return [row[0] for row in cur.fetchall()]


def _fire(entry_id: str) -> None:
    subprocess.Popen(
        [sys.executable, _RESPONDER, entry_id],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def watch() -> None:
    if not _grove_alive():
        print(_GROVE_ERROR, file=sys.stderr, flush=True)
        sys.exit(1)

    print(f"journal_watcher: Grove up — polling every {POLL_INTERVAL}s for '{SAGA_TAG}'", flush=True)
    pg = PgBridge()
    try:
        while True:
            if not _grove_alive():
                print("journal_watcher: Grove went down — exiting", flush=True)
                break

            try:
                pending = _pending_entries(pg)
                for entry_id in pending:
                    print(f"journal_watcher: saga invited → {entry_id}", flush=True)
                    _fire(entry_id)
            except Exception as exc:
                print(f"journal_watcher: error — {exc}", file=sys.stderr, flush=True)
                try:
                    pg.close()
                except Exception:
                    pass
                pg = PgBridge()

            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("journal_watcher: stopped", flush=True)
    finally:
        pg.close()


if __name__ == "__main__":
    watch()
