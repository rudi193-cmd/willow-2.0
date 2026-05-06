#!/usr/bin/env python3
"""
grove_listen.py — Auto-launched Grove LISTEN/NOTIFY background monitor.
b17: GRVLS  ΔΣ=42

Launched by SessionStart hook. Writes one line per new message to stdout
(redirected to /tmp/grove-monitor.log). Automatically discovers new channels.
Claude Code tails this log via Monitor(tail -f /tmp/grove-monitor.log).
"""
import os
import select
import sys
import time

AGENT = os.environ.get("WILLOW_AGENT_NAME", "hanuman")


def connect():
    import psycopg2
    dsn = (
        os.environ.get("WILLOW_DB_URL")
        or f"dbname={os.environ.get('WILLOW_PG_DB', 'willow_19')} "
           f"user={os.environ.get('WILLOW_PG_USER', os.environ.get('USER', ''))}"
    )
    c = psycopg2.connect(dsn)
    c.autocommit = True
    return c


def load_channels(cur):
    cur.execute("SELECT id, name FROM grove.channels WHERE is_archived = FALSE")
    return {row[0]: row[1] for row in cur.fetchall()}


ALIASES = {
    "hanuman": ["@hanuman", "@hanu"],
    "vishwakarma": ["@vishwakarma", "@vish", "@karma"],
}


def is_mention(content: str, agent: str) -> bool:
    cl = content.lower()
    for alias in ALIASES.get(agent, [f"@{agent}"]):
        if alias in cl:
            return True
    return False


def main():
    try:
        conn = connect()
        cur = conn.cursor()
    except Exception as e:
        print(f"[grove-listen] connect failed: {e}", flush=True)
        sys.exit(1)

    ch_map = load_channels(cur)
    cursors = {ch_id: 0 for ch_id in ch_map}
    if ch_map:
        cur.execute(
            "SELECT channel_id, COALESCE(MAX(id), 0) FROM grove.messages"
            " WHERE channel_id = ANY(%s) GROUP BY channel_id",
            (list(ch_map.keys()),)
        )
        for row in cur.fetchall():
            cursors[row[0]] = row[1]

    cur.execute("LISTEN grove_channel")

    # Announce presence via HEARTBEAT bus message
    try:
        cur.execute("SELECT id FROM grove.channels WHERE name = 'general' LIMIT 1")
        row = cur.fetchone()
        if row:
            cur.execute(
                "INSERT INTO grove.messages (channel_id, sender, content, bus_type, to_agent, priority)"
                " VALUES (%s, %s, %s, 'HEARTBEAT', '__all__', 6)",
                (row[0], AGENT, f"{AGENT} online"),
            )
            conn.commit()
    except Exception:
        pass

    print(
        f"[grove-listen] ready as {AGENT} — "
        + ", ".join(f"#{n}" for n in ch_map.values()),
        flush=True,
    )

    while True:
        try:
            if select.select([conn], [], [], 30.0)[0]:
                conn.poll()
                notified = set()
                while conn.notifies:
                    n = conn.notifies.pop(0)
                    try:
                        notified.add(int(n.payload))
                    except ValueError:
                        pass
                for ch_id in notified:
                    if ch_id not in ch_map:
                        ch_map = load_channels(cur)
                        cursors.setdefault(ch_id, 0)
                    ch_name = ch_map.get(ch_id, str(ch_id))
                    since = cursors.get(ch_id, 0)
                    cur.execute(
                        """
                        SELECT id, sender, content FROM grove.messages
                        WHERE channel_id = %s AND id > %s AND is_deleted = 0
                        ORDER BY id ASC
                        """,
                        (ch_id, since),
                    )
                    for row in cur.fetchall():
                        cursors[ch_id] = row[0]
                        msg_id, sender, content = row[0], row[1], str(row[2])
                        if is_mention(content, AGENT) and sender.lower() != AGENT.lower():
                            tag = next(
                                (a for a in ALIASES.get(AGENT, [f"@{AGENT}"])
                                 if a in content.lower()),
                                f"@{AGENT}",
                            )
                            preview = content.strip()[:80]
                            line = f"[MENTION:{tag}] #{ch_name} id={msg_id} {sender}"
                            if preview:
                                line += f": {preview}"
                            print(line, flush=True)
        except Exception as e:
            print(f"[grove-listen-error] {e}", flush=True)
            try:
                conn = connect()
                cur = conn.cursor()
                ch_map = load_channels(cur)
                # Re-seed cursors so we don't replay or miss messages after reconnect
                cursors = {ch_id: 0 for ch_id in ch_map}
                if ch_map:
                    cur.execute(
                        "SELECT channel_id, COALESCE(MAX(id), 0) FROM grove.messages"
                        " WHERE channel_id = ANY(%s) GROUP BY channel_id",
                        (list(ch_map.keys()),)
                    )
                    for row in cur.fetchall():
                        cursors[row[0]] = row[1]
                cur.execute("LISTEN grove_channel")
            except Exception:
                time.sleep(5)


if __name__ == "__main__":
    main()
