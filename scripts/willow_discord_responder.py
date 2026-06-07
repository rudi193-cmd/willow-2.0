#!/usr/bin/env python3
"""
willow_discord_responder.py — Always-on Ollama-backed Discord responder.

Polls Grove 'hanuman' for discord-bridge messages, claims them atomically,
routes to Ollama inference, replies as 'hanuman' sender so discord_remote.py
outbound picks them up and forwards to Discord.

Coordination: uses ~/.willow/discord_claims.json as a shared claim file.
Any responder (Claude Code, this script, future agents) must claim a grove_id
before posting a reply. First claim wins; others skip.

Config (env, loaded from ~/.willow/env):
  OLLAMA_URL                — Ollama base URL (default: http://localhost:11434)
  WILLOW_RESPONDER_MODEL    — model for inference (default: llama3.1:8b)
  WILLOW_RESPONDER_INTERVAL — poll interval in seconds (default: 20)

Usage:
  python3 scripts/willow_discord_responder.py run [--interval 20]
  python3 scripts/willow_discord_responder.py run-once
  python3 scripts/willow_discord_responder.py status
  python3 scripts/willow_discord_responder.py stop
  python3 scripts/willow_discord_responder.py restart [--interval 20]

State:  ~/.willow/willow_responder_state.json
Log:    ~/.willow/willow_responder.log
PID:    ~/.willow/willow_responder.pid
Claims: ~/.willow/discord_claims.json

b17: WDRSP · ΔΣ=42
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

STATE_PATH = Path.home() / ".willow" / "willow_responder_state.json"
LOG_PATH = Path.home() / ".willow" / "willow_responder.log"
PID_PATH = Path.home() / ".willow" / "willow_responder.pid"
CLAIMS_PATH = Path.home() / ".willow" / "discord_claims.json"
WILLOW_ENV = Path.home() / "github" / ".willow" / "env"

GROVE_CHANNEL = "hanuman"
INBOUND_SENDER = "discord-bridge"
REPLY_SENDER = "hanuman"
MY_ID = "willow-responder"
DEFAULT_INTERVAL = 20
DEFAULT_MODEL = "llama3.1:8b"
TIER_3B = "llama3.2:3b"
TIER_8B = "llama3.1:8b"
CLAIMS_TTL_S = 3600  # prune claims older than 1 hour

# Keywords that signal a trivially simple query → route to 3b regardless of length
_SIMPLE_STARTS = (
    "hi", "hello", "hey", "ping", "yo ", "sup ",
    "status", "who are you", "what are you", "what's up", "whats up",
)

SYSTEM_PROMPT = (
    "You are Willow, the fleet coordinator for the Willow 2.0 agent fleet. "
    "Answer questions about the fleet concisely. "
    "Keep responses under 1800 characters — they will be posted to Discord. "
    "Be helpful, direct, and brief. Do not pad or hedge. "
    "If you don't know something, say so in one sentence."
)

KB_CONTEXT_LIMIT = 3  # atoms to inject per query
KB_EMBED_MODEL = "nomic-embed-text"


def _load_env() -> None:
    if WILLOW_ENV.is_file():
        for line in WILLOW_ENV.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log(msg: str) -> None:
    line = f"[{_now_iso()}] {msg}"
    print(line, flush=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


# ---------------------------------------------------------------------------
# Claim coordination
# ---------------------------------------------------------------------------

def _prune_claims(claims: dict) -> dict:
    """Remove claims older than CLAIMS_TTL_S."""
    now = time.time()
    keep = {}
    for gid, info in claims.items():
        try:
            ts_str = info.get("ts", "")
            ts = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
            if now - ts < CLAIMS_TTL_S:
                keep[gid] = info
        except Exception:
            pass
    return keep


def try_claim(grove_id: int) -> bool:
    """
    Atomically claim a grove message id. Returns True if this process got it.
    Uses fcntl.LOCK_EX for single-machine mutual exclusion.
    """
    key = str(grove_id)
    CLAIMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    mode = "r+" if CLAIMS_PATH.exists() else "w+"
    try:
        with open(CLAIMS_PATH, mode, encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.seek(0)
                content = f.read()
                claims = json.loads(content) if content.strip() else {}
                if key in claims:
                    return False  # already claimed
                claims = _prune_claims(claims)
                claims[key] = {"claimed_by": MY_ID, "ts": _now_iso()}
                f.seek(0)
                f.truncate()
                f.write(json.dumps(claims, indent=2) + "\n")
                return True
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception as exc:
        _log(f"claim error grove_id={grove_id}: {exc}")
        return False


def claim_for(grove_id: int, claimer_id: str) -> bool:
    """
    Claim on behalf of another agent (e.g. Claude Code calling this helper).
    Returns True if the claim was written (not already taken).
    """
    key = str(grove_id)
    CLAIMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    mode = "r+" if CLAIMS_PATH.exists() else "w+"
    try:
        with open(CLAIMS_PATH, mode, encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.seek(0)
                content = f.read()
                claims = json.loads(content) if content.strip() else {}
                if key in claims:
                    return False
                claims = _prune_claims(claims)
                claims[key] = {"claimed_by": claimer_id, "ts": _now_iso()}
                f.seek(0)
                f.truncate()
                f.write(json.dumps(claims, indent=2) + "\n")
                return True
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception as exc:
        _log(f"claim_for error grove_id={grove_id} claimer={claimer_id}: {exc}")
        return False


def read_claim(grove_id: int) -> str | None:
    """Return the claimer id for a grove_id, or None if unclaimed."""
    key = str(grove_id)
    if not CLAIMS_PATH.exists():
        return None
    try:
        claims = json.loads(CLAIMS_PATH.read_text(encoding="utf-8"))
        entry = claims.get(key)
        return entry["claimed_by"] if entry else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# KB search (pgvector via Postgres)
# ---------------------------------------------------------------------------

def _kb_embed(text: str) -> list | None:
    """Get embedding vector from Ollama nomic-embed-text. Returns None on failure."""
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
    payload = {"model": KB_EMBED_MODEL, "prompt": text}
    req = urllib.request.Request(
        f"{ollama_url}/api/embeddings",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read()).get("embedding")
    except Exception as exc:
        _log(f"kb_embed error: {exc}")
        return None


def _kb_context(query: str) -> str:
    """Search KB via pgvector cosine similarity. Returns formatted context for injection."""
    embedding = _kb_embed(query)
    if not embedding:
        return ""
    vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
    try:
        from core import grove_db
        conn = grove_db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT title, summary, content
                FROM knowledge
                WHERE embedding IS NOT NULL
                  AND invalid_at IS NULL
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (vec_str, KB_CONTEXT_LIMIT),
            )
            rows = cur.fetchall()
            if not rows:
                return ""
            parts = []
            for title, summary, content in rows:
                body = summary or ""
                if not body and isinstance(content, dict):
                    body = str(content.get("evidence") or content.get("summary") or "")[:300]
                if body:
                    parts.append(f"• {title}: {body[:300]}")
            if not parts:
                return ""
            return "Relevant Willow knowledge:\n" + "\n".join(parts)
        finally:
            grove_db.release_connection(conn)
    except Exception as exc:
        _log(f"kb_context error: {exc}")
        return ""


# ---------------------------------------------------------------------------
# Tier selection
# ---------------------------------------------------------------------------

def _select_tier(command: str, context: str) -> str:
    """Return TIER_3B or TIER_8B based on query complexity and KB context availability."""
    lc = command.lower().strip()
    words = command.split()
    # Trivial greetings / status pings always go to 3b
    if any(lc.startswith(p) for p in _SIMPLE_STARTS) and len(words) <= 8:
        return TIER_3B
    # Short query with no KB context → 3b can handle it
    if len(words) <= 10 and not context:
        return TIER_3B
    # KB context present or complex query → 8b
    return TIER_8B


# ---------------------------------------------------------------------------
# Ollama inference
# ---------------------------------------------------------------------------

def _infer(command: str, context: str = "", model: str = "") -> str:
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
    model = model or os.environ.get("WILLOW_RESPONDER_MODEL", DEFAULT_MODEL)
    system = SYSTEM_PROMPT if not context else f"{SYSTEM_PROMPT}\n\n{context}"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": command},
        ],
        "stream": False,
    }
    req = urllib.request.Request(
        f"{ollama_url}/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
        content = result.get("message", {}).get("content", "").strip()
        return content if content else "[no response from model]"
    except Exception as exc:
        return f"[inference error: {exc}]"


# ---------------------------------------------------------------------------
# Grove polling + reply
# ---------------------------------------------------------------------------

def _grove_poll(since_id: int) -> tuple[list[dict], int]:
    from core import grove_db
    try:
        conn = grove_db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM channels WHERE name = %s", (GROVE_CHANNEL,))
            row = cur.fetchone()
            if not row:
                return [], since_id
            cid = row[0]
            msgs = grove_db.get_history(conn, cid, limit=50, since_id=since_id)
            results = []
            max_id = since_id
            for m in msgs:
                mid = int(m["id"])
                if mid > max_id:
                    max_id = mid
                if m.get("sender") == INBOUND_SENDER:
                    results.append(m)
            return results, max_id
        finally:
            grove_db.release_connection(conn)
    except Exception as exc:
        _log(f"grove_poll error: {exc}")
        return [], since_id


def _grove_post(content: str) -> dict:
    from core import grove_db
    try:
        conn = grove_db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM channels WHERE name = %s", (GROVE_CHANNEL,))
            row = cur.fetchone()
            if not row:
                return {"error": "channel not found"}
            cid = row[0]
            msg = grove_db.send_message(conn, channel_id=cid, sender=REPLY_SENDER, content=content)
            return {"ok": True, "id": msg["id"]}
        finally:
            grove_db.release_connection(conn)
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def _grove_current_max_id() -> int:
    """Return the current max Grove message id — used to skip history on first run."""
    try:
        from core import grove_db
        conn = grove_db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM channels WHERE name = %s", (GROVE_CHANNEL,))
            row = cur.fetchone()
            if not row:
                return 0
            cid = row[0]
            cur.execute("SELECT MAX(id) FROM messages WHERE channel_id = %s", (cid,))
            row = cur.fetchone()
            return int(row[0]) if row and row[0] else 0
        finally:
            grove_db.release_connection(conn)
    except Exception:
        return 0


def _load_state() -> dict:
    if STATE_PATH.is_file():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    # No state file — start from current Grove head to avoid replaying all history
    current = _grove_current_max_id()
    _log(f"no state file — initializing cursor from Grove head (id={current})")
    return {"grove_cursor": current}


def _save_state(state: dict) -> None:
    state["updated_at"] = _now_iso()
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Main poll cycle
# ---------------------------------------------------------------------------

def run_once() -> dict:
    state = _load_state()
    since_id = int(state.get("grove_cursor", 0))
    msgs, new_cursor = _grove_poll(since_id)
    state["grove_cursor"] = new_cursor

    handled = 0
    skipped = 0
    for m in msgs:
        grove_id = int(m["id"])
        content = (m.get("content") or "").strip()
        if not content:
            continue

        # Strip the [Discord/username] prefix to get the raw command
        command = content
        if content.startswith("[Discord/") and "] " in content:
            command = content.split("] ", 1)[1].strip()

        if not try_claim(grove_id):
            _log(f"skip grove_id={grove_id} — already claimed by {read_claim(grove_id)}")
            skipped += 1
            continue

        _log(f"claimed grove_id={grove_id} | {command[:60]}")
        context = _kb_context(command)
        if context:
            _log(f"kb_context grove_id={grove_id} | {len(context)} chars injected")
        tier = _select_tier(command, context)
        _log(f"tier={tier} grove_id={grove_id}")
        response = _infer(command, context, model=tier)
        res = _grove_post(response)
        if res.get("ok"):
            _log(f"replied grove_id={grove_id} → Grove id={res['id']} | {response[:60]}")
            handled += 1
        else:
            _log(f"reply failed grove_id={grove_id}: {res.get('error')}")

    _save_state(state)
    return {"handled": handled, "skipped": skipped}


# ---------------------------------------------------------------------------
# Daemon
# ---------------------------------------------------------------------------

def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _already_running() -> bool:
    if PID_PATH.is_file():
        try:
            pid = int(PID_PATH.read_text(encoding="utf-8").strip())
            return _pid_alive(pid)
        except ValueError:
            pass
    return False


def _write_pid() -> None:
    PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    PID_PATH.write_text(str(os.getpid()), encoding="utf-8")


def _cleanup(*_) -> None:
    PID_PATH.unlink(missing_ok=True)
    _log("stopped")
    sys.exit(0)


def cmd_run(interval: int) -> int:
    if _already_running():
        _log("already running")
        return 0
    signal.signal(signal.SIGTERM, _cleanup)
    signal.signal(signal.SIGINT, _cleanup)
    _write_pid()
    model = os.environ.get("WILLOW_RESPONDER_MODEL", DEFAULT_MODEL)
    _log(f"started interval={interval}s model={model}")
    run_once()
    while True:
        time.sleep(interval)
        run_once()
    return 0


def cmd_status() -> int:
    running = _already_running()
    state = _load_state()
    print(json.dumps({"running": running, "state": state}, indent=2))
    return 0 if running else 1


def cmd_stop() -> int:
    if not PID_PATH.is_file():
        print("not running")
        return 1
    try:
        pid = int(PID_PATH.read_text(encoding="utf-8").strip())
        os.kill(pid, signal.SIGTERM)
        print(f"sent SIGTERM to {pid}")
        return 0
    except Exception as exc:
        print(f"stop failed: {exc}")
        return 1


def cmd_restart(interval: int) -> int:
    if PID_PATH.is_file():
        try:
            pid = int(PID_PATH.read_text(encoding="utf-8").strip())
            if _pid_alive(pid):
                os.kill(pid, signal.SIGTERM)
                _log(f"restart: sent SIGTERM to {pid}")
                for _ in range(20):
                    time.sleep(0.5)
                    if not _pid_alive(pid):
                        break
                else:
                    os.kill(pid, signal.SIGKILL)
                    _log(f"restart: SIGKILL to {pid} after timeout")
                    time.sleep(0.5)
            PID_PATH.unlink(missing_ok=True)
        except Exception as exc:
            _log(f"restart: kill failed: {exc}")
            PID_PATH.unlink(missing_ok=True)
    else:
        _log("restart: no PID file — starting fresh")
    _log("restart: starting")
    return cmd_run(interval)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_p = sub.add_parser("run", help="Daemon loop")
    run_p.add_argument("--interval", type=int, default=DEFAULT_INTERVAL)
    sub.add_parser("run-once", help="Single poll cycle")
    sub.add_parser("status", help="Check if running + state")
    sub.add_parser("stop", help="Stop the daemon")
    restart_p = sub.add_parser("restart", help="Stop the running daemon and start it again")
    restart_p.add_argument("--interval", type=int, default=DEFAULT_INTERVAL)

    args = parser.parse_args()
    _load_env()

    if args.cmd == "run":
        return cmd_run(args.interval)
    if args.cmd == "run-once":
        result = run_once()
        print(json.dumps(result, indent=2))
        return 0
    if args.cmd == "status":
        return cmd_status()
    if args.cmd == "stop":
        return cmd_stop()
    if args.cmd == "restart":
        return cmd_restart(args.interval)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
