#!/usr/bin/env python3
# b17: DF76F  ΔΣ=42
"""
ingest_seeds.py — load OAKENSCROLL_SEED v1/v2/v3 into willow-2.0.db.
Run once: python3 ingest_seeds.py
"""
import json
import sqlite3
from pathlib import Path

DB_PATH    = Path.home() / ".willow" / "willow-2.0.db"
SEEDS_DIR  = Path.home() / "Downloads"

SEED_FILES = [
    ("OAKENSCROLL_SEED_v1",    SEEDS_DIR / "OAKENSCROLL_SEED.json",    "1.0", None),
    ("OAKENSCROLL_SEED_v2",    SEEDS_DIR / "OAKENSCROLL_SEED_v2.json", "2.0", "OAKENSCROLL_SEED_v1"),
    ("OAKENSCROLL_SEED_v3",    SEEDS_DIR / "OAKENSCROLL_SEED_v3.json", "3.0", "OAKENSCROLL_SEED_v2"),
]


def ingest(conn: sqlite3.Connection, seed_id: str, path: Path, version: str, extends: str | None):
    raw = json.loads(path.read_text())

    sections = [(k, v) for k, v in raw.items() if k != "seed"]
    for section, body in sections:
        conn.execute("""
            INSERT INTO seed_sections (seed_id, section, body)
            VALUES (?, ?, ?)
            ON CONFLICT(seed_id, section) DO UPDATE SET body=excluded.body
        """, (seed_id, section, json.dumps(body)))

    print(f"  {seed_id}: {len(sections)} sections")


def main():
    if not DB_PATH.exists():
        print(f"DB not found at {DB_PATH} — run init_db.py first")
        return

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")

    for seed_id, path, version, extends in SEED_FILES:
        if not path.exists():
            print(f"  SKIP {path.name} — file not found")
            continue
        ingest(conn, seed_id, path, version, extends)

    conn.commit()
    conn.close()
    print(f"Done → {DB_PATH}")


if __name__ == "__main__":
    main()
