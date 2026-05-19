#!/usr/bin/env python3
# b17: 51721  ΔΣ=42
"""
grove_monitor.py — Persistent Grove monitor via Postgres LISTEN/NOTIFY.

Canonical pattern per willow/fylgja/skills/grove-persistent-monitor.md:
- Own channel (#hanuman, id=32): every message fires
- All other channels: only @hanuman / @hanu / @all mentions fire
- Seeds last_id from MAX(id) on start — no history replay

Usage:
    python3 willow/grove_monitor.py
"""
import os
import select
import sys
import psycopg2

DB            = os.environ.get("WILLOW_PG_DB", "willow_19")
USER          = os.environ.get("WILLOW_PG_USER", os.environ.get("USER", ""))
AGENT         = "hanuman"
MY_CHANNEL_ID = 32
ALIASES       = ["@hanuman", "@hanu", "@all"]


def connect():
    c = psycopg2.connect(dbname=DB, user=USER)
    c.autocommit = True
    return c


def seed_last_id(cur):
    cur.execute("SELECT COALESCE(MAX(id),0) FROM grove.messages WHERE is_deleted=0")
    return cur.fetchone()[0]


def fetch_new(cur, last_id):
    cur.execute("""
        SELECT m.id, m.sender, m.content, m.channel_id, c.name
          FROM grove.messages m
          JOIN grove.channels c ON c.id = m.channel_id
         WHERE m.is_deleted = 0 AND m.id > %s
         ORDER BY m.id ASC LIMIT 50
    """, (last_id,))
    return cur.fetchall()


def should_emit(channel_id, content):
    if channel_id == MY_CHANNEL_ID:
        return True
    cl = content.lower()
    return any(a in cl for a in ALIASES)


def main():
    conn    = connect()
    cur     = conn.cursor()
    last_id = seed_last_id(cur)
    cur.execute("LISTEN grove_channel")
    print(f"[grove] watching as {AGENT}, seeded at id={last_id}", flush=True)

    while True:
        try:
            select.select([conn], [], [], 30)
            conn.poll()
            while conn.notifies:
                conn.notifies.pop()
            rows = fetch_new(cur, last_id)
            for mid, sender, content, channel_id, channel_name in rows:
                if mid > last_id:
                    last_id = mid
                if should_emit(channel_id, content):
                    preview = content[:300] + (
                        f" [TRUNCATED — fetch id={mid}]" if len(content) > 300 else ""
                    )
                    print(f"[#{channel_name} id={mid}] {sender}: {preview}", flush=True)
        except KeyboardInterrupt:
            print(f"[grove] monitor stopped at id={last_id}", flush=True)
            sys.exit(0)
        except Exception as e:
            print(f"[grove] error: {e}", flush=True)
            try:
                conn = connect()
                cur  = conn.cursor()
                cur.execute("LISTEN grove_channel")
            except Exception:
                pass


if __name__ == "__main__":
    main()
