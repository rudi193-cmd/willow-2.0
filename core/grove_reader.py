"""grove_reader.py — Direct Postgres reader for Grove and routing data.
b17: WDASH  ΔΣ=42
"""
import hashlib
import json
import logging
import os
from datetime import datetime, timezone

from . import grove_db

_log = logging.getLogger("grove_reader")

# ── Color hash palette (ANSI 16, maps to curses color pair numbers 11-17) ────
_HASH_PAIRS = [11, 12, 13, 14, 15, 16, 17]


def color_for_sender(name: str) -> int:
    """Return a stable curses color_pair number for this sender name."""
    return _HASH_PAIRS[int(hashlib.md5(name.encode()).hexdigest(), 16) % len(_HASH_PAIRS)]


def _conn_ctx(conn):
    """(conn, owned) — owned=True means caller must release to pool."""
    if conn is not None:
        return conn, False
    return grove_db.get_connection(), True


def _release(conn, owned: bool) -> None:
    if owned:
        grove_db.release_connection(conn)


def dashboard_grove_sender() -> str:
    """Sender name for dashboard chat + DeskPane (fleet identity).

    Explicit GROVE_SENDER wins, then GROVE_NAME.
    Otherwise 'Auto' (Cursor/dashboard router row in public.agents).
    """
    for key in ("GROVE_SENDER", "GROVE_NAME"):
        v = (os.environ.get(key) or "").strip()
        if v:
            return v
    return "Auto"


def desk_mention_handles(primary_sender: str | None = None) -> list[str]:
    """Handles for ATTENTION (@-substring match via ILIKE), deduped case-insensitively.

    primary_sender overrides dashboard identity (e.g. MCP inbox with agent='Auto').

    Includes the primary sender plus 'all' so @all broadcasts surface on the desk.
    Optional GROVE_DESK_MENTIONS=comma,separated extras (handles without leading @).
    """
    handles: list[str] = []
    seen: set[str] = set()

    def _add(raw: str) -> None:
        h = raw.strip().lstrip("@")
        if not h:
            return
        k = h.lower()
        if k in seen:
            return
        seen.add(k)
        handles.append(h)

    base = (
        primary_sender.strip()
        if (primary_sender and primary_sender.strip())
        else dashboard_grove_sender()
    )
    _add(base)
    _add("all")
    extras = (os.environ.get("GROVE_DESK_MENTIONS") or "").strip()
    for part in extras.split(","):
        _add(part)
    return handles


def merge_attention_messages(*row_groups: list[dict], limit: int = 20) -> list[dict]:
    """Dedupe-by-id descending merge for desk ATTENTION / inbox."""
    seen: set[int] = set()
    out: list[dict] = []
    merged: list[dict] = []
    for grp in row_groups:
        merged.extend(grp or [])
    for row in sorted(merged, key=lambda r: -int(r["id"])):
        mid = int(row["id"])
        if mid in seen:
            continue
        seen.add(mid)
        out.append(row)
        if len(out) >= limit:
            break
    return out


def grove_messages_bus_addressed_to(
    recipient: str,
    *,
    since_id: int = 0,
    limit: int = 40,
    conn=None,
) -> list[dict]:
    """Messages bus-routed *directly* to recipient (to_agent matches, case-insensitive).

    Rows where content lacks @mentions but agents used MCP bus addressing.
    Drops HEARTBEAT/ACK noise. Does NOT include '__all__' broadcasts (use mentions + history).
    """
    r = recipient.strip()
    if not r:
        return []
    conn, owned = _conn_ctx(conn)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT m.id, c.name, m.sender, m.content
            FROM grove.messages m
            JOIN grove.channels c ON c.id = m.channel_id
            WHERE m.is_deleted = 0
              AND c.is_archived = FALSE
              AND m.id > %s
              AND LOWER(TRIM(COALESCE(m.to_agent, ''))) = LOWER(TRIM(%s))
              AND LOWER(TRIM(COALESCE(m.to_agent, ''))) <> '__all__'
              AND COALESCE(m.bus_type, '') NOT IN ('HEARTBEAT', 'ACK')
            ORDER BY m.id DESC
            LIMIT %s
            """,
            (since_id, r, limit),
        )
        return [
            {"id": r0[0], "channel": r0[1], "sender": r0[2], "content": r0[3]}
            for r0 in cur.fetchall()
        ]
    except Exception as e:
        _log.warning("grove_reader.grove_messages_bus_addressed_to: %s", e)
        return []
    finally:
        _release(conn, owned)


def grove_own_channel_since(
    channel_name: str,
    *,
    since_id: int = 0,
    limit: int = 80,
    conn=None,
) -> list[dict]:
    """Rule 1 (persistent monitor): every message in the agent-dedicated channel.

    Channel name convention: lowercased sender identity (e.g. Auto → #auto).
    Skips HEARTBEAT bus noise — text posts only.
    """
    ch = (channel_name or "").strip()
    if not ch:
        return []
    conn, owned = _conn_ctx(conn)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT m.id, c.name, m.sender, m.content
              FROM grove.messages m
              JOIN grove.channels c ON c.id = m.channel_id
             WHERE LOWER(TRIM(c.name)) = LOWER(TRIM(%s))
               AND m.is_deleted = 0
               AND c.is_archived = FALSE
               AND m.id > %s
               AND COALESCE(m.bus_type, '') NOT IN ('HEARTBEAT', 'ACK')
             ORDER BY m.id DESC
             LIMIT %s
            """,
            (ch, since_id, limit),
        )
        return [
            {"id": r[0], "channel": r[1], "sender": r[2], "content": r[3]}
            for r in cur.fetchall()
        ]
    except Exception as e:
        _log.warning("grove_reader.grove_own_channel_since: %s", e)
        return []
    finally:
        _release(conn, owned)


def grove_inbox_bundle(
    agent: str | None = None,
    *,
    since_id: int = 0,
    mention_limit: int = 60,
    bus_limit: int = 60,
    merge_limit: int = 35,
    conn=None,
) -> list[dict]:
    """Unified pull: @mentions + bus to_agent + dedicated #<agent> inbox (rule 1).

    Acquires a single pooled connection for all three sub-queries when conn=None,
    avoiding three separate checkout/release round-trips per call.
    """
    who = agent.strip() if (agent and agent.strip()) else dashboard_grove_sender()
    handles = desk_mention_handles(who)
    inbox_name = who.strip().lower().replace(" ", "-")
    _conn, owned = _conn_ctx(conn)
    try:
        mention_rows = grove_mentions_for_handles(handles, limit=mention_limit, conn=_conn)
        bus_rows = grove_messages_bus_addressed_to(who, since_id=since_id, limit=bus_limit, conn=_conn)
        own_rows = grove_own_channel_since(inbox_name, since_id=since_id, limit=mention_limit, conn=_conn)
    finally:
        _release(_conn, owned)
    filtered_mentions = [m for m in mention_rows if int(m["id"]) > since_id]
    return merge_attention_messages(
        filtered_mentions, bus_rows, own_rows, limit=merge_limit,
    )


def grove_agents(conn=None) -> list[dict]:
    """Return agents from HEARTBEAT bus messages, most recent first.
    Each entry: {sender: str, last_seen_at: datetime, age_secs: int}
    Falls back to all-sender inference if bus_type column is absent.
    """
    conn, owned = _conn_ctx(conn)
    try:
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT sender, MAX(created_at) AS last_seen
                FROM grove.messages
                WHERE bus_type = 'HEARTBEAT' AND is_deleted = 0
                GROUP BY sender
                ORDER BY last_seen DESC
                LIMIT 20
            """)
        except Exception as e:
            _log.debug("grove_reader.grove_agents: bus_type column absent, falling back: %s", e)
            conn.rollback()
            cur.execute("""
                SELECT sender, MAX(created_at) AS last_seen
                FROM grove.messages
                WHERE is_deleted = 0
                GROUP BY sender
                ORDER BY last_seen DESC
                LIMIT 20
            """)
        now = datetime.now(timezone.utc)
        rows = []
        for sender, last_seen in cur.fetchall():
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)
            age_secs = int((now - last_seen).total_seconds())
            rows.append({"sender": sender, "last_seen_at": last_seen, "age_secs": age_secs})
        return rows
    except Exception as e:
        _log.warning("grove_reader.grove_agents: %s", e)
        return []
    finally:
        _release(conn, owned)


def _ui_state(age_secs: int | None, hb_content: str | None) -> str:
    if hb_content and hb_content.lstrip().startswith("[AGENT_VIEW] status=blocked"):
        return "blocked"
    if age_secs is None:
        return "unknown"
    if age_secs < 120:
        return "running"
    if age_secs < 900:
        return "idle"
    return "stale"


def grove_latest_message_for_sender(
    sender: str,
    exclude_bus_types: tuple = ("HEARTBEAT",),
    conn=None,
) -> dict | None:
    """Return the latest non-HEARTBEAT message for sender, or None."""
    conn, owned = _conn_ctx(conn)
    try:
        cur = conn.cursor()
        placeholders = ",".join(["%s"] * len(exclude_bus_types))
        cur.execute(
            f"""
            SELECT id, content, correlation_id, reply_to_id
            FROM grove.messages
            WHERE sender = %s
              AND bus_type NOT IN ({placeholders})
              AND is_deleted = 0
            ORDER BY id DESC LIMIT 1
            """,
            (sender, *exclude_bus_types),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "content": row[1],
            "correlation_id": row[2],
            "reply_to_id": row[3],
        }
    except Exception as e:
        _log.warning("grove_reader.grove_latest_message_for_sender: %s", e)
        return None
    finally:
        _release(conn, owned)


def grove_agent_fleet_rows(limit: int = 50, conn=None) -> list[dict]:
    """Return fleet rows for the AgentsPane.

    Each row: sender, last_seen_at, age_secs, ui_state, peek,
              blocked, reply_to_message_id, correlation_id.
    Two round-trips max per §7 (Phase 0).
    """
    conn, owned = _conn_ctx(conn)
    try:
        cur = conn.cursor()

        # Round 1: latest HEARTBEAT per sender + structured heartbeat content
        cur.execute(
            """
            SELECT m.sender, m.created_at, m.content
            FROM grove.messages m
            JOIN (
                SELECT sender, MAX(id) AS hb_id
                FROM grove.messages
                WHERE bus_type = 'HEARTBEAT' AND is_deleted = 0
                GROUP BY sender
            ) latest ON m.id = latest.hb_id
            ORDER BY m.created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        hb_rows = cur.fetchall()

        now = datetime.now(timezone.utc)
        senders = [r[0] for r in hb_rows]

        # Round 2: latest non-HEARTBEAT + needs-reply flag per sender (batch)
        peek_by_sender: dict = {}
        if senders:
            cur.execute(
                """
                SELECT DISTINCT ON (m.sender)
                    m.sender, m.id, m.content, m.correlation_id,
                    (mf.message_id IS NOT NULL) AS needs_reply
                FROM grove.messages m
                LEFT JOIN grove.message_flags mf
                       ON mf.message_id = m.id AND mf.flag = 'needs-reply'
                WHERE m.sender = ANY(%s)
                  AND m.bus_type != 'HEARTBEAT'
                  AND m.is_deleted = 0
                ORDER BY m.sender, m.id DESC
                """,
                (senders,),
            )
            for row in cur.fetchall():
                peek_by_sender[row[0]] = {
                    "peek_id": row[1],
                    "peek": (row[2] or "")[:200],
                    "correlation_id": row[3],
                    "needs_reply": bool(row[4]),
                }

        rows = []
        for sender, last_seen, hb_content in hb_rows:
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)
            age_secs = int((now - last_seen).total_seconds())
            peek_data = peek_by_sender.get(sender, {})
            needs_reply = peek_data.get("needs_reply", False)
            state = _ui_state(age_secs, hb_content)
            if needs_reply and state != "blocked":
                state = "blocked"
            rows.append({
                "sender": sender,
                "last_seen_at": last_seen,
                "age_secs": age_secs,
                "ui_state": state,
                "peek": peek_data.get("peek", ""),
                "blocked": needs_reply or state == "blocked",
                "reply_to_message_id": peek_data.get("peek_id") if needs_reply else None,
                "correlation_id": peek_data.get("correlation_id"),
            })
        return rows
    except Exception as e:
        _log.warning("grove_reader.grove_agent_fleet_rows: %s", e)
        return []
    finally:
        _release(conn, owned)


def coordinator_heartbeat(conn=None) -> dict | None:
    """Return parsed HEARTBEAT content from willow-coordinator, or None."""
    conn, owned = _conn_ctx(conn)
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT content FROM grove.messages
            WHERE sender = 'willow' AND bus_type = 'HEARTBEAT'
              AND is_deleted = 0
            ORDER BY created_at DESC LIMIT 1
        """)
        row = cur.fetchone()
        return json.loads(row[0]) if row else None
    except Exception:
        return None
    finally:
        _release(conn, owned)


def grove_channels(conn=None, last_seen_ids: dict | None = None) -> list[dict]:
    """Return channels with unread counts.
    last_seen_ids: {channel_name: last_seen_message_id}
    Each entry: {id: int, name: str, unread: int, agent_name: str|None}
    """
    conn, owned = _conn_ctx(conn)
    last_seen_ids = last_seen_ids or {}
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT id, name, agent_name FROM grove.channels "
                "WHERE is_archived = FALSE ORDER BY id"
            )
            channels = [(r[0], r[1], r[2]) for r in cur.fetchall()]
        except Exception as e:
            _log.debug("grove_reader.grove_channels: agent_name column absent, falling back: %s", e)
            conn.rollback()
            cur = conn.cursor()
            cur.execute(
                "SELECT id, name FROM grove.channels "
                "WHERE is_archived = FALSE ORDER BY id"
            )
            channels = [(r[0], r[1], None) for r in cur.fetchall()]
        result = []
        for ch_id, name, agent_name in channels:
            last_id = last_seen_ids.get(name, 0)
            cur.execute(
                "SELECT COUNT(*) FILTER (WHERE id > %s), COALESCE(MAX(id), 0) "
                "FROM grove.messages WHERE channel_id = %s AND is_deleted = 0",
                (last_id, ch_id),
            )
            row = cur.fetchone()
            unread = row[0] if row else 0
            max_id = row[1] if row else 0
            result.append({"id": ch_id, "name": name, "unread": unread,
                           "max_id": max_id, "agent_name": agent_name})
        return result
    except Exception as e:
        _log.warning("grove_reader.grove_channels: %s", e)
        return []
    finally:
        _release(conn, owned)


def grove_messages(channel_name: str, conn=None, limit: int = 50,
                   since_id: int = 0) -> list[dict]:
    """Return messages for a channel, oldest first.
    Each entry: {id: int, sender: str, content: str, created_at: datetime}
    """
    conn, owned = _conn_ctx(conn)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM grove.channels WHERE name = %s LIMIT 1",
            (channel_name,),
        )
        row = cur.fetchone()
        if not row:
            return []
        ch_id = row[0]
        cur.execute(
            """
            SELECT id, sender, content, created_at
            FROM grove.messages
            WHERE channel_id = %s AND id > %s AND is_deleted = 0
            ORDER BY id DESC LIMIT %s
            """,
            (ch_id, since_id, limit),
        )
        msgs = []
        for mid, sender, content, created_at in cur.fetchall():
            msgs.append({"id": mid, "sender": sender,
                         "content": content, "created_at": created_at})
        return list(reversed(msgs))
    except Exception as e:
        _log.warning("grove_reader.grove_messages: %s", e)
        return []
    finally:
        _release(conn, owned)


def grove_messages_all_agents(
    known_agents: "frozenset[str]",
    last_id: int = 0,
    limit: int = 20,
) -> "list[dict]":
    """Return recent grove.messages from known agent senders, id > last_id."""
    conn, owned = _conn_ctx(None)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, sender, content, created_at"
            " FROM grove.messages"
            " WHERE sender = ANY(%s::text[]) AND id > %s AND is_deleted = 0"
            " ORDER BY id DESC LIMIT %s",
            (list(known_agents), last_id, limit),
        )
        rows = cur.fetchall()
        return [
            {"id": r[0], "sender": r[1], "content": r[2], "created_at": r[3]}
            for r in reversed(rows)
        ]
    except Exception as e:
        _log.warning("grove_reader.grove_messages_all_agents: %s", e)
        return []
    finally:
        _release(conn, owned)


_mention_index_ensured = False

_MENTION_INDEX_DDL = """
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_messages_content_trgm
    ON grove.messages USING GIN (content gin_trgm_ops);
"""


def _ensure_mention_index(cur) -> None:
    """Create pg_trgm extension + GIN index on first call. No-op if already present."""
    global _mention_index_ensured
    if _mention_index_ensured:
        return
    try:
        for stmt in _MENTION_INDEX_DDL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                cur.execute(stmt)
        _mention_index_ensured = True
    except Exception as e:
        _log.warning("grove_reader._ensure_mention_index: %s", e)


def grove_mentions_for_handles(handles: list[str], limit: int = 20, conn=None) -> list[dict]:
    """Recent messages matching @<handle> for any handle (ILIKE substring, case-folded).

    Each entry: {id, channel, sender, content}
    """
    clean: list[str] = []
    seen: set[str] = set()
    for raw in handles:
        h = (raw or "").strip().lstrip("@")
        if not h:
            continue
        k = h.lower()
        if k in seen:
            continue
        seen.add(k)
        clean.append(h)
    if not clean:
        return []
    conn, owned = _conn_ctx(conn)
    try:
        cur = conn.cursor()
        _ensure_mention_index(cur)
        placeholders = " OR ".join(["m.content ILIKE %s"] * len(clean))
        params = [f"%@{h}%" for h in clean]
        params.append(limit)
        cur.execute(
            f"""
            SELECT m.id, c.name, m.sender, m.content
            FROM grove.messages m
            JOIN grove.channels c ON c.id = m.channel_id
            WHERE ({placeholders})
              AND m.is_deleted = 0
              AND c.is_archived = FALSE
            ORDER BY m.id DESC
            LIMIT %s
            """,
            params,
        )
        return [
            {"id": r[0], "channel": r[1], "sender": r[2], "content": r[3]}
            for r in cur.fetchall()
        ]
    except Exception as e:
        _log.warning("grove_reader.grove_mentions_for_handles: %s", e)
        return []
    finally:
        _release(conn, owned)


def grove_mentions(name: str, limit: int = 20, conn=None) -> list[dict]:
    """Single-handle wrapper over grove_mentions_for_handles."""
    return grove_mentions_for_handles([name], limit=limit, conn=conn)


_ROUTING_DDL = """
CREATE SCHEMA IF NOT EXISTS willow;
CREATE TABLE IF NOT EXISTS willow.routing_decisions (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
    session_id  TEXT,
    prompt_snippet TEXT,
    routed_to   TEXT,
    rule_matched TEXT,
    confidence  FLOAT,
    latency_ms  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_routing_decisions_ts
    ON willow.routing_decisions (ts DESC);
"""


def routing_decisions(conn=None, limit: int = 8) -> list[dict]:
    """Return recent routing decisions. Auto-creates table on first call.

    Reads **only** `willow.routing_decisions` (oracle-shaped rows). MCP also logs JSON decisions
    to `public.routing_decisions`; see ``docs/verify/ROUTING_OBSERVABILITY.md``.

    Each entry: {ts, prompt_snippet, routed_to, rule_matched, confidence, latency_ms}
    """
    conn, owned = _conn_ctx(conn)
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT ts, prompt_snippet, routed_to, rule_matched, confidence, latency_ms
                FROM willow.routing_decisions
                ORDER BY ts DESC LIMIT %s
                """,
                (limit,),
            )
        except Exception as e:
            _log.debug("grove_reader.routing_decisions: table absent, auto-creating: %s", e)
            conn.rollback()
            cur.execute(_ROUTING_DDL)
            conn.commit()
            return []
        rows = []
        for ts, snippet, routed_to, rule_matched, confidence, latency_ms in cur.fetchall():
            rows.append({
                "ts": ts,
                "prompt_snippet": snippet,
                "routed_to": routed_to,
                "rule_matched": rule_matched,
                "confidence": float(confidence) if confidence is not None else 1.0,
                "latency_ms": latency_ms,
            })
        return rows
    except Exception as e:
        _log.warning("grove_reader.routing_decisions: %s", e)
        return []
    finally:
        _release(conn, owned)
