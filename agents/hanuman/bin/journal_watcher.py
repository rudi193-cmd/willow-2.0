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

from core.pg_bridge import PgBridge
from core.grove_gate import assert_grove as _assert_grove_startup, grove_alive as _grove_alive

SAGA_TAG = "::saga"
POLL_INTERVAL = int(os.environ.get("JOURNAL_WATCHER_INTERVAL", "10"))  # seconds
_RESPONDER = os.path.join(os.path.dirname(__file__), "journal_responder.py")


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
        ids = [row[0] for row in cur.fetchall()]
    # Poll-only read: release the implicit transaction so the long-lived
    # PgBridge connection does not sit idle-in-transaction on the pool slot.
    try:
        pg.conn.rollback()
    except Exception:
        pass
    return ids


def _fire(entry_id: str) -> None:
    subprocess.Popen(
        [sys.executable, _RESPONDER, entry_id],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def watch() -> None:
    _assert_grove_startup("journal_watcher")

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

            try:
                from core.loop_heartbeat import write_throttled

                write_throttled("journal_watcher")
            except Exception:
                pass

            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("journal_watcher: stopped", flush=True)
    finally:
        pg.close()


if __name__ == "__main__":
    watch()
