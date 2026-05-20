#!/usr/bin/env python3
# b17: DF76F  ΔΣ=42
"""
init_db.py — willow-2.0 sandbox DB (records/notes/sessions schema)
Run once: python3 init_db.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path.home() / ".willow" / "willow-2.0.db"

def init():
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript("""
-- General-purpose key-value store. SOIL analogue without MCP overhead.
CREATE TABLE IF NOT EXISTS records (
    id          TEXT PRIMARY KEY,
    collection  TEXT NOT NULL,
    data        TEXT NOT NULL,                          -- JSON
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_records_collection
    ON records (collection);

-- Freeform scratchpad. Lightweight atom store, no embedding required.
CREATE TABLE IF NOT EXISTS notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    body       TEXT NOT NULL,
    tags       TEXT,                                    -- comma-separated
    created_at TEXT DEFAULT (datetime('now'))
);

-- Per-session handoff surface. frank_ledger analogue, no Postgres or hash chain.
CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT PRIMARY KEY,
    summary    TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Persona seed sections. Populated by ingest_seeds.py; read by persona.py.
CREATE TABLE IF NOT EXISTS seed_sections (
    seed_id    TEXT NOT NULL,
    section    TEXT NOT NULL,
    body       TEXT NOT NULL,            -- JSON
    PRIMARY KEY (seed_id, section)
);
    """)
    conn.commit()
    conn.close()
    print(f"DB ready: {DB_PATH}")

if __name__ == "__main__":
    init()
