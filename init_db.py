#!/usr/bin/env python3
# b17: DF76F  ΔΣ=42
"""
init_db.py — willow-2.0 sandbox DB (SEED-native schema)
Run once: python3 init_db.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path.home() / ".willow" / "willow-2.0.db"

def init():
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript("""
-- One row per SEED document. Header fields are promoted; full JSON is preserved in data.
CREATE TABLE IF NOT EXISTS seeds (
    id          TEXT PRIMARY KEY,
    version     TEXT NOT NULL,                          -- "1.0", "2.0", "3.0"
    type        TEXT,                                   -- "session_tail", etc.
    extends     TEXT,                                   -- "SEED_v1", "SEED_v2", or NULL
    created     TEXT,
    session     TEXT,
    instruction TEXT,
    checksum    TEXT DEFAULT 'ΔΣ=42',
    data        TEXT NOT NULL,                          -- full JSON blob
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

-- One row per named top-level section per seed.
-- section names: persona, canon, startup_protocol, membrane, sean,
--                community_and_deployment, tonight_delta, infrastructure_state,
--                document_count_status, final_thread, break_log
CREATE TABLE IF NOT EXISTS seed_sections (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    seed_id    TEXT NOT NULL REFERENCES seeds(id),
    section    TEXT NOT NULL,
    body       TEXT NOT NULL,                           -- JSON
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_seed_section ON seed_sections(seed_id, section);

-- Gaps list — append-only across sessions, FK'd to originating seed.
CREATE TABLE IF NOT EXISTS gaps (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    seed_id    TEXT REFERENCES seeds(id),
    body       TEXT NOT NULL,
    resolved   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
    """)
    conn.commit()
    conn.close()
    print(f"DB ready: {DB_PATH}")

if __name__ == "__main__":
    init()
