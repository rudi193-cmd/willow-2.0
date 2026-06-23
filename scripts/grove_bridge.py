#!/usr/bin/env python3
# b17: 4E6C6  ΔΣ=42
"""
grove_bridge.py — Grove bus relay between two Postgres nodes.

Connects to two Grove instances via LISTEN/NOTIFY. When a bus message arrives
on one node that wasn't bridged, forwards it to the other.

Loop prevention: forwarded messages get correlation_id = BRIDGE:{src}:{id}.
The bridge skips any message whose correlation_id already starts with BRIDGE:.

Only bus-layer messages are forwarded — conversational messages stay local.

Usage:
    python3 scripts/grove_bridge.py --node-b 192.168.12.X

    BRIDGE_NODE_B=192.168.12.X python3 scripts/grove_bridge.py

Env:
    WILLOW_PG_DB      database name (default: willow_19)
    WILLOW_PG_USER    postgres user (default: $USER)
    BRIDGE_NODE_A     node A host (default: localhost)
    BRIDGE_NODE_B     node B host (required)
    BRIDGE_A_NAME     friendly name for node A (default: desktop)
    BRIDGE_B_NAME     friendly name for node B (default: thinkpad)
"""

import argparse
import logging
import os
import select
import sys

import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s %(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("grove-bridge")

DB      = os.environ.get("WILLOW_PG_DB", "willow_19")
PG_USER = os.environ.get("WILLOW_PG_USER", os.environ.get("USER", ""))

BRIDGE_PREFIX = "BRIDGE:"

# Forward these bus types across nodes. Plain EVENT to __all__ is conversational — stays local.
FORWARD_TYPES = {"COMMAND", "RESPONSE", "INTERRUPT", "HEARTBEAT", "ACK", "DATA", "SYNC"}


def connect(host: str, name: str) -> psycopg2.extensions.connection:
    # Use Unix socket for localhost (peer auth); TCP for remote hosts
    if host in ("localhost", "127.0.0.1", "::1"):
        conn = psycopg2.connect(dbname=DB, user=PG_USER)
    else:
        conn = psycopg2.connect(host=host, dbname=DB, user=PG_USER)
    conn.autocommit = True
    log.info(f"Connected to {name} ({host}/{DB})")
    return conn


def seed_cursor(cur) -> int:
    cur.execute("SELECT COALESCE(MAX(id),0) FROM grove.messages WHERE is_deleted=0")
    return cur.fetchone()[0]


def channel_name(cur, channel_id: int) -> str | None:
    cur.execute("SELECT name FROM grove.channels WHERE id=%s", (channel_id,))
    row = cur.fetchone()
    return row[0] if row else None


def get_or_create_channel(cur, name: str) -> int:
    cur.execute("SELECT id FROM grove.channels WHERE name=%s", (name,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO grove.channels(name, channel_type) VALUES (%s, 'group') RETURNING id",
        (name,),
    )
    return cur.fetchone()[0]


def fetch_bus_messages(cur, last_id: int) -> list:
    cur.execute(
        """
        SELECT id, channel_id, sender, content, message_type,
               to_agent, bus_type, priority, correlation_id, ttl
          FROM grove.messages
         WHERE is_deleted = 0
           AND id > %s
           AND (
               bus_type = ANY(%s)
               OR (bus_type = 'EVENT' AND to_agent != '__all__')
           )
           AND (correlation_id IS NULL OR correlation_id NOT LIKE %s)
         ORDER BY id ASC
         LIMIT 50
        """,
        (last_id, list(FORWARD_TYPES), BRIDGE_PREFIX + "%"),
    )
    return cur.fetchall()


def forward(src_cur, dst_cur, row: tuple, src_name: str) -> None:
    mid, ch_id, sender, content, msg_type, to_agent, bus_type, priority, corr_id, ttl = row

    ch_name = channel_name(src_cur, ch_id)
    if not ch_name:
        log.warning(f"Cannot resolve channel_id={ch_id} on {src_name} — skipping id={mid}")
        return

    dst_ch_id = get_or_create_channel(dst_cur, ch_name)

    bridge_corr = f"{BRIDGE_PREFIX}{src_name}:{mid}"
    if corr_id:
        bridge_corr = f"{bridge_corr}:{corr_id}"

    dst_cur.execute(
        """
        INSERT INTO grove.messages
            (channel_id, sender, content, message_type,
             to_agent, bus_type, priority, correlation_id, ttl)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (dst_ch_id, sender, content, msg_type, to_agent, bus_type, priority, bridge_corr, ttl),
    )
    log.info(f"  [{bus_type}] {src_name}::{ch_name} id={mid} → to={to_agent}")


def run(node_a_host: str, node_b_host: str, node_a_name: str, node_b_name: str) -> None:
    conn_a = connect(node_a_host, node_a_name)
    conn_b = connect(node_b_host, node_b_name)

    cur_a  = conn_a.cursor()
    cur_b  = conn_b.cursor()
    last_a = seed_cursor(cur_a)
    last_b = seed_cursor(cur_b)

    listen_a = conn_a.cursor()
    listen_b = conn_b.cursor()
    listen_a.execute("LISTEN grove_channel")
    listen_b.execute("LISTEN grove_channel")

    log.info(f"Bridge live — {node_a_name}(cursor={last_a}) ↔ {node_b_name}(cursor={last_b})")
    print(f"[grove-bridge] {node_a_name} ↔ {node_b_name} — forwarding bus layer", flush=True)

    while True:
        select.select([conn_a, conn_b], [], [], 30)

        for conn in (conn_a, conn_b):
            try:
                conn.poll()
                while conn.notifies:
                    conn.notifies.pop()
            except psycopg2.OperationalError as e:
                log.error(f"Connection lost: {e}")
                sys.exit(1)

        # A → B
        for row in fetch_bus_messages(cur_a, last_a):
            if row[0] > last_a:
                last_a = row[0]
            forward(cur_a, cur_b, row, node_a_name)

        # B → A
        for row in fetch_bus_messages(cur_b, last_b):
            if row[0] > last_b:
                last_b = row[0]
            forward(cur_b, cur_a, row, node_b_name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Grove bus bridge between two Postgres nodes")
    parser.add_argument("--node-a",      default=os.environ.get("BRIDGE_NODE_A", "localhost"))
    parser.add_argument("--node-b",      default=os.environ.get("BRIDGE_NODE_B", ""))
    parser.add_argument("--node-a-name", default=os.environ.get("BRIDGE_A_NAME", "desktop"))
    parser.add_argument("--node-b-name", default=os.environ.get("BRIDGE_B_NAME", "thinkpad"))
    args = parser.parse_args()

    if not args.node_b:
        parser.error("--node-b is required (or set BRIDGE_NODE_B env var)")

    run(args.node_a, args.node_b, args.node_a_name, args.node_b_name)


if __name__ == "__main__":
    main()
