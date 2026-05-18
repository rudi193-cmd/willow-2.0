# b17: EVTLG  ΔΣ=42
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB = Path(__file__).parent / "events.db"


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB)
    con.execute("""
        CREATE TABLE IF NOT EXISTS device_events (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT    NOT NULL,
            device    TEXT    NOT NULL,
            action    TEXT    NOT NULL,
            ts        TEXT    NOT NULL
        )
    """)
    con.commit()
    return con


def log_event(device_id: str, device: str, action: str) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    con = _connect()
    con.execute(
        "INSERT INTO device_events (device_id, device, action, ts) VALUES (?, ?, ?, ?)",
        (device_id, device, action, ts),
    )
    con.commit()
    con.close()
