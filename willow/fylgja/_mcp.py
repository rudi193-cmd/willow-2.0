"""
_mcp.py — Willow MCP direct client.
b17: FYGJ1  ΔΣ=42

Dispatches hook→MCP calls directly to Python implementations.
No subprocess. No stale binary. No init handshake. No auth gap.

Tool groups:
  store_*                → core.store_port.StorePort (WillowStoreAdapter)
  grove_*                → core.grove_client
  willow_knowledge_*     → core.pg_bridge + core.embedder
  willow_handoff_*       → sap.sap_mcp (via subprocess fallback)
  everything else        → subprocess fallback (willow-mcp binary)
"""
import json
import os
import subprocess
import threading
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent  # willow-2.0/
_WILLOW_MCP = Path(os.environ.get(
    "WILLOW_MCP_BIN",
    str(Path.home() / ".local" / "bin" / "willow-mcp")
))

# ---------------------------------------------------------------------------
# Direct store dispatch
# ---------------------------------------------------------------------------

_store = None


def _get_store():
    global _store
    if _store is None:
        import sys
        if str(_REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(_REPO_ROOT))
        from core.store_port import get_store_port
        _store = get_store_port()
    return _store


def _dispatch_store(tool_name: str, arguments: dict):
    store = _get_store()
    col = arguments.get("collection", "")

    if tool_name == "store_put":
        record = arguments.get("record", {})
        record_id = arguments.get("record_id") or record.get("id")
        result = store.put(col, record, record_id=record_id)
        if isinstance(result, tuple):
            rid, action = result[0], result[1]
            return {"id": rid, "action": action}
        return {"id": record_id or "", "action": "written"}

    if tool_name == "store_get":
        record_id = arguments.get("record_id") or arguments.get("id", "")
        result = store.get(col, record_id)
        return result if result is not None else {"error": "not_found"}

    if tool_name == "store_list":
        return store.all(col) or []

    if tool_name == "store_search":
        query = arguments.get("query", "")
        after = arguments.get("after")
        return store.search(col, query, after=after) or []

    if tool_name == "store_search_all":
        return store.search_all(arguments.get("query", "")) or []

    if tool_name == "store_delete":
        record_id = arguments.get("record_id", "")
        return store.delete(col, record_id)

    if tool_name == "store_update":
        record_id = arguments.get("record_id", "")
        record = arguments.get("record", {})
        result = store.update(col, record_id, record)
        if isinstance(result, tuple):
            return {"id": result[0], "action": result[1]}
        return {"id": record_id, "action": "updated"}

    if tool_name == "store_add_edge":
        return store.add_edge(
            arguments.get("from_collection", ""),
            arguments.get("from_id", ""),
            arguments.get("to_collection", ""),
            arguments.get("to_id", ""),
            arguments.get("label", ""),
        )

    if tool_name == "store_edges_for":
        return store.edges_for(col, arguments.get("record_id", "")) or []

    if tool_name == "store_stats":
        return store.stats() or {}

    if tool_name == "store_audit":
        return store.audit() or {}

    return {"error": f"unknown store tool: {tool_name}"}


# ---------------------------------------------------------------------------
# Direct soil dispatch — same StorePort backend as the MCP server's soil_ tools
# (sap/sap_mcp.py: soil_ → store → WillowStore). Mirrors that module's
# semantics so a hook write lands exactly where soil_get/soil_list will read it,
# without the subprocess willow-mcp spawn + init handshake the fallback requires.
# ---------------------------------------------------------------------------

def _qualifies_as_flag(record: dict, deviation: float) -> bool:
    # Mirror of sap.sap_mcp._qualifies_as_flag — keep in sync.
    return (
        record.get("type") in ("failure-log",) or
        record.get("domain") == "governance" or
        deviation > 0.6 or
        (record.get("type") == "gap" and record.get("severity") in ("high", "critical"))
    )


def _dispatch_soil(tool_name: str, arguments: dict):
    store = _get_store()
    col = arguments.get("collection", "")

    if tool_name == "soil_put":
        record = arguments.get("record", {})
        record_id = arguments.get("record_id") or record.get("id")
        deviation = arguments.get("deviation", 0.0) or 0.0
        result = store.put(col, record, record_id=record_id or None, deviation=deviation)
        # StorePort.put returns (id, action) or (id, action, proposals)
        if isinstance(result, tuple):
            rid = result[0]
            action = result[1] if len(result) > 1 else "written"
            proposals = result[2] if len(result) > 2 else None
        else:
            rid, action, proposals = (record_id or ""), "written", None
        out: dict = {"id": rid, "action": action}
        if proposals:
            out["proposals"] = [p.to_dict() for p in proposals]
        # Auto-flag qualifying records into {namespace}/flags — mirrors soil_put
        if not col.endswith("/flags") and _qualifies_as_flag(record, deviation):
            from datetime import datetime, timezone
            namespace = col.split("/")[0]
            store.put(f"{namespace}/flags", {
                "atom_id": rid,
                "collection": col,
                "deviation": deviation,
                "ts": datetime.now(timezone.utc).isoformat(),
            })
        return out

    if tool_name == "soil_get":
        record_id = arguments.get("record_id") or arguments.get("id", "")
        result = store.get(col, record_id)
        return result if result is not None else {"error": "not_found"}

    if tool_name == "soil_list":
        return store.all(col) or []

    if tool_name == "soil_search":
        query = arguments.get("query", "")
        after = arguments.get("after") or None
        if arguments.get("semantic"):
            return store.search_semantic(col, query) or []
        return store.search(col, query, after=after) or []

    if tool_name == "soil_search_all":
        return store.search_all(arguments.get("query", "")) or []

    if tool_name == "soil_delete":
        return store.delete(col, arguments.get("record_id", ""))

    if tool_name == "soil_update":
        record_id = arguments.get("record_id", "")
        record = arguments.get("record", {})
        result = store.update(col, record_id, record)
        if isinstance(result, tuple):
            return {"id": result[0], "action": result[1]}
        return {"id": record_id, "action": "updated"}

    if tool_name == "soil_edges_for":
        return store.edges_for(arguments.get("record_id", "")) or []

    if tool_name == "soil_stats":
        return store.stats() or {}

    return {"error": f"unknown soil tool: {tool_name}"}


# ---------------------------------------------------------------------------
# Direct grove dispatch — raw psycopg2 to grove.* schema
# ---------------------------------------------------------------------------

def _grove_connect():
    import psycopg2
    db = os.environ.get("WILLOW_PG_DB", "willow_20")
    user = os.environ.get("WILLOW_PG_USER", os.environ.get("USER", ""))
    conn = psycopg2.connect(dbname=db, user=user)
    conn.autocommit = True
    return conn


def _dispatch_grove(tool_name: str, arguments: dict):
    try:
        conn = _grove_connect()
        cur = conn.cursor()

        if tool_name == "grove_send_message":
            channel = arguments.get("channel_name", arguments.get("channel", ""))
            cur.execute("SELECT id FROM grove.channels WHERE name=%s LIMIT 1", (channel,))
            row = cur.fetchone()
            if not row:
                return {"error": f"channel not found: {channel}"}
            cur.execute(
                "INSERT INTO grove.messages (channel_id, sender, content) VALUES (%s, %s, %s) RETURNING id",
                (row[0], arguments.get("sender", ""), arguments.get("content", "")),
            )
            msg_id = cur.fetchone()[0]
            conn.close()
            return {"id": msg_id, "ok": True}

        if tool_name == "grove_reply":
            cur.execute("SELECT channel_id FROM grove.messages WHERE id=%s LIMIT 1",
                        (arguments.get("parent_id", 0),))
            row = cur.fetchone()
            if not row:
                return {"error": "parent message not found"}
            cur.execute(
                "INSERT INTO grove.messages (channel_id, sender, content, parent_id) VALUES (%s, %s, %s, %s) RETURNING id",
                (row[0], arguments.get("sender", ""), arguments.get("content", ""), arguments.get("parent_id")),
            )
            msg_id = cur.fetchone()[0]
            conn.close()
            return {"id": msg_id, "ok": True}

        if tool_name == "grove_get_history":
            channel = arguments.get("channel_name", arguments.get("channel", ""))
            cur.execute("SELECT id FROM grove.channels WHERE name=%s LIMIT 1", (channel,))
            row = cur.fetchone()
            if not row:
                return {"result": []}
            since_id = arguments.get("since_id", 0)
            limit = min(arguments.get("limit", 50), 200)
            cur.execute(
                "SELECT id, sender, content, created_at FROM grove.messages "
                "WHERE channel_id=%s AND id>%s AND is_deleted=0 ORDER BY id ASC LIMIT %s",
                (row[0], since_id, limit),
            )
            rows = cur.fetchall()
            conn.close()
            return {"result": [{"id": r[0], "sender": r[1], "content": r[2],
                                 "created_at": str(r[3])} for r in rows]}

        if tool_name == "grove_heartbeat":
            cur.execute("SELECT id FROM grove.channels WHERE name='heartbeat' LIMIT 1")
            row = cur.fetchone()
            if row:
                cur.execute(
                    "INSERT INTO grove.messages (channel_id, sender, content) VALUES (%s, %s, %s)",
                    (row[0], arguments.get("sender", ""), "♥"),
                )
            conn.close()
            return {"ok": True}

        conn.close()
    except Exception as e:
        return {"error": f"grove dispatch error: {e}"}
    return {"error": f"unknown grove tool: {tool_name}"}


# ---------------------------------------------------------------------------
# Subprocess fallback (for tools not covered by direct dispatch)
# Sends proper MCP initialize handshake.
# ---------------------------------------------------------------------------

def _unwrap_tool_response(data: dict) -> dict:
    """Unwrap MCP content envelope → plain dict."""
    inner = data.get("result", data)
    if isinstance(inner, dict) and "content" in inner:
        for block in inner["content"]:
            if block.get("type") == "text":
                try:
                    return json.loads(block["text"])
                except Exception:
                    return {"text": block["text"]}
    return inner


def _subprocess_call(tool_name: str, arguments: dict, timeout: int) -> dict:
    init_msg = json.dumps({
        "jsonrpc": "2.0", "id": 0,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "willow-hook", "version": "1"},
        },
    })
    initialized_notif = json.dumps({
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    })
    tool_msg = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    })

    env = os.environ.copy()
    env.setdefault("WILLOW_SAFE_ROOT", str(Path.home() / "github" / "SAFE" / "Applications"))
    env.setdefault("WILLOW_PG_DB", "willow_20")
    env.setdefault("WILLOW_PG_USER", os.environ.get("USER", ""))


    def _read_line(stream, wait_secs) -> str | None:
        """Read one non-empty line from stream with a wall-clock timeout."""
        box: list = []
        def _worker():
            while True:
                line = stream.readline()
                if line.strip():
                    box.append(line.strip())
                    return
                if not line:   # EOF
                    return
        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join(wait_secs)
        return box[0] if box else None

    try:
        proc = subprocess.Popen(
            [str(_WILLOW_MCP)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
    except Exception as e:
        return {"error": str(e), "tool": tool_name}

    try:
        # Step 1 — send initialize, wait for init response
        proc.stdin.write(init_msg + "\n")
        proc.stdin.flush()
        init_line = _read_line(proc.stdout, wait_secs=min(timeout, 8))
        if not init_line:
            return {"error": "timeout_on_init", "tool": tool_name}

        # Step 2 — send initialized notification + tool call; keep stdin open until
        # the response arrives, then close. Closing stdin early triggers FastMCP's
        # stdio transport shutdown which cancels the in-flight tool handler.
        proc.stdin.write(initialized_notif + "\n" + tool_msg + "\n")
        proc.stdin.flush()
        tool_line = _read_line(proc.stdout, wait_secs=timeout)
        proc.stdin.close()
        if not tool_line:
            return {"error": "no_tool_response", "tool": tool_name}

        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
    except Exception as e:
        return {"error": str(e), "tool": tool_name}
    finally:
        try:
            proc.kill()
        except Exception:
            pass

    try:
        data = json.loads(tool_line)
        if data.get("id") == 1:
            return _unwrap_tool_response(data)
        return {"error": "unexpected_response_id", "raw": tool_line[:200], "tool": tool_name}
    except Exception as e:
        return {"error": f"parse_error: {e}", "tool": tool_name}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def call(tool_name: str, arguments: dict, timeout: int = 10) -> dict:
    """Dispatch a tool call. Direct path for store/grove; subprocess fallback for all else."""
    if tool_name.startswith("store_"):
        try:
            return _dispatch_store(tool_name, arguments)
        except Exception as e:
            return {"error": f"store dispatch error: {e}", "tool": tool_name}

    if tool_name.startswith("grove_"):
        try:
            return _dispatch_grove(tool_name, arguments)
        except Exception as e:
            return {"error": f"grove dispatch error: {e}", "tool": tool_name}

    if tool_name.startswith("soil_"):
        try:
            return _dispatch_soil(tool_name, arguments)
        except Exception as e:
            return {"error": f"soil dispatch error: {e}", "tool": tool_name}

    return _subprocess_call(tool_name, timeout=timeout, arguments=arguments)
