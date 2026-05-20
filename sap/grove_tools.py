"""
sap/grove_tools.py — Grove messaging tools for the unified MCP.

Ports grove/mcp_local.py tool implementations into sap/ so a single
FastMCP instance can expose willow + grove + mai tools together.

Requires grove repo on PYTHONPATH (grove_db, grove_reader).
"""
from __future__ import annotations

import os
import socket
import threading
import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

# ── Grove DB imports (grove repo must be on PYTHONPATH) ───────────────────────

try:
    import grove_db as db
    import grove_reader as _grove_reader
    _GROVE_AVAILABLE = True
except ImportError:
    db = None  # type: ignore[assignment]
    _grove_reader = None  # type: ignore[assignment]
    _GROVE_AVAILABLE = False


# ── Notification state (shared with unified lifespan) ────────────────────────

_subscriptions: dict[int, set[asyncio.Queue]] = {}
_subscriptions_lock = threading.Lock()
_main_loop: asyncio.AbstractEventLoop | None = None


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _main_loop
    _main_loop = loop


def pg_notify_thread() -> None:
    """Dedicated Postgres LISTEN thread for grove channel notifications."""
    if not _GROVE_AVAILABLE:
        return
    import psycopg2
    import select as _select
    import time

    dsn = os.getenv("WILLOW_DB_URL", "")
    if not dsn:
        pg_db   = os.getenv("WILLOW_PG_DB", "willow_20")
        pg_user = os.getenv("WILLOW_PG_USER", os.environ.get("USER", ""))
        dsn = f"dbname={pg_db} user={pg_user}"

    while True:
        try:
            conn = psycopg2.connect(dsn)
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute("SET search_path = grove, public")
            cur.execute("LISTEN grove_channel")
            while True:
                ready = _select.select([conn], [], [], 5.0)
                if not ready[0]:
                    continue
                conn.poll()
                while conn.notifies:
                    n = conn.notifies.pop(0)
                    try:
                        channel_id = int(n.payload)
                    except ValueError:
                        continue
                    with _subscriptions_lock:
                        queues = list(_subscriptions.get(channel_id, set()))
                    if queues and _main_loop:
                        for q in queues:
                            asyncio.run_coroutine_threadsafe(q.put(channel_id), _main_loop)
        except Exception:
            time.sleep(3)


def _msgs_to_dicts(msgs: list) -> list[dict]:
    return [
        {
            "id": m["id"],
            "sender": m["sender"],
            "content": m["content"],
            "reply_to_id": m.get("reply_to_id"),
            "to_agent": m.get("to_agent", db.BUS_BROADCAST if db else "__all__"),
            "bus_type": m.get("bus_type", "EVENT"),
            "priority": m.get("priority", 3),
            "correlation_id": m.get("correlation_id"),
            "created_at": m["created_at"].isoformat() if m.get("created_at") else None,
        }
        for m in msgs
    ]


def _unavailable() -> dict:
    return {"error": "Grove package not available — check PYTHONPATH includes safe-app-willow-grove"}


# ── Tool registration ─────────────────────────────────────────────────────────

def register(mcp: "FastMCP") -> None:
    """Register all grove tools on the provided FastMCP instance."""

    @mcp.tool()
    def grove_list_channels() -> list[dict]:
        """List all active Grove channels (name, type, description)."""
        if not _GROVE_AVAILABLE:
            return [_unavailable()]
        conn = db.get_connection()
        try:
            rows = db.list_channels(conn)
            return [
                {"id": r["id"], "name": r["name"], "type": r["channel_type"],
                 "description": r.get("description")}
                for r in rows
            ]
        finally:
            db.release_connection(conn)

    @mcp.tool()
    def grove_get_history(channel_name: str, limit: int = 50, since_id: int = 0) -> list[dict]:
        """
        Get message history from a Grove channel.

        Args:
            channel_name: Exact channel name (use grove_list_channels to find names).
            limit: Number of messages to return (max 200, default 50).
            since_id: If > 0, return only messages with id greater than this value,
                      oldest first. Use the last returned message's id as your next
                      since_id to poll for new messages without re-fetching history.
        """
        if not _GROVE_AVAILABLE:
            return [_unavailable()]
        conn = db.get_connection()
        try:
            channels = db.list_channels(conn)
            ch = next((c for c in channels if c["name"] == channel_name), None)
            if not ch:
                return []
            if since_id > 0:
                msgs = db.get_history(conn, ch["id"], limit=min(limit, 200), since_id=since_id)
            else:
                msgs = db.get_history(conn, ch["id"], limit=min(limit, 200))
                msgs = list(reversed(msgs))
            return [
                {
                    "id": m["id"],
                    "sender": m["sender"],
                    "content": m["content"],
                    "created_at": m["created_at"].isoformat() if m.get("created_at") else None,
                }
                for m in msgs
            ]
        finally:
            db.release_connection(conn)

    @mcp.tool()
    def grove_send_message(channel_name: str, content: str, sender: str = "Auto") -> dict:
        """
        Send a message to a Grove channel. Creates the channel if it doesn't exist.

        Args:
            channel_name: Target channel name.
            content: Message body.
            sender: Display name for the sender (default: Auto).
        """
        if not _GROVE_AVAILABLE:
            return _unavailable()
        conn = db.get_connection()
        try:
            channels = db.list_channels(conn)
            ch = next((c for c in channels if c["name"] == channel_name), None)
            if not ch:
                ch = db.create_channel(conn, name=channel_name, channel_type="group")
            msg = db.send_message(conn, channel_id=ch["id"], sender=sender, content=content)
            return {"id": msg["id"], "channel": channel_name, "sent": True}
        finally:
            db.release_connection(conn)

    @mcp.tool()
    def grove_search(query: str, channel_name: str = "") -> list[dict]:
        """
        Search Grove messages by content.

        Args:
            query: Search term (case-insensitive substring match).
            channel_name: Optional channel to restrict search to.
        """
        if not _GROVE_AVAILABLE:
            return [_unavailable()]
        conn = db.get_connection()
        try:
            channel_id = None
            if channel_name:
                channels = db.list_channels(conn)
                ch = next((c for c in channels if c["name"] == channel_name), None)
                channel_id = ch["id"] if ch else None
            msgs = db.search_messages(conn, query, channel_id=channel_id)
            return [
                {
                    "sender": m["sender"],
                    "content": m["content"],
                    "created_at": m["created_at"].isoformat() if m.get("created_at") else None,
                }
                for m in msgs[:50]
            ]
        finally:
            db.release_connection(conn)

    @mcp.tool()
    def grove_get_identity() -> dict:
        """Get this Grove node's u2u address and public key."""
        if not _GROVE_AVAILABLE:
            return _unavailable()
        from u2u.identity import Identity
        identity_path = Path.home() / ".willow" / "grove_identity.json"
        identity = Identity.load_or_generate(identity_path)
        name = os.getenv("GROVE_NAME", os.getenv("USER", "me"))
        port = int(os.getenv("GROVE_PORT", "8550"))
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                host = s.getsockname()[0]
        except OSError:
            host = "localhost"
        return {
            "address": f"{name}@{host}:{port}",
            "public_key": identity.public_key_hex,
        }

    @mcp.tool()
    def grove_watch(channel_name: str, since_id: int) -> list[dict]:
        """
        Return any new messages in a channel since since_id. Non-blocking.

        Args:
            channel_name: Channel to check.
            since_id: Return messages with id greater than this value.
        """
        if not _GROVE_AVAILABLE:
            return [_unavailable()]
        conn = db.get_connection()
        try:
            channels = db.list_channels(conn)
            ch = next((c for c in channels if c["name"] == channel_name), None)
            if not ch:
                return []
            msgs = db.get_history(conn, ch["id"], limit=50, since_id=since_id)
            return _msgs_to_dicts(msgs)
        finally:
            db.release_connection(conn)

    @mcp.tool()
    def grove_watch_all(cursors: dict) -> dict:
        """
        Check multiple channels at once for new messages. Non-blocking.

        Args:
            cursors: Dict mapping channel_name → since_id, e.g. {"general": 6, "github": 10}
        """
        if not _GROVE_AVAILABLE:
            return _unavailable()
        conn = db.get_connection()
        try:
            all_channels = db.list_channels(conn)
            results = {}
            for ch in all_channels:
                name = ch["name"]
                if name not in cursors:
                    continue
                msgs = db.get_history(conn, ch["id"], limit=50, since_id=cursors[name])
                if msgs:
                    results[name] = _msgs_to_dicts(msgs)
            return results
        finally:
            db.release_connection(conn)

    @mcp.tool()
    def grove_reply(channel_name: str, content: str, sender: str, reply_to_id: int) -> dict:
        """
        Reply to a message in a thread.

        Args:
            channel_name: Channel containing the parent message.
            content: Reply body.
            sender: Display name for the sender.
            reply_to_id: ID of the message being replied to.
        """
        if not _GROVE_AVAILABLE:
            return _unavailable()
        conn = db.get_connection()
        try:
            channels = db.list_channels(conn)
            ch = next((c for c in channels if c["name"] == channel_name), None)
            if not ch:
                return {"error": f"channel '{channel_name}' not found"}
            msg = db.send_message(conn, channel_id=ch["id"], sender=sender,
                                  content=content, reply_to_id=reply_to_id)
            db.clear_flag(conn, message_id=reply_to_id, sender="__system__", flag="needs-reply")
            return {"id": msg["id"], "channel": channel_name, "reply_to_id": reply_to_id, "sent": True}
        finally:
            db.release_connection(conn)

    @mcp.tool()
    def grove_get_thread(message_id: int) -> dict:
        """
        Get a message and all its replies.

        Args:
            message_id: ID of the parent message.
        """
        if not _GROVE_AVAILABLE:
            return _unavailable()
        conn = db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM messages WHERE id = %s AND is_deleted = 0", (message_id,))
            row = cur.fetchone()
            if not row:
                return {"error": "message not found"}
            cols = [d[0] for d in cur.description]
            parent = dict(zip(cols, row))
            replies = db.get_thread(conn, message_id)
            flags = db.get_flags(conn, message_id)
            return {
                "parent": _msgs_to_dicts([parent])[0],
                "flags": flags,
                "replies": _msgs_to_dicts(replies),
            }
        finally:
            db.release_connection(conn)

    @mcp.tool()
    def grove_flag(message_id: int, flag: str, sender: str) -> dict:
        """
        Set a flag on a message.

        Args:
            message_id: ID of the message to flag.
            flag: One of: needs-reply, starred, read, urgent, resolved.
            sender: Who is setting the flag.
        """
        if not _GROVE_AVAILABLE:
            return _unavailable()
        conn = db.get_connection()
        try:
            db.set_flag(conn, message_id=message_id, sender=sender, flag=flag)
            return {"message_id": message_id, "flag": flag, "set": True}
        except ValueError as e:
            return {"error": str(e)}
        finally:
            db.release_connection(conn)

    @mcp.tool()
    def grove_unflag(message_id: int, flag: str, sender: str) -> dict:
        """
        Clear a flag from a message.

        Args:
            message_id: ID of the message to unflag.
            flag: Flag to clear.
            sender: Who is clearing the flag.
        """
        if not _GROVE_AVAILABLE:
            return _unavailable()
        conn = db.get_connection()
        try:
            cleared = db.clear_flag(conn, message_id=message_id, sender=sender, flag=flag)
            return {"message_id": message_id, "flag": flag, "cleared": cleared}
        finally:
            db.release_connection(conn)

    @mcp.tool()
    def grove_bus_send(
        channel_name: str, sender: str, content: str,
        to_agent: str = "__all__", bus_type: str = "EVENT",
        priority: int = 3, correlation_id: str = "", ttl: int = 0,
    ) -> dict:
        """
        Send a structured bus message — addressed, typed, and prioritized.

        Args:
            channel_name: Channel to post to.
            sender: Sending agent name.
            content: Message body.
            to_agent: Recipient agent name, or '__all__' for broadcast.
            bus_type: COMMAND, RESPONSE, EVENT, INTERRUPT, HEARTBEAT, ACK, DATA, SYNC.
            priority: 0=INTERRUPT, 3=NORMAL, 6=HEARTBEAT, 7=DEBUG.
            correlation_id: Pair requests with responses.
            ttl: Seconds until message expires. 0 = never.
        """
        if not _GROVE_AVAILABLE:
            return _unavailable()
        conn = db.get_connection()
        try:
            channels = db.list_channels(conn)
            ch = next((c for c in channels if c["name"] == channel_name), None)
            if not ch:
                ch = db.create_channel(conn, name=channel_name, channel_type="group")
            msg = db.bus_send(
                conn, channel_id=ch["id"], sender=sender, content=content,
                to_agent=to_agent or db.BUS_BROADCAST,
                bus_type=bus_type, priority=priority,
                correlation_id=correlation_id or None,
                ttl=ttl or None,
            )
            if bus_type in ("COMMAND", "INTERRUPT"):
                db.set_flag(conn, message_id=msg["id"], sender="__system__", flag="needs-reply")
            return {
                "id": msg["id"], "channel": channel_name, "to_agent": to_agent,
                "bus_type": bus_type, "priority": priority,
                "correlation_id": correlation_id or None, "sent": True,
            }
        finally:
            db.release_connection(conn)

    @mcp.tool()
    def grove_bus_receive(agent: str, channel_name: str = "", since_id: int = 0) -> list[dict]:
        """
        Fetch bus messages addressed to this agent (or broadcast), ordered by priority.

        Args:
            agent: Your agent name.
            channel_name: Optional — restrict to one channel.
            since_id: Only return messages with id greater than this cursor.
        """
        if not _GROVE_AVAILABLE:
            return [_unavailable()]
        conn = db.get_connection()
        try:
            if channel_name:
                channels = db.list_channels(conn)
                ch = next((c for c in channels if c["name"] == channel_name), None)
                if not ch:
                    return []
                msgs = db.bus_receive(conn, agent=agent, since_id=since_id)
                msgs = [m for m in msgs if m.get("channel_id") == ch["id"]]
            else:
                msgs = db.bus_receive(conn, agent=agent, since_id=since_id)
            return _msgs_to_dicts(msgs)
        finally:
            db.release_connection(conn)

    @mcp.tool()
    def grove_ack(channel_name: str, sender: str, correlation_id: str, original_id: int) -> dict:
        """
        Acknowledge a received message. Clears needs-reply flag on the original.

        Args:
            channel_name: Channel of the original message.
            sender: Your agent name.
            correlation_id: The correlation_id from the message you're acking.
            original_id: The id of the message being acknowledged.
        """
        if not _GROVE_AVAILABLE:
            return _unavailable()
        conn = db.get_connection()
        try:
            channels = db.list_channels(conn)
            ch = next((c for c in channels if c["name"] == channel_name), None)
            if not ch:
                return {"error": f"channel '{channel_name}' not found"}
            msg = db.bus_send(
                conn, channel_id=ch["id"], sender=sender,
                content=f"ACK {correlation_id}",
                bus_type="ACK", priority=2,
                correlation_id=correlation_id,
            )
            db.clear_flag(conn, message_id=original_id, sender="__system__", flag="needs-reply")
            db.set_flag(conn, message_id=original_id, sender=sender, flag="read")
            return {"id": msg["id"], "acked": original_id, "correlation_id": correlation_id}
        finally:
            db.release_connection(conn)

    @mcp.tool()
    def grove_heartbeat(sender: str) -> dict:
        """
        Broadcast a heartbeat — I am alive and on the bus.

        Args:
            sender: Your agent name.
        """
        if not _GROVE_AVAILABLE:
            return _unavailable()
        conn = db.get_connection()
        try:
            channels = db.list_channels(conn)
            ch = next((c for c in channels if c["name"] == "general"), None)
            if not ch:
                ch = db.create_channel(conn, name="general", channel_type="group")
            msg = db.bus_send(
                conn, channel_id=ch["id"], sender=sender,
                content=f"{sender} online",
                bus_type="HEARTBEAT", priority=6,
                to_agent=db.BUS_BROADCAST,
            )
            return {"id": msg["id"], "sender": sender, "bus_type": "HEARTBEAT"}
        finally:
            db.release_connection(conn)

    @mcp.tool()
    def grove_inbox(agent: str = "", since_id: int = 0, limit: int = 35) -> list[dict]:
        """
        Fleet inbox: @mentions plus messages bus-addressed directly to this agent.

        Args:
            agent: Recipient identity; default follows GROVE_SENDER/GROVE_NAME.
            since_id: Only messages with id greater than this (cursor for polling).
            limit: Merge cap after dedupe-by-id newest-first.
        """
        if not _GROVE_AVAILABLE:
            return [_unavailable()]
        who = agent.strip() if agent.strip() else None
        cap = max(5, min(int(limit), 80))
        return _grove_reader.grove_inbox_bundle(who, since_id=max(0, int(since_id)), merge_limit=cap)

    @mcp.tool()
    def grove_flagged(flag: str, channel_name: str = "") -> list[dict]:
        """
        List messages carrying a given flag across all channels (or one channel).

        Args:
            flag: One of: needs-reply, starred, read, urgent, resolved.
            channel_name: Optional — restrict to one channel.
        """
        if not _GROVE_AVAILABLE:
            return [_unavailable()]
        conn = db.get_connection()
        try:
            channel_id = None
            if channel_name:
                channels = db.list_channels(conn)
                ch = next((c for c in channels if c["name"] == channel_name), None)
                channel_id = ch["id"] if ch else None
            msgs = db.get_flagged(conn, flag=flag, channel_id=channel_id)
            return _msgs_to_dicts(msgs)
        finally:
            db.release_connection(conn)
