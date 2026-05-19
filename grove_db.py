"""
grove_db.py — Grove workspace messaging database.
b17: WGRV1  ΔΣ=42

Self-contained — no sibling repo dependency. Pool, schema bootstrap,
LISTEN helper, and all channel/message/flag/bus/cursor operations.
"""

import os
import threading
from datetime import datetime
from typing import Optional, List, Dict, Any

_pool = None
_pool_lock = threading.Lock()

SCHEMA = "grove"

VALID_CHANNEL_TYPES = frozenset({"direct", "group", "persona", "broadcast"})
VALID_MESSAGE_TYPES = frozenset({"text", "system", "file_share", "reaction"})
VALID_FLAGS = frozenset({"needs-reply", "starred", "read", "urgent", "resolved"})

# Bus protocol constants
BUS_TYPES = frozenset({
    "COMMAND",    # instruct an agent to do something
    "RESPONSE",   # reply to a COMMAND
    "EVENT",      # something happened (fire and forget)
    "INTERRUPT",  # act immediately, preempt normal flow
    "HEARTBEAT",  # I am alive
    "ACK",        # I received and understood your message
    "DATA",       # bulk payload, routed to Kart/DMA layer
    "SYNC",       # synchronise state between agents
})

# Priority 0 = highest (INTERRUPT), 7 = lowest (DEBUG) — mirrors CAN bus
BUS_PRIORITY = {
    "INTERRUPT": 0, "URGENT": 1, "HIGH": 2, "NORMAL": 3,
    "LOW": 4, "BACKGROUND": 5, "HEARTBEAT": 6, "DEBUG": 7,
}
BUS_BROADCAST = "__all__"   # sentinel: message is addressed to every agent


def _get_pool():
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is None:
            import psycopg2.pool
            dsn = os.getenv("WILLOW_DB_URL", "")
            if not dsn:
                pg_db   = os.getenv("WILLOW_PG_DB", "willow_20")
                pg_user = os.getenv("WILLOW_PG_USER", os.environ.get("USER", ""))
                dsn = f"dbname={pg_db} user={pg_user}"
            _pool = psycopg2.pool.ThreadedConnectionPool(minconn=2, maxconn=10, dsn=dsn)
            _bootstrap_schema(_pool)
    return _pool


def _bootstrap_schema(pool):
    """Create grove schema idempotently on first pool use."""
    conn = pool.getconn()
    try:
        init_schema(conn)
    finally:
        pool.putconn(conn)


def get_connection():
    pool = _get_pool()
    conn = pool.getconn()
    try:
        conn.autocommit = False
        cur = conn.cursor()
        cur.execute(f"SET search_path = {SCHEMA}, public")
        cur.close()
        return conn
    except Exception:
        pool.putconn(conn)
        raise


def release_connection(conn):
    try:
        conn.rollback()
    except Exception:
        pass
    _get_pool().putconn(conn)


def listen_connection():
    """Open a dedicated autocommit connection for LISTEN — not from the pool.

    Callers own this connection for its lifetime and must close() it themselves.
    Pool connections must not be set autocommit; this is the correct path for
    any caller that needs LISTEN/NOTIFY.
    """
    import psycopg2
    pg_db   = os.getenv("WILLOW_PG_DB",   "willow_20")
    pg_user = os.getenv("WILLOW_PG_USER",  os.getenv("USER", ""))
    dsn     = os.getenv("WILLOW_DB_URL",   "") or f"dbname={pg_db} user={pg_user}"
    conn    = psycopg2.connect(dsn)
    conn.autocommit = True
    return conn


def init_schema(conn):
    """Create grove schema and tables. Idempotent."""
    cur = conn.cursor()
    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    cur.execute(f"SET search_path = {SCHEMA}, public")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            name            TEXT NOT NULL UNIQUE,
            channel_type    TEXT NOT NULL CHECK (channel_type IN ('direct','group','persona','broadcast')),
            description     TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_archived     BOOLEAN DEFAULT FALSE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            channel_id          BIGINT NOT NULL REFERENCES channels(id),
            sender              TEXT NOT NULL,
            content             TEXT NOT NULL,
            message_type        TEXT NOT NULL DEFAULT 'text'
                                    CHECK (message_type IN ('text','system','file_share','reaction')),
            reply_to_id         BIGINT REFERENCES messages(id),
            willow_indexed_at   TIMESTAMP,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_deleted          INTEGER DEFAULT 0
        )
    """)

    # Bus envelope columns — only ALTER when column genuinely absent (avoids ACCESS EXCLUSIVE lock)
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'grove' AND table_name = 'messages'
          AND column_name IN ('to_agent', 'bus_type', 'priority', 'correlation_id', 'ttl')
    """)
    existing_msg_cols = {r[0] for r in cur.fetchall()}
    for col_name, col_sql in [
        ("to_agent",       "ALTER TABLE messages ADD COLUMN to_agent TEXT DEFAULT '__all__'"),
        ("bus_type",       "ALTER TABLE messages ADD COLUMN bus_type TEXT DEFAULT 'EVENT'"),
        ("priority",       "ALTER TABLE messages ADD COLUMN priority INTEGER DEFAULT 3"),
        ("correlation_id", "ALTER TABLE messages ADD COLUMN correlation_id TEXT"),
        ("ttl",            "ALTER TABLE messages ADD COLUMN ttl INTEGER"),
    ]:
        if col_name not in existing_msg_cols:
            cur.execute(col_sql)

    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_channels_name ON channels (name)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_channels_type ON channels (channel_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages (channel_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages (sender)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_created ON messages (created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_reply ON messages (reply_to_id)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS message_flags (
            id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            message_id  BIGINT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
            sender      TEXT NOT NULL,
            flag        TEXT NOT NULL CHECK (flag IN ('needs-reply','starred','read','urgent','resolved')),
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (message_id, sender, flag)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_flags_message ON message_flags (message_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_flags_flag ON message_flags (flag)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_to_agent ON messages (to_agent)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_bus_type ON messages (bus_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_priority ON messages (priority)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_correlation ON messages (correlation_id) WHERE correlation_id IS NOT NULL")

    # Optional agent_name column on channels — only ALTER when absent (avoids ACCESS EXCLUSIVE lock)
    cur.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'grove' AND table_name = 'channels' AND column_name = 'agent_name'
    """)
    if not cur.fetchone():
        cur.execute("ALTER TABLE channels ADD COLUMN agent_name TEXT")

    # LISTEN/NOTIFY trigger — fires grove_channel notify on every new message
    cur.execute("""
        CREATE OR REPLACE FUNCTION grove_notify_message()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            PERFORM pg_notify('grove_channel', NEW.channel_id::text);
            RETURN NEW;
        END;
        $$
    """)
    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgname = 'trg_grove_notify'
            ) THEN
                CREATE TRIGGER trg_grove_notify
                AFTER INSERT ON messages
                FOR EACH ROW EXECUTE FUNCTION grove_notify_message();
            END IF;
        END
        $$
    """)

    conn.commit()


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------

def create_channel(conn, *, name: str, channel_type: str, description: str = None) -> Dict[str, Any]:
    if channel_type not in VALID_CHANNEL_TYPES:
        raise ValueError(f"channel_type must be one of {VALID_CHANNEL_TYPES}")
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO channels (name, channel_type, description)
        VALUES (%s, %s, %s)
        RETURNING id, name, channel_type, description, created_at, updated_at, is_archived
    """, (name, channel_type, description))
    row = cur.fetchone()
    cols = [d[0] for d in cur.description]
    conn.commit()
    return dict(zip(cols, row))


def list_channels(conn, include_archived: bool = False) -> List[Dict[str, Any]]:
    cur = conn.cursor()
    if include_archived:
        cur.execute("SELECT * FROM channels ORDER BY name")
    else:
        cur.execute("SELECT * FROM channels WHERE is_archived = FALSE ORDER BY name")
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in rows]


def get_channel(conn, channel_id: int) -> Optional[Dict[str, Any]]:
    cur = conn.cursor()
    cur.execute("SELECT * FROM channels WHERE id = %s", (channel_id,))
    row = cur.fetchone()
    if not row:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))


def archive_channel(conn, channel_id: int) -> bool:
    cur = conn.cursor()
    cur.execute(
        "UPDATE channels SET is_archived = TRUE, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (channel_id,)
    )
    conn.commit()
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

def send_message(conn, *, channel_id: int, sender: str, content: str,
                 message_type: str = "text", reply_to_id: int = None) -> Dict[str, Any]:
    if message_type not in VALID_MESSAGE_TYPES:
        raise ValueError(f"message_type must be one of {VALID_MESSAGE_TYPES}")
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO messages (channel_id, sender, content, message_type, reply_to_id)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, channel_id, sender, content, message_type, reply_to_id,
                  willow_indexed_at, created_at, is_deleted
    """, (channel_id, sender, content, message_type, reply_to_id))
    row = cur.fetchone()
    cols = [d[0] for d in cur.description]
    conn.commit()
    return dict(zip(cols, row))


def get_history(conn, channel_id: int, limit: int = 100,
                before_id: int = None, since_id: int = None) -> List[Dict[str, Any]]:
    """Return top-level messages (no replies).

    before_id: newest-first pagination (go backward).
    since_id:  forward polling — return messages with id > since_id, oldest first.
    """
    cur = conn.cursor()
    if since_id is not None:
        cur.execute("""
            SELECT * FROM messages
            WHERE channel_id = %s AND reply_to_id IS NULL AND is_deleted = 0 AND id > %s
            ORDER BY id ASC LIMIT %s
        """, (channel_id, since_id, limit))
    elif before_id:
        cur.execute("""
            SELECT * FROM messages
            WHERE channel_id = %s AND reply_to_id IS NULL AND is_deleted = 0 AND id < %s
            ORDER BY created_at DESC LIMIT %s
        """, (channel_id, before_id, limit))
    else:
        cur.execute("""
            SELECT * FROM messages
            WHERE channel_id = %s AND reply_to_id IS NULL AND is_deleted = 0
            ORDER BY created_at DESC LIMIT %s
        """, (channel_id, limit))
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in rows]


def get_thread(conn, parent_id: int) -> List[Dict[str, Any]]:
    """Return all replies to a message, oldest first."""
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM messages
        WHERE reply_to_id = %s AND is_deleted = 0
        ORDER BY created_at ASC
    """, (parent_id,))
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in rows]


def delete_message(conn, message_id: int) -> bool:
    cur = conn.cursor()
    cur.execute("UPDATE messages SET is_deleted = 1 WHERE id = %s", (message_id,))
    conn.commit()
    return cur.rowcount > 0


def search_messages(conn, query: str, channel_id: int = None) -> List[Dict[str, Any]]:
    cur = conn.cursor()
    if channel_id is not None:
        cur.execute("""
            SELECT * FROM messages
            WHERE content ILIKE %s AND channel_id = %s AND is_deleted = 0
            ORDER BY created_at DESC LIMIT 100
        """, (f"%{query}%", channel_id))
    else:
        cur.execute("""
            SELECT * FROM messages
            WHERE content ILIKE %s AND is_deleted = 0
            ORDER BY created_at DESC LIMIT 100
        """, (f"%{query}%",))
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in rows]


# ---------------------------------------------------------------------------
# Flags
# ---------------------------------------------------------------------------

def set_flag(conn, *, message_id: int, sender: str, flag: str) -> bool:
    if flag not in VALID_FLAGS:
        raise ValueError(f"flag must be one of {VALID_FLAGS}")
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO message_flags (message_id, sender, flag)
        VALUES (%s, %s, %s) ON CONFLICT (message_id, sender, flag) DO NOTHING
    """, (message_id, sender, flag))
    conn.commit()
    return cur.rowcount > 0


def clear_flag(conn, *, message_id: int, sender: str, flag: str) -> bool:
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM message_flags WHERE message_id = %s AND sender = %s AND flag = %s
    """, (message_id, sender, flag))
    conn.commit()
    return cur.rowcount > 0


def get_flags(conn, message_id: int) -> list[dict]:
    cur = conn.cursor()
    cur.execute("""
        SELECT sender, flag, created_at FROM message_flags WHERE message_id = %s ORDER BY created_at
    """, (message_id,))
    rows = cur.fetchall()
    return [{"sender": r[0], "flag": r[1], "created_at": r[2].isoformat() if r[2] else None}
            for r in rows]


def get_flagged(conn, flag: str, channel_id: int = None, limit: int = 50) -> list[dict]:
    cur = conn.cursor()
    if channel_id is not None:
        cur.execute("""
            SELECT m.* FROM messages m
            JOIN message_flags f ON f.message_id = m.id
            WHERE f.flag = %s AND m.channel_id = %s AND m.is_deleted = 0
            ORDER BY m.created_at DESC LIMIT %s
        """, (flag, channel_id, limit))
    else:
        cur.execute("""
            SELECT m.* FROM messages m
            JOIN message_flags f ON f.message_id = m.id
            WHERE f.flag = %s AND m.is_deleted = 0
            ORDER BY m.created_at DESC LIMIT %s
        """, (flag, limit))
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in rows]


# ---------------------------------------------------------------------------
# Bus
# ---------------------------------------------------------------------------

def bus_send(conn, *, channel_id: int, sender: str, content: str,
             to_agent: str = BUS_BROADCAST, bus_type: str = "EVENT",
             priority: int = 3, correlation_id: str = None,
             ttl: int = None) -> Dict[str, Any]:
    if bus_type not in BUS_TYPES:
        raise ValueError(f"bus_type must be one of {BUS_TYPES}")
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO messages
            (channel_id, sender, content, message_type, to_agent, bus_type, priority, correlation_id, ttl)
        VALUES (%s, %s, %s, 'text', %s, %s, %s, %s, %s)
        RETURNING id, channel_id, sender, content, to_agent, bus_type, priority,
                  correlation_id, ttl, created_at
    """, (channel_id, sender, content, to_agent, bus_type, priority, correlation_id, ttl))
    row = cur.fetchone()
    cols = [d[0] for d in cur.description]
    conn.commit()
    return dict(zip(cols, row))


def bus_receive(conn, agent: str, since_id: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM messages
        WHERE (
            LOWER(TRIM(COALESCE(to_agent, ''))) = LOWER(TRIM(%s))
            OR to_agent = %s
          )
          AND is_deleted = 0
          AND id > %s
          AND (ttl IS NULL OR created_at + (ttl || ' seconds')::interval > NOW())
        ORDER BY priority ASC, id ASC
        LIMIT %s
    """, (agent, BUS_BROADCAST, since_id, limit))
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in rows]


# ---------------------------------------------------------------------------
# Cursors
# ---------------------------------------------------------------------------

def cursor_save(conn, agent: str, cursors: dict) -> None:
    import json
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agent_cursors (
            agent      TEXT PRIMARY KEY,
            cursors    JSONB NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        INSERT INTO agent_cursors (agent, cursors, updated_at)
        VALUES (%s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (agent) DO UPDATE
        SET cursors = EXCLUDED.cursors, updated_at = CURRENT_TIMESTAMP
    """, (agent, json.dumps(cursors)))
    conn.commit()


def cursor_load(conn, agent: str) -> dict:
    import json
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS agent_cursors (
                agent      TEXT PRIMARY KEY,
                cursors    JSONB NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("SELECT cursors FROM agent_cursors WHERE agent = %s", (agent,))
        row = cur.fetchone()
        conn.commit()
        if not row:
            return {}
        val = row[0]
        return val if isinstance(val, dict) else json.loads(val)
    except Exception:
        conn.rollback()
        return {}


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------

def get_unindexed(conn, limit: int = 100) -> List[Dict[str, Any]]:
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM messages
        WHERE willow_indexed_at IS NULL AND is_deleted = 0
        ORDER BY created_at ASC LIMIT %s
    """, (limit,))
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in rows]


def mark_indexed(conn, message_ids: List[int]) -> int:
    if not message_ids:
        return 0
    cur = conn.cursor()
    cur.execute(
        "UPDATE messages SET willow_indexed_at = CURRENT_TIMESTAMP WHERE id = ANY(%s)",
        (message_ids,)
    )
    conn.commit()
    return cur.rowcount


# ---------------------------------------------------------------------------
# Grove-specific helpers
# ---------------------------------------------------------------------------

def ensure_card_builder_channel() -> None:
    """Idempotent: create #card-builder channel if absent."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO grove.channels (name, channel_type, description, agent_name)
            VALUES ('card-builder', 'group', 'Card builder interview channel', 'willow')
            ON CONFLICT (name) DO NOTHING
        """)
        conn.commit()
    except Exception:
        pass
    finally:
        if conn is not None:
            release_connection(conn)
