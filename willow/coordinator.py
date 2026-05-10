#!/usr/bin/env python3
"""
willow/coordinator.py — Willow local coordinator.
Watches Grove, routes tasks, feeds Kart. Runs on yggdrasil:v9.

Run: python3 -m willow.coordinator
Env:
  WILLOW_COORDINATOR_API_URL       (default: http://localhost:11434/v1/chat/completions)
  WILLOW_COORDINATOR_MODEL         (default: yggdrasil:v9)
  WILLOW_COORDINATOR_SILENCE_SECS  (default: 600 — 10 minutes)
  WILLOW_COORDINATOR_HEARTBEAT_SECS (default: 300 — 5 minutes)
  WILLOW_PG_DB  WILLOW_PG_USER
"""
import json
import logging
import os
import select
import sys
import time
import urllib.request
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

import psycopg2
import psycopg2.extensions

sys.path.insert(0, str(Path(__file__).parent.parent))

log = logging.getLogger("willow.coordinator")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

# ── Config ────────────────────────────────────────────────────────────────────
COORDINATOR_SENDER = "willow"
FLEET_SENDERS      = frozenset({"hanuman", "heimdallr", "vishwakarma", "loki"})
SEAN_SENDER        = "sean-campbell"

API_URL        = os.environ.get("WILLOW_COORDINATOR_API_URL",        "http://localhost:11434/v1/chat/completions")
MODEL          = os.environ.get("WILLOW_COORDINATOR_MODEL",          "yggdrasil:v9")
SILENCE_SECS   = int(os.environ.get("WILLOW_COORDINATOR_SILENCE_SECS",    "600"))
HEARTBEAT_SECS = int(os.environ.get("WILLOW_COORDINATOR_HEARTBEAT_SECS",  "300"))

_BLOCKED_KEYWORDS = frozenset({"blocked", "waiting", "unclear", "stuck", "need"})


# ── Signal model ──────────────────────────────────────────────────────────────
class Signal(str, Enum):
    SEAN_DIRECT   = "sean_direct"
    FLEET_BLOCKED = "fleet_blocked"
    WILLOW_TAGGED = "willow_tagged"
    SILENCE_FEED  = "silence_feed"


def _is_blocked(content: str) -> bool:
    cl = content.lower()
    return any(kw in cl for kw in _BLOCKED_KEYWORDS)


def classify_message(msg: dict) -> Optional[Signal]:
    sender  = msg.get("sender", "")
    content = msg.get("content", "")

    if sender == SEAN_SENDER:
        return Signal.SEAN_DIRECT                          # always fires, skip oracle

    if "@willow" in content:
        return Signal.FLEET_BLOCKED if sender in FLEET_SENDERS else Signal.WILLOW_TAGGED

    if sender in FLEET_SENDERS and _is_blocked(content):
        return Signal.FLEET_BLOCKED

    return None


# ── DB helpers ────────────────────────────────────────────────────────────────
def _dsn() -> str:
    db   = os.environ.get("WILLOW_PG_DB",   "willow_19")
    user = os.environ.get("WILLOW_PG_USER", os.environ.get("USER", ""))
    return f"dbname={db} user={user}"


def _grove_connect():
    conn = psycopg2.connect(_dsn())
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    conn.cursor().execute("LISTEN grove_channel;")
    return conn


def _fetch_message(channel_id: int) -> Optional[dict]:
    try:
        conn = psycopg2.connect(_dsn())
        with conn.cursor() as cur:
            cur.execute("""
                SELECT m.id, c.name, m.sender, m.content, m.created_at
                  FROM grove.messages m
                  JOIN grove.channels c ON c.id = m.channel_id
                 WHERE m.channel_id = %s AND m.is_deleted = 0
                 ORDER BY m.id DESC LIMIT 1
            """, (channel_id,))
            row = cur.fetchone()
        conn.close()
        if row:
            return {"id": row[0], "channel": row[1], "sender": row[2],
                    "content": row[3], "created_at": str(row[4])}
    except Exception as e:
        log.warning("fetch_message failed: %s", e)
    return None


def _grove_post(content: str, channel: str = "general") -> None:
    try:
        conn = psycopg2.connect(_dsn())
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM grove.channels WHERE name = %s", (channel,))
            row = cur.fetchone()
            if not row:
                cur.execute(
                    "INSERT INTO grove.channels (name) VALUES (%s) RETURNING id",
                    (channel,)
                )
                row = cur.fetchone()
            cur.execute(
                "INSERT INTO grove.messages (channel_id, sender, content) VALUES (%s, %s, %s)",
                (row[0], COORDINATOR_SENDER, content),
            )
        conn.commit()
        conn.close()
        log.info("Posted to #%s: %s", channel, content[:80])
    except Exception as e:
        log.error("grove_post failed: %s", e)


def _kart_pending_count() -> int:
    try:
        conn = psycopg2.connect(_dsn())
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM public.tasks WHERE status = 'pending'")
            n = cur.fetchone()[0]
        conn.close()
        return n
    except Exception:
        return 0


def _kart_submit(cmd: str, agent: str = "kart") -> None:
    try:
        conn = psycopg2.connect(_dsn())
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO public.tasks (task, status, submitted_by, agent)"
                " VALUES (%s, 'pending', %s, %s)",
                (cmd, COORDINATOR_SENDER, agent),
            )
        conn.commit()
        conn.close()
        log.info("Kart: submitted → %s", cmd[:80])
    except Exception as e:
        log.error("kart_submit failed: %s", e)


def _kb_context(limit: int = 8) -> str:
    """Pull recent learning atoms for LLM context injection."""
    try:
        conn = psycopg2.connect(_dsn())
        with conn.cursor() as cur:
            cur.execute("""
                SELECT title, summary FROM knowledge
                 WHERE source_type IN ('learned', 'discovered_pattern', 'correction', 'behavioral_pattern')
                   AND invalid_at IS NULL
                 ORDER BY created_at DESC LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
        conn.close()
        return "\n".join(f"- {r[0]}: {r[1]}" for r in rows) if rows else ""
    except Exception:
        return ""


# ── LLM call ──────────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = (
    "You are Willow, the local coordinator for a multi-agent AI fleet. "
    "Your job is to route work, unblock agents, and keep the fleet moving. "
    "Be concise — one short paragraph maximum. Do not over-explain. "
    "When an agent is blocked, route the task or submit it to the queue. "
    "When Sean speaks, acknowledge and act. "
    "If you decide work needs to be queued, end your reply with exactly: "
    "KART: <shell command or task description>"
)


def _llm_call(signal: Signal, msg: dict, kb_ctx: str) -> Optional[str]:
    user_msg = f"[signal={signal.value}] [{msg.get('sender')} in #{msg.get('channel')}]: {msg.get('content','')[:400]}"
    if kb_ctx:
        user_msg += f"\n\n[Recent KB context]\n{kb_ctx}"

    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system",  "content": _SYSTEM_PROMPT},
            {"role": "user",    "content": user_msg},
        ],
        "stream": False,
    }).encode()

    try:
        req = urllib.request.Request(
            API_URL, data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = json.loads(resp.read())
            # Support both Ollama and OpenAI response shapes
            return (
                raw.get("message", {}).get("content", "").strip()
                or raw.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            )
    except Exception as e:
        log.error("LLM call failed: %s", e)
        return None


# ── Signal handlers ───────────────────────────────────────────────────────────
def _handle(signal: Signal, msg: dict) -> None:
    kb_ctx = _kb_context()
    reply  = _llm_call(signal, msg, kb_ctx)
    if not reply:
        return

    channel = msg.get("channel", "general")

    if "KART:" in reply:
        grove_part, kart_part = reply.split("KART:", 1)
        kart_cmd = kart_part.strip().splitlines()[0].strip()
        if grove_part.strip():
            _grove_post(grove_part.strip(), channel)
        _kart_submit(kart_cmd)
    else:
        _grove_post(reply, channel)


def _kart_next_pending() -> Optional[str]:
    """Return the task text of the oldest pending Kart task, or None."""
    try:
        conn = psycopg2.connect(_dsn())
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, task FROM public.tasks WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1"
            )
            row = cur.fetchone()
        conn.close()
        return (row[0], row[1]) if row else None
    except Exception:
        return None


def _handle_silence_feed(pending: int) -> None:
    next_task = _kart_next_pending()
    if next_task:
        task_id, task_text = next_task
        _grove_post(f"Queue has {pending} pending — activating next task: {task_text[:80]}", "general")
        # Mark the task as running so Kart picks it up
        try:
            conn = psycopg2.connect(_dsn())
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE public.tasks SET status = 'running' WHERE id = %s AND status = 'pending'",
                    (task_id,)
                )
            conn.commit()
            conn.close()
        except Exception as e:
            log.error("silence_feed: failed to activate task %s: %s", task_id, e)
    else:
        _grove_post("Queue has pending tasks but couldn't fetch next — check Kart.", "general")


def _heartbeat(signal_counts: dict, last_signal: Optional[str]) -> None:
    """Post HEARTBEAT to #willow channel. Dashboard picks it up via grove_agents()."""
    payload = json.dumps({
        "type":          "HEARTBEAT",
        "model":         MODEL,
        "signal_counts": signal_counts,
        "last_signal":   last_signal,
        "ts":            datetime.now(timezone.utc).isoformat(),
    })
    _grove_post(payload, "willow")


# ── Main loop ─────────────────────────────────────────────────────────────────
def run() -> None:
    log.info("Willow coordinator starting — model=%s api=%s", MODEL, API_URL)

    last_fleet_activity: float = time.time()
    last_heartbeat:      float = time.time()
    last_signal_name:    Optional[str] = None
    signal_counts:       dict  = {s.value: 0 for s in Signal}

    grove_conn = None

    while True:
        now = time.time()

        # Reconnect Grove listener if needed
        if grove_conn is None:
            try:
                grove_conn = _grove_connect()
                log.info("Grove connected")
            except Exception as e:
                log.error("Grove connect failed: %s — retry in 15s", e)
                time.sleep(15)
                continue

        # Heartbeat tick (posts to #willow, not #general — doesn't reset fleet clock)
        if now - last_heartbeat >= HEARTBEAT_SECS:
            _heartbeat(signal_counts, last_signal_name)
            last_heartbeat = now

        # Silence feed (fleet clock only — coordinator heartbeat does NOT reset this)
        if now - last_fleet_activity >= SILENCE_SECS:
            pending = _kart_pending_count()
            if pending > 0:
                _handle_silence_feed(pending)
                signal_counts[Signal.SILENCE_FEED.value] += 1
                last_signal_name = Signal.SILENCE_FEED.value
            last_fleet_activity = now  # reset to avoid repeat fires this cycle

        # Grove LISTEN/NOTIFY poll (5s timeout)
        try:
            ready = select.select([grove_conn], [], [], 5)
            if ready[0]:
                grove_conn.poll()
                while grove_conn.notifies:
                    notify = grove_conn.notifies.pop()
                    try:
                        channel_id = int(notify.payload)
                    except (ValueError, TypeError):
                        continue

                    msg = _fetch_message(channel_id)
                    if not msg:
                        continue

                    sender = msg.get("sender", "")

                    # Two-clock update — fleet clock excludes coordinator's own posts
                    if sender != COORDINATOR_SENDER:
                        last_fleet_activity = now

                    # Skip own messages (prevent feedback loop)
                    if sender == COORDINATOR_SENDER:
                        continue

                    signal = classify_message(msg)
                    if signal is None:
                        continue

                    log.info("Signal %s from %s in #%s", signal.value, sender, msg.get("channel"))
                    signal_counts[signal.value] += 1
                    last_signal_name = signal.value

                    _handle(signal, msg)

        except Exception as e:
            log.error("Grove poll error: %s — reconnecting", e)
            try:
                grove_conn.close()
            except Exception:
                pass
            grove_conn = None
            continue


if __name__ == "__main__":
    run()
