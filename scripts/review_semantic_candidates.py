#!/usr/bin/env python3
"""
scripts/review_semantic_candidates.py — Print needs_review semantic candidates.

Usage:
    python3 scripts/review_semantic_candidates.py [--limit N] [--min-confidence F]
"""
import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from willow.fylgja.willow_home import willow_home

DEFAULT_DB = Path(
    os.environ.get("WILLOW_20_DB", str(willow_home(_REPO) / "willow-2.0.db"))
).expanduser()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-path", default=str(DEFAULT_DB))
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--min-confidence", type=float, default=0.0)
    ap.add_argument("--collection", default="atoms/session_semantic_candidates")
    ap.add_argument("--show-session", action="store_true")
    args = ap.parse_args()

    db = Path(args.db_path).expanduser()
    conn = sqlite3.connect(str(db))
    rows = conn.execute(
        """
        SELECT id, collection, data FROM records
        WHERE collection = ?
        ORDER BY json_extract(data, '$.confidence') DESC
        LIMIT ?
        """,
        (args.collection, args.limit),
    ).fetchall()
    conn.close()

    total = 0
    for row_id, collection, data_json in rows:
        d = json.loads(data_json)
        conf = d.get("confidence", 0)
        if conf < args.min_confidence:
            continue
        evidence = d.get("evidence", d.get("summary", ""))
        session_id = d.get("data", {}).get("session_id", "")
        needs_review = d.get("needs_review", True)
        marker = "🔲" if needs_review else "✅"
        session_str = f"  [{session_id[:8]}]" if args.show_session else ""
        print(f"{marker} [{conf:.2f}]{session_str} {evidence[:200]}")
        total += 1

    print(f"\n{total} candidates shown (db: {db})")


if __name__ == "__main__":
    main()
