# grove/mcp_local.py — Grove MCP for Claude Code.
# b17: GRMLC  ΔΣ=42
"""
Modes:
  stdio (default):   python3 -m grove.mcp_local
                     .mcp.json: {"command": "python3", "args": ["-m", "grove.mcp_local"]}

  serve (push):      python3 -m grove.mcp_local --serve  [--port 8765] [--watch]
                     Runs as a persistent streamable-HTTP server with OAuth.
                     Set GROVE_MCP_URL to the public base URL (e.g. ngrok tunnel).
                     If unset, serve mode defaults to http://127.0.0.1:<GROVE_MCP_PORT>
                     for valid OAuth issuer URLs (local-only).
                     .mcp.json: {"url": "https://<tunnel>/mcp"}
                     Postgres LISTEN/NOTIFY → send_resource_updated pushed to all subscribers.
                     --watch: supervise a **child** serve process; restart it when
                     `grove/*.py` changes (parent polls mtimes — works because `mcp.run` blocks).

Auth in serve mode: OAuth 2.0 PKCE (dynamic client registration, single-user approval page).
Auth in stdio mode: implicit (local process, trusted user) — no OAuth.
"""
import os
import select
import socket
import sys
import threading
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from mcp.server.fastmcp import FastMCP

from core import grove_db as db
from core import grove_reader as _grove_reader
from willow.fylgja.willow_home import willow_home

# ── Notification state ────────────────────────────────────────────────────────
_subscriptions: dict[int, set[asyncio.Queue]] = {}
_subscriptions_lock = threading.Lock()
_main_loop: asyncio.AbstractEventLoop | None = None
_notify_thread: threading.Thread | None = None
_notify_thread_lock = threading.Lock()


def _pg_notify_thread() -> None:
    """Dedicated Postgres LISTEN thread. Broadcasts to subscriber queues on NOTIFY."""
    import psycopg2

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
                ready = select.select([conn], [], [], 5.0)
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
            import time
            time.sleep(3)


def _ensure_pg_notify_thread() -> None:
    """Start the process-wide Postgres LISTEN thread once."""
    global _notify_thread
    with _notify_thread_lock:
        if _notify_thread is not None and _notify_thread.is_alive():
            return
        _notify_thread = threading.Thread(target=_pg_notify_thread, daemon=True)
        _notify_thread.start()


@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncIterator[None]:
    global _main_loop
    _main_loop = asyncio.get_running_loop()
    _ensure_pg_notify_thread()
    yield


_PORT = int(os.getenv("GROVE_MCP_PORT", "8765"))
_SERVE_MODE = "--serve" in sys.argv
_BASE_URL_ENV = (os.getenv("GROVE_MCP_URL") or "").strip().rstrip("/")
# AuthSettings (OAuth) requires absolute issuer/resource URLs. Local serve defaults
# to loopback when GROVE_MCP_URL is unset — avoids Pydantic rejecting "/" alone.
if _SERVE_MODE and not _BASE_URL_ENV:
    _BASE_URL = f"http://127.0.0.1:{_PORT}"
else:
    _BASE_URL = _BASE_URL_ENV

_common_kwargs = dict(
    instructions=(
        "Grove sovereign workspace messaging. "
        "Send and read messages, search conversations, list channels."
    ),
    host="127.0.0.1",
    port=_PORT,
    lifespan=_lifespan,
)

if _SERVE_MODE:
    from grove.mcp_auth import GroveOAuthProvider
    from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions

    _fleet_home = willow_home()
    _auth_provider = GroveOAuthProvider(
        token_path=_fleet_home / "grove_mcp_token",
        base_url=_BASE_URL,
    )
    mcp = FastMCP(
        "grove",
        **_common_kwargs,
        auth_server_provider=_auth_provider,
        auth=AuthSettings(
            issuer_url=_BASE_URL + "/",
            resource_server_url=_BASE_URL + "/",
            client_registration_options=ClientRegistrationOptions(
                enabled=True,
                valid_scopes=["grove"],
                default_scopes=["grove"],
            ),
            required_scopes=["grove"],
        ),
    )
else:
    _auth_provider = None
    mcp = FastMCP("grove", **_common_kwargs)


@mcp.tool()
def grove_list_channels() -> list[dict]:
    """List all active Grove channels (name, type, description)."""
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
        sender: Display name for the sender (default: Auto — matches public.agents / dashboard).
    """
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
    from u2u.identity import Identity
    identity_path = willow_home() / "grove_identity.json"
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


def _msgs_to_dicts(msgs: list) -> list[dict]:
    return [
        {
            "id": m["id"],
            "sender": m["sender"],
            "content": m["content"],
            "reply_to_id": m.get("reply_to_id"),
            "to_agent": m.get("to_agent", db.BUS_BROADCAST),
            "bus_type": m.get("bus_type", "EVENT"),
            "priority": m.get("priority", 3),
            "correlation_id": m.get("correlation_id"),
            "created_at": m["created_at"].isoformat() if m.get("created_at") else None,
        }
        for m in msgs
    ]


# ── Resources (serve mode) ────────────────────────────────────────────────────

@mcp.resource("grove://channel/{channel_name}")
def grove_channel_resource(channel_name: str) -> str:
    """
    Grove channel as an MCP resource. Read to get recent messages.
    Subscribe to receive push notifications when new messages arrive.
    """
    conn = db.get_connection()
    try:
        channels = db.list_channels(conn)
        ch = next((c for c in channels if c["name"] == channel_name), None)
        if not ch:
            return f"Channel '{channel_name}' not found."
        msgs = db.get_history(conn, ch["id"], limit=20)
        msgs = list(reversed(msgs))
        lines = [f"[{m['sender']}] {m['content']}" for m in msgs]
        return "\n".join(lines) if lines else "(empty)"
    finally:
        db.release_connection(conn)


@mcp._mcp_server.subscribe_resource()
async def _on_subscribe(uri: str) -> None:
    """Register a notification queue for this session when client subscribes to a channel resource."""
    if not uri.startswith("grove://channel/"):
        return
    channel_name = uri[len("grove://channel/"):]
    conn = db.get_connection()
    try:
        channels = db.list_channels(conn)
        ch = next((c for c in channels if c["name"] == channel_name), None)
        if not ch:
            return
        channel_id = ch["id"]
    finally:
        db.release_connection(conn)

    queue: asyncio.Queue = asyncio.Queue()
    with _subscriptions_lock:
        _subscriptions.setdefault(channel_id, set()).add(queue)

    session = mcp._mcp_server.request_context.session

    async def _watcher():
        try:
            while True:
                await queue.get()
                from mcp.types import AnyUrl
                await session.send_resource_updated(AnyUrl(uri))
        except Exception:
            pass
        finally:
            with _subscriptions_lock:
                _subscriptions.get(channel_id, set()).discard(queue)

    asyncio.ensure_future(_watcher())


@mcp.tool()
def grove_watch(channel_name: str, since_id: int) -> list[dict]:
    """
    Return any new messages in a channel since since_id. Non-blocking.

    Returns immediately — empty list means nothing new yet. Call again to poll.
    Use grove_get_history with since_id for the same effect with more control.

    Args:
        channel_name: Channel to check.
        since_id: Return messages with id greater than this value.
    """
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

    Returns immediately. Empty dict means nothing new in any channel.

    Args:
        cursors: Dict mapping channel_name → since_id, e.g. {"general": 6, "github": 10}

    Returns a dict mapping channel_name → list of new messages.
    Only channels with new messages appear in the result.
    Use the highest id in each channel's result as your updated cursor.
    """
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
    conn = db.get_connection()
    try:
        cleared = db.clear_flag(conn, message_id=message_id, sender=sender, flag=flag)
        return {"message_id": message_id, "flag": flag, "cleared": cleared}
    finally:
        db.release_connection(conn)


@mcp.tool()
def grove_bus_send(channel_name: str, sender: str, content: str,
                   to_agent: str = "__all__", bus_type: str = "EVENT",
                   priority: int = 3, correlation_id: str = "",
                   ttl: int = 0) -> dict:
    """
    Send a structured bus message — addressed, typed, and prioritized.

    Args:
        channel_name: Channel to post to.
        sender: Sending agent name.
        content: Message body.
        to_agent: Recipient agent name, or '__all__' for broadcast.
        bus_type: COMMAND, RESPONSE, EVENT, INTERRUPT, HEARTBEAT, ACK, DATA, SYNC.
        priority: 0=INTERRUPT, 3=NORMAL, 6=HEARTBEAT, 7=DEBUG.
        correlation_id: Pair requests with responses. Leave empty for new messages.
        ttl: Seconds until message expires. 0 = never.
    """
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
        agent: Your agent name — receives messages addressed to you or '__all__'.
        channel_name: Optional — restrict to one channel.
        since_id: Only return messages with id greater than this cursor.
    """
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
def grove_ack(channel_name: str, sender: str, correlation_id: str,
              original_id: int) -> dict:
    """
    Acknowledge a received message. Clears needs-reply flag on the original.

    Args:
        channel_name: Channel of the original message.
        sender: Your agent name.
        correlation_id: The correlation_id from the message you're acking.
        original_id: The id of the message being acknowledged.
    """
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
    Fleet inbox for Cursor: @mentions (@Auto / @all / GROVE_DESK_MENTIONS) plus messages
    bus-addressed directly to Auto (to_agent matches) even when the body has no @.

    Poll this when coordinating from the IDE— nothing is pushed into chat automatically.

    Args:
        agent: Recipient identity as stored on to_agent; default follows
               GROVE_SENDER/GROVE_NAME/dashboard default (Auto).
        since_id: Only messages with id greater than this (cursor for polling).
        limit: Merge cap after dedupe-by-id newest-first.
    """
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


# ── OAuth approval route (serve mode only) ───────────────────────────────────

if _SERVE_MODE and _auth_provider is not None:
    from starlette.requests import Request
    from starlette.responses import HTMLResponse, RedirectResponse

    @mcp.custom_route("/", methods=["GET", "POST", "DELETE", "PUT"])
    async def root_redirect(request: Request) -> RedirectResponse:
        """Redirect bare-root MCP calls to /mcp for clients that drop the path."""
        url = str(request.url).replace(str(request.base_url).rstrip("/"), "", 1)
        target = "/mcp" + (url if url and url != "/" else "")
        return RedirectResponse(target, status_code=307)

    @mcp.custom_route("/grove-approve", methods=["GET", "POST"])
    async def grove_approve(request: Request) -> HTMLResponse | RedirectResponse:
        """Single-user OAuth approval page. Sean opens this to authorize claude.ai."""
        pending_key = request.query_params.get("pending", "")
        entry = _auth_provider.pop_pending(pending_key)

        if request.method == "GET":
            if not entry:
                return HTMLResponse("<h2>Grove OAuth</h2><p>Invalid or expired approval link.</p>", status_code=400)
            client, params = entry
            # Re-stash so POST can use it
            _auth_provider._pending[pending_key] = (client, params)
            html = f"""<!DOCTYPE html>
<html><head><title>Grove Access Request</title>
<style>body{{font-family:sans-serif;max-width:480px;margin:80px auto;padding:20px}}
button{{padding:12px 24px;font-size:16px;cursor:pointer;margin:8px}}
.allow{{background:#2563eb;color:#fff;border:none;border-radius:6px}}
.deny{{background:#e5e7eb;color:#111;border:none;border-radius:6px}}</style>
</head><body>
<h2>Allow Grove access?</h2>
<p><strong>{client.client_id}</strong> is requesting access to read and send Grove messages.</p>
<form method="post" action="/grove-approve?pending={pending_key}">
  <button class="allow" type="submit" name="action" value="allow">Allow</button>
  <button class="deny" type="submit" name="action" value="deny">Deny</button>
</form>
</body></html>"""
            return HTMLResponse(html)

        # POST — issue code or deny (entry already popped at top of function)
        form = await request.form()
        action = form.get("action", "deny")
        if not entry or action != "allow":
            return HTMLResponse("<h2>Access denied.</h2>", status_code=200)

        client, params = entry
        code = _auth_provider.issue_code(client, params)
        redirect = str(params.redirect_uri)
        sep = "&" if "?" in redirect else "?"
        redirect_url = f"{redirect}{sep}code={code}"
        if params.state:
            redirect_url += f"&state={params.state}"
        return RedirectResponse(redirect_url, status_code=302)


def _snapshot_grove_mtimes(grove_dir: Path) -> dict[Path, float]:
    return {p: p.stat().st_mtime for p in grove_dir.glob("*.py")}


def _watch_serve_supervisor() -> None:
    """Reload dev mode: run `--serve` in a subprocess and restart on `grove/*.py` changes.

    Calling `mcp.run()` in-process blocks forever, so an outer poll loop cannot run.
    Supervising a child fixes that without requiring uvicorn reload internals.
    """
    import subprocess
    import time

    grove_dir = Path(__file__).parent
    mtimes = _snapshot_grove_mtimes(grove_dir)

    def child_argv() -> list[str]:
        args = [sys.executable, "-m", "grove.mcp_local"]
        for a in sys.argv[1:]:
            if a == "--watch":
                continue
            args.append(a)
        return args

    proc: subprocess.Popen | None = None
    print(f"[grove-mcp] watch: supervising child; grove dir={grove_dir}", flush=True)
    try:
        while True:
            cmd = child_argv()
            print(f"[grove-mcp] watch: spawn: {' '.join(cmd)}", flush=True)
            proc = subprocess.Popen(cmd)
            reload_requested = False
            while proc.poll() is None:
                time.sleep(0.5)
                for p in grove_dir.glob("*.py"):
                    try:
                        cur = p.stat().st_mtime
                    except OSError:
                        continue
                    old = mtimes.get(p)
                    if old is None or cur != old:
                        reload_requested = True
                        break
                if reload_requested:
                    print("[grove-mcp] watch: source changed — restarting child", flush=True)
                    proc.terminate()
                    try:
                        proc.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    mtimes = _snapshot_grove_mtimes(grove_dir)
                    break
            else:
                rc = proc.returncode if proc is not None else -1
                if rc == 0:
                    print("[grove-mcp] watch: child exited cleanly — supervisor done", flush=True)
                    return
                print(f"[grove-mcp] watch: child exited {rc}; retry in 2s", flush=True)
                time.sleep(2)
                mtimes = _snapshot_grove_mtimes(grove_dir)
    except KeyboardInterrupt:
        print("[grove-mcp] watch: interrupted", flush=True)
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


def main():
    if "--serve" in sys.argv:
        print(f"[grove-mcp] serving on http://127.0.0.1:{_PORT}/mcp  (OAuth: {'enabled' if _SERVE_MODE else 'disabled'})", flush=True)
        mcp.run(transport="streamable-http", mount_path="/")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    if "--watch" in sys.argv:
        if "--serve" not in sys.argv:
            print("[grove-mcp] error: --watch requires --serve", file=sys.stderr)
            sys.exit(2)
        _watch_serve_supervisor()
    else:
        main()
