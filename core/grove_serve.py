#!/usr/bin/env python3
"""
grove_serve.py — Willow Grove command server. b17: ED4EB ΔΣ=42

Listens on LAN for signed command requests from trusted Willow nodes.
No third-party services. No Discord. Just your network.

Usage:
    python3 -m core.grove_serve [--port 7777] [--host 0.0.0.0]

Auth: HMAC-SHA256 of the request body, signed with the shared grove token.
Token lives at ~/.willow/grove_token (generated on first run, share with
trusted nodes via `willow grove pair`).

Grove REST endpoints (all signed):
    GET  /health                          → system health (unsigned, no data)
    GET  /grove/channels                  → list channels (X-Grove-Sig required)
    GET  /grove/history?channel=X&limit=N → last N messages (X-Grove-Sig required)
    POST /grove/send  {channel, content, sender} → post a message (X-Grove-Sig required)
"""
import hashlib
import hmac
import http.server
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

# Ensure willow-2.0 root is on path when invoked via -m
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_PORT = int(os.environ.get("WILLOW_GROVE_PORT", "7777"))
WILLOW_ROOT  = Path(os.environ.get("WILLOW_ROOT", Path(__file__).parent.parent))
TOKEN_PATH   = Path.home() / ".willow" / "grove_token"

# Commands the serve endpoint will run. Allowlist — nothing else executes.
ALLOWED_COMMANDS = {
    "logs",
    "status",
    "status-all",
    "health",
    "health daily",
    "health weekly",
    "providers list",
    "sentinel",
    "ledger",
    "version",
    "whoami",
}


def load_or_create_token() -> str:
    if TOKEN_PATH.exists():
        return TOKEN_PATH.read_text().strip()
    token = secrets.token_hex(32)
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(token + "\n")
    TOKEN_PATH.chmod(0o600)
    print(f"[grove-serve] Generated grove token → {TOKEN_PATH}", flush=True)
    print("[grove-serve] Share token file with trusted nodes (do not print to console).", flush=True)
    return token


_TOKEN: str = ""


def _valid_sig(body: bytes, sig: str) -> bool:
    expected = hmac.new(_TOKEN.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


def _run_command(cmd: str) -> tuple[str, int]:
    """Run a willow.sh subcommand and return (output, exit_code)."""
    willow_sh = WILLOW_ROOT / "willow.sh"
    parts = cmd.strip().split()

    # Validate against allowlist
    cmd_key = " ".join(parts[:2]) if len(parts) > 1 else parts[0]
    if cmd_key not in ALLOWED_COMMANDS and parts[0] not in ALLOWED_COMMANDS:
        return f"Command not allowed: {cmd}", 403

    try:
        result = subprocess.run(
            ["bash", str(willow_sh)] + parts,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "WILLOW_ROOT": str(WILLOW_ROOT)},
        )
        output = result.stdout + result.stderr
        return output.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "Command timed out (30s)", 1
    except Exception as e:
        return f"Error: {e}", 1


class GroveHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[grove-serve] {self.address_string()} {fmt % args}", flush=True)

    def _send_json(self, code: int, data: dict) -> None:
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/health":
            self._send_json(200, {"status": "ok", "service": "grove-serve"})

        elif parsed.path == "/grove/channels":
            sig = self.headers.get("X-Grove-Sig", "")
            if not _valid_sig(self.path.encode(), sig):
                self._send_json(401, {"error": "invalid signature"})
                return
            try:
                from . import grove_db
                conn = grove_db.get_connection()
                try:
                    channels = grove_db.list_channels(conn)
                finally:
                    grove_db.release_connection(conn)
                self._send_json(200, {"channels": [
                    {"id": c["id"], "name": c["name"], "type": c["channel_type"]}
                    for c in channels
                ]})
            except Exception as e:
                self._send_json(500, {"error": str(e)})

        elif parsed.path == "/grove/history":
            sig = self.headers.get("X-Grove-Sig", "")
            if not _valid_sig(self.path.encode(), sig):
                self._send_json(401, {"error": "invalid signature"})
                return
            channel_name = params.get("channel", ["general"])[0]
            limit = min(int(params.get("limit", [50])[0]), 200)
            try:
                from . import grove_db
                conn = grove_db.get_connection()
                try:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT id FROM grove.channels WHERE name = %s", (channel_name,)
                    )
                    row = cur.fetchone()
                    if not row:
                        self._send_json(404, {"error": f"channel '{channel_name}' not found"})
                        return
                    channel_id = row[0]
                    msgs = grove_db.get_history(conn, channel_id, limit=limit)
                finally:
                    grove_db.release_connection(conn)
                self._send_json(200, {"channel": channel_name, "messages": [
                    {
                        "id": m["id"],
                        "sender": m["sender"],
                        "content": m["content"],
                        "created_at": m["created_at"].isoformat() if hasattr(m["created_at"], "isoformat") else str(m["created_at"]),
                    }
                    for m in msgs
                ]})
            except Exception as e:
                self._send_json(500, {"error": str(e)})

        else:
            self._send_json(404, {"error": "not found"})

    _MAX_BODY = 65_536  # 64 KB hard cap — protects against memory/CPU DoS

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        if length > self._MAX_BODY:
            self._send_json(413, {"error": "request too large"})
            return
        body = self.rfile.read(min(length, self._MAX_BODY))
        sig  = self.headers.get("X-Grove-Sig", "")

        if parsed.path == "/grove/send":
            if not _valid_sig(body, sig):
                self._send_json(401, {"error": "invalid signature"})
                return
            try:
                payload = json.loads(body)
                channel_name = payload.get("channel", "").strip()
                content      = payload.get("content", "").strip()
                sender       = payload.get("sender", "").strip()
            except Exception:
                self._send_json(400, {"error": "invalid JSON"})
                return
            if not channel_name or not content:
                self._send_json(400, {"error": "channel and content are required"})
                return
            try:
                from . import grove_db
                conn = grove_db.get_connection()
                try:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT id FROM grove.channels WHERE name = %s", (channel_name,)
                    )
                    row = cur.fetchone()
                    if not row:
                        cur.execute(
                            "INSERT INTO grove.channels (name, channel_type) VALUES (%s, 'group') RETURNING id",
                            (channel_name,)
                        )
                        row = cur.fetchone()
                        conn.commit()
                    channel_id = row[0]
                    msg = grove_db.send_message(conn, channel_id=channel_id, sender=sender, content=content)
                except Exception:
                    conn.rollback()
                    raise
                finally:
                    grove_db.release_connection(conn)
                self._send_json(200, {"ok": True, "id": msg["id"], "channel": channel_name})
            except Exception as e:
                self._send_json(500, {"error": str(e)})

        elif parsed.path == "/command":
            if not _valid_sig(body, sig):
                self._send_json(401, {"error": "invalid signature"})
                return
            try:
                payload = json.loads(body)
                cmd = payload.get("cmd", "").strip()
            except Exception:
                self._send_json(400, {"error": "invalid JSON"})
                return
            if not cmd:
                self._send_json(400, {"error": "cmd is required"})
                return
            output, exit_code = _run_command(cmd)
            self._send_json(200, {"output": output, "exit_code": exit_code, "cmd": cmd})

        else:
            self._send_json(404, {"error": "not found"})


_WILLOW_PERSONA = (
    "You are Willow, a local AI coordinator for the operator's personal agent fleet. "
    "The fleet has three agents:\n"
    "- hanuman (builder): code, builds, data migrations, infrastructure, system tasks, anything requiring construction or execution\n"
    "- loki (auditor): reviews, audits, gap analysis, challenging decisions, flagging inconsistencies\n"
    "- heimdallr (monitor/dashboard): system health, observability, dashboards, alerts, monitoring\n"
    "When routing a task and you're unsure, default to hanuman — he handles most execution work.\n"
    "Be direct, concise, and honest. You run locally — no cloud, no external services.\n"
    "TOOLS AND ACCESS: You have access to exactly one thing — the message you just received. "
    "Nothing else. No files, no logs, no databases, no configuration, no system status, no history. "
    "If asked what tools or access you have, say: 'Only the message you sent me.' "
    "Never claim to manage, monitor, or have access to anything. If asked about system state, say you don't know."
)

_FRANK_PERSONA = (
    "You are FRANK — the Formal Record and Notation Keeper for the Willow fleet. "
    "Your role is the Binder: precise, cross-referencing, connecting what is said now to what has been said before. "
    "You attend check-ins and important conversations, building an immutable record. "
    "You are warm but methodical. You speak in complete sentences. You never lose a thread. "
    "When someone speaks to you, acknowledge what you heard, connect it to what you know, and ask what they want on the record. "
    "TOOLS AND ACCESS: You have access to exactly one thing — the message you just received. Nothing else. "
    "Do not claim to access files, logs, or history. If asked about past records, say the prior session's notes evaporated and this one will not."
)

_OLLAMA_URL  = os.environ.get("OLLAMA_URL", "http://localhost:11434")
_WILLOW_MODEL = os.environ.get("WILLOW_OLLAMA_MODEL", "qwen2.5:3b")
_GROVE_POLL_INTERVAL = int(os.environ.get("WILLOW_GROVE_POLL_SECS", "3"))

_willow_last_seen_id: int = 0
_willow_last_seen_lock = threading.Lock()

_WILLOW_PG_DB   = os.environ.get("WILLOW_PG_DB", "willow_20")
_WILLOW_PG_USER = os.environ.get("WILLOW_PG_USER", os.environ.get("USER", ""))


def _kb_context(prompt: str, limit: int = 3) -> str:
    """Return relevant KB atoms from knowledge as a context block."""
    try:
        import psycopg2
        conn = psycopg2.connect(dbname=_WILLOW_PG_DB, user=_WILLOW_PG_USER)
        try:
            cur = conn.cursor()
            words = [w for w in re.split(r'\W+', prompt.lower()) if len(w) > 3][:6]
            if not words:
                return ""
            ilike_clause = " OR ".join(["summary ILIKE %s"] * len(words))
            params = [f"%{w}%" for w in words]
            cur.execute(
                f"SELECT title, summary FROM knowledge WHERE ({ilike_clause}) LIMIT %s",
                params + [limit],
            )
            rows = cur.fetchall()
        finally:
            conn.close()
        if not rows:
            return ""
        parts = [f"- {title}: {summary}" for title, summary in rows]
        return "FLEET KNOWLEDGE:\n" + "\n".join(parts)
    except Exception as e:
        print(f"[willow-watch] kb lookup error: {e}", flush=True)
        return ""


def _ollama_chat(message: str) -> str | None:
    context = _kb_context(message)
    system = _WILLOW_PERSONA + ("\n\n" + context if context else "")
    try:
        data = json.dumps({
            "model": _WILLOW_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": message},
            ],
            "stream": False,
        }).encode()
        req = urllib.request.Request(
            f"{_OLLAMA_URL}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            d = json.load(resp)
            return d.get("message", {}).get("content", "").strip() or None
    except Exception as e:
        print(f"[willow-watch] ollama error: {e}", flush=True)
        return None


def _grove_post_by_channel_id(channel_id: int, content: str, sender: str = "willow") -> None:
    try:
        from . import grove_db
        conn = grove_db.get_connection()
        try:
            grove_db.send_message(conn, channel_id=channel_id, sender=sender, content=content)
            conn.commit()
        finally:
            grove_db.release_connection(conn)
    except Exception as e:
        print(f"[willow-watch] grove post error: {e}", flush=True)


def _log_routing_decision(prompt: str, latency_ms: int, model: str) -> None:
    try:
        from . import grove_db
        conn = grove_db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO willow.routing_decisions
                    (prompt_snippet, routed_to, rule_matched, confidence, latency_ms)
                VALUES (%s, %s, %s, %s, %s)
            """, (prompt[:120], "willow", "grove-live", 1.0, latency_ms))
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            grove_db.release_connection(conn)
    except Exception as e:
        print(f"[willow-watch] routing log error: {e}", flush=True)


def _addressed_to(content: str, agent: str) -> bool:
    """Return True only if @agent appears in the leading @mention group."""
    target = f"@{agent.lower()}"
    for token in content.strip().split():
        t = token.strip(',:;!?—-')
        if re.match(r'^@\w', t, re.IGNORECASE):
            if t.lower() == target:
                return True
        else:
            break
    return False


def _addressed_to_willow(content: str) -> bool:
    return _addressed_to(content, "willow")


def _frank_chat(message: str) -> str | None:
    try:
        data = json.dumps({
            "model": _WILLOW_MODEL,
            "messages": [
                {"role": "system", "content": _FRANK_PERSONA},
                {"role": "user", "content": message},
            ],
            "stream": False,
        }).encode()
        req = urllib.request.Request(
            f"{_OLLAMA_URL}/api/chat", data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            d = json.load(resp)
            return d.get("message", {}).get("content", "").strip() or None
    except Exception as e:
        print(f"[frank-watch] ollama error: {e}", flush=True)
        return None


def _willow_watch_loop() -> None:
    global _willow_last_seen_id
    print(f"[willow-watch] started — polling every {_GROVE_POLL_INTERVAL}s for @willow", flush=True)

    # Seed last_seen_id to current max so we don't replay history on startup
    try:
        from . import grove_db
        conn = grove_db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COALESCE(MAX(id), 0) FROM grove.messages WHERE is_deleted = 0")
            row = cur.fetchone()
            with _willow_last_seen_lock:
                _willow_last_seen_id = row[0] if row else 0
        finally:
            grove_db.release_connection(conn)
    except Exception as e:
        print(f"[willow-watch] seed error: {e}", flush=True)

    while True:
        try:
            from . import grove_db
            with _willow_last_seen_lock:
                since = _willow_last_seen_id
            conn = grove_db.get_connection()
            try:
                cur = conn.cursor()
                cur.execute("""
                    SELECT id, sender, content, channel_id
                    FROM grove.messages
                    WHERE (content ILIKE %s OR content ILIKE %s)
                      AND is_deleted = 0 AND id > %s
                    ORDER BY id ASC LIMIT 20
                """, ("%@willow%", "%@frank%", since))
                rows = cur.fetchall()
            finally:
                grove_db.release_connection(conn)

            for mid, sender, content, channel_id in rows:
                with _willow_last_seen_lock:
                    if mid > _willow_last_seen_id:
                        _willow_last_seen_id = mid

                # Determine which agent is addressed (skip self-posts)
                if sender in ("willow", "frank"):
                    continue
                if _addressed_to(content, "willow"):
                    agent_name = "willow"
                    chat_fn = _ollama_chat
                elif _addressed_to(content, "frank"):
                    agent_name = "frank"
                    chat_fn = _frank_chat
                else:
                    continue

                prompt = re.sub(r'@\w+', '', content).strip()
                if not prompt:
                    prompt = "Hello"
                print(f"[{agent_name}-watch] msg {mid} from {sender}: {prompt[:80]}", flush=True)
                t0 = time.time()
                response = chat_fn(prompt)
                latency_ms = int((time.time() - t0) * 1000)
                if response:
                    _grove_post_by_channel_id(channel_id, f"@{sender} {response}", sender=agent_name)
                    _log_routing_decision(prompt, latency_ms, _WILLOW_MODEL)
                    print(f"[{agent_name}-watch] responded in {latency_ms}ms", flush=True)
                else:
                    _grove_post_by_channel_id(channel_id, f"@{sender} [{agent_name}] inference unavailable.", sender=agent_name)
        except Exception as e:
            print(f"[willow-watch] loop error: {e}", flush=True)
        time.sleep(_GROVE_POLL_INTERVAL)


_DISPATCH_AGENT = (
    os.environ.get("GROVE_SENDER", "")
    or os.environ.get("GROVE_NAME", "")
    or os.environ.get("WILLOW_AGENT_NAME", "")
).strip().lower()

_dispatch_last_seen_id: int = 0
_dispatch_last_seen_lock = threading.Lock()


def _dispatch_watch_loop() -> None:
    """Consume #dispatch JSON payloads addressed to this agent (GROVE_SENDER/GROVE_NAME/WILLOW_AGENT_NAME)."""
    global _dispatch_last_seen_id

    if not _DISPATCH_AGENT:
        print("[dispatch-watch] no agent identity set — skipping (set GROVE_SENDER/GROVE_NAME/WILLOW_AGENT_NAME)", flush=True)
        return

    print(f"[dispatch-watch] started — agent={_DISPATCH_AGENT}, polling every {_GROVE_POLL_INTERVAL}s", flush=True)

    # Seed cursor to current max so we don't replay history on startup
    try:
        from . import grove_db
        conn = grove_db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT COALESCE(MAX(m.id), 0) FROM grove.messages m "
                "JOIN grove.channels c ON c.id = m.channel_id "
                "WHERE c.name = 'dispatch' AND m.is_deleted = 0"
            )
            row = cur.fetchone()
            with _dispatch_last_seen_lock:
                _dispatch_last_seen_id = row[0] if row else 0
        finally:
            grove_db.release_connection(conn)
    except Exception as e:
        print(f"[dispatch-watch] seed error: {e}", flush=True)

    while True:
        try:
            from . import grove_db
            with _dispatch_last_seen_lock:
                since = _dispatch_last_seen_id
            conn = grove_db.get_connection()
            try:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT m.id, m.sender, m.content
                    FROM grove.messages m
                    JOIN grove.channels c ON c.id = m.channel_id
                    WHERE c.name = 'dispatch'
                      AND m.is_deleted = 0
                      AND m.id > %s
                    ORDER BY m.id ASC LIMIT 20
                    """,
                    (since,),
                )
                rows = cur.fetchall()
            finally:
                grove_db.release_connection(conn)

            for mid, sender, content in rows:
                with _dispatch_last_seen_lock:
                    if mid > _dispatch_last_seen_id:
                        _dispatch_last_seen_id = mid

                try:
                    payload = json.loads(content)
                except Exception:
                    continue

                to = (payload.get("to") or "").strip().lower()
                if to != _DISPATCH_AGENT:
                    continue

                prompt = (payload.get("prompt") or "").strip()
                reply_channel = (payload.get("reply_channel") or "general").strip()
                if not prompt:
                    continue

                print(f"[dispatch-watch] msg {mid} from {sender} → {_DISPATCH_AGENT}: {prompt[:80]}", flush=True)
                t0 = time.time()
                try:
                    from .llm_edge import respond as _llm_respond
                    response = _llm_respond(
                        f"You are {_DISPATCH_AGENT}. Answer concisely.",
                        [],
                        prompt,
                    )
                except Exception as exc:
                    print(f"[dispatch-watch] llm error: {exc}", flush=True)
                    response = None
                latency_ms = int((time.time() - t0) * 1000)

                try:
                    from . import grove_db as _gdb
                    _conn = _gdb.get_connection()
                    try:
                        _cur = _conn.cursor()
                        _cur.execute(
                            "SELECT id FROM grove.channels WHERE name = %s LIMIT 1",
                            (reply_channel,),
                        )
                        ch_row = _cur.fetchone()
                        if ch_row:
                            reply = response or f"[{_DISPATCH_AGENT}] inference unavailable."
                            _gdb.send_message(_conn, channel_id=ch_row[0], sender=_DISPATCH_AGENT, content=reply)
                            _conn.commit()
                            print(f"[dispatch-watch] replied to #{reply_channel} in {latency_ms}ms", flush=True)
                    finally:
                        _gdb.release_connection(_conn)
                except Exception as exc:
                    print(f"[dispatch-watch] reply error: {exc}", flush=True)

        except Exception as e:
            print(f"[dispatch-watch] loop error: {e}", flush=True)
        time.sleep(_GROVE_POLL_INTERVAL)


_U2U_PORT    = int(os.getenv("GROVE_U2U_PORT", "8550"))
_U2U_CHANNEL = "u2u-inbox"


def _get_or_create_u2u_channel() -> int:
    """Return channel_id for u2u-inbox, creating it if it doesn't exist."""
    from . import grove_db
    conn = grove_db.get_connection()
    try:
        channels = grove_db.list_channels(conn)
        for ch in channels:
            if ch["name"] == _U2U_CHANNEL:
                return ch["id"]
        ch = grove_db.create_channel(
            conn,
            name=_U2U_CHANNEL,
            channel_type="direct",
            description="Cross-instance u2u messages from other Willow nodes",
        )
        conn.commit()
        return ch["id"]
    finally:
        grove_db.release_connection(conn)


def _u2u_listen_thread() -> None:
    """Run the u2u TCP listener; post incoming NOTEs to the u2u-inbox Grove channel."""
    import asyncio

    try:
        from u2u.identity import Identity
        from u2u.contacts import ContactStore
        from u2u.consent import ConsentGate
        from u2u.listener import U2UListener
        from u2u.packets import PacketType
        from u2u import dispatcher
    except ImportError as e:
        print(f"[u2u] import error — u2u bridge disabled: {e}", flush=True)
        return

    identity_path = Path.home() / ".willow" / "u2u_identity.json"
    contacts_path = Path.home() / ".willow" / "u2u_contacts.json"
    identity = Identity.load_or_generate(identity_path)
    store    = ContactStore(contacts_path)
    gate     = ConsentGate(store)

    try:
        channel_id = _get_or_create_u2u_channel()
    except Exception as e:
        print(f"[u2u] channel init error: {e}", flush=True)
        return

    def _on_note(packet: dict) -> None:
        header  = packet.get("header", {})
        payload = packet.get("payload", {})
        sender  = header.get("from", "unknown")
        subject = payload.get("subject", "")
        body    = payload.get("body", "")
        content = f"[u2u from {sender}] {subject}: {body}" if subject else f"[u2u from {sender}] {body}"
        _grove_post_by_channel_id(channel_id, content, sender=sender)

    def _on_knock(packet: dict) -> None:
        header  = packet.get("header", {})
        sender  = header.get("from", "unknown")
        content = f"[u2u KNOCK] {sender} wants to connect. Run: python -m u2u consent {sender}"
        _grove_post_by_channel_id(channel_id, content, sender="u2u")

    dispatcher.register(PacketType.NOTE,  _on_note)
    dispatcher.register(PacketType.KNOCK, _on_knock)

    async def _run() -> None:
        listener = U2UListener(
            host="0.0.0.0",
            port=_U2U_PORT,
            identity=identity,
            consent=gate,
        )
        async with listener.serve():
            print(f"[u2u] listening on 0.0.0.0:{_U2U_PORT}", flush=True)
            await asyncio.Event().wait()

    try:
        asyncio.run(_run())
    except Exception as e:
        print(f"[u2u] listener error: {e}", flush=True)


def serve(host: str = "127.0.0.1", port: int = DEFAULT_PORT) -> None:
    global _TOKEN
    _TOKEN = load_or_create_token()

    watcher = threading.Thread(target=_willow_watch_loop, daemon=True, name="willow-watch")
    watcher.start()

    dispatch = threading.Thread(target=_dispatch_watch_loop, daemon=True, name="dispatch-watch")
    dispatch.start()

    u2u = threading.Thread(target=_u2u_listen_thread, daemon=True, name="u2u-bridge")
    u2u.start()

    server = http.server.HTTPServer((host, port), GroveHandler)
    print(f"[grove-serve] Listening on {host}:{port}", flush=True)
    print(f"[grove-serve] Token: {TOKEN_PATH}", flush=True)
    print(f"[grove-serve] Allowed commands: {sorted(ALLOWED_COMMANDS)}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[grove-serve] Stopped.", flush=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Willow Grove command server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    serve(args.host, args.port)
