#!/usr/bin/env python3
"""
discord_remote.py — Discord REST API ↔ Grove bridge for Claude Code remote control.

No openclaw dependency. Uses Discord REST API directly with DISCORD_BOT_TOKEN.

Inbound  (Discord → Grove 'hanuman'):
  Poll Discord channel for new non-bot messages → post to Grove as 'discord-bridge'

Outbound (Grove 'hanuman' → Discord):
  Poll Grove 'hanuman' for messages from 'hanuman' sender → post to Discord

Config (env, loaded from ~/.willow/env if not set in shell):
  DISCORD_BOT_TOKEN   — bot token from Discord Developer Portal
  DISCORD_CHANNEL_ID  — channel snowflake (default: 1509605940578615487)

State: ~/.willow/discord_remote_state.json
Log:   ~/.willow/discord_remote.log
PID:   ~/.willow/discord_remote.pid

Usage:
  python3 scripts/discord_remote.py run [--interval 30]
  python3 scripts/discord_remote.py run-once
  python3 scripts/discord_remote.py status
  python3 scripts/discord_remote.py test-send [message]

b17: DSCREM · ΔΣ=42
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import urllib.request
import urllib.error

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from willow.fylgja.willow_home import willow_home

_FLEET = willow_home(_ROOT)
STATE_PATH = _FLEET / "discord_remote_state.json"
LOG_PATH = _FLEET / "discord_remote.log"
PID_PATH = _FLEET / "discord_remote.pid"
WILLOW_ENV = _FLEET / "env"

DEFAULT_CHANNEL_ID = "1509605940578615487"
DISCORD_API = "https://discord.com/api/v10"
GROVE_SENDER = "discord-bridge"
GROVE_CHANNEL = "hanuman"
CLAUDE_SENDER = "hanuman"
DEFAULT_INTERVAL = 30


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


def _token() -> str:
    t = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    if not t:
        raise RuntimeError("DISCORD_BOT_TOKEN not set — add to ~/.willow/env")
    return t


def _channel_id() -> str:
    return os.environ.get("DISCORD_CHANNEL_ID", DEFAULT_CHANNEL_ID).strip()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log(msg: str) -> None:
    line = f"[{_now_iso()}] {msg}"
    print(line, flush=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _discord_request(method: str, path: str, data: dict | None = None):
    url = f"{DISCORD_API}{path}"
    body = json.dumps(data).encode() if data else None
    headers = {
        "Authorization": f"Bot {_token()}",
        "Content-Type": "application/json",
        "User-Agent": "WillowBot/1.0",
    }
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:200]
        raise RuntimeError(f"Discord {method} {path} → {exc.code}: {detail}") from exc


def _get_messages(channel_id: str, after_id: str = "0", limit: int = 50) -> list[dict]:
    path = f"/channels/{channel_id}/messages?limit={limit}"
    if after_id and after_id != "0":
        path += f"&after={after_id}"
    result = _discord_request("GET", path)
    if not isinstance(result, list):
        return []
    return sorted(result, key=lambda m: int(m.get("id", "0")))


def _send_discord(channel_id: str, content: str) -> dict:
    if len(content) > 1990:
        content = content[:1990] + "\n…(truncated)"
    return _discord_request("POST", f"/channels/{channel_id}/messages", {"content": content})


def _load_state() -> dict:
    if STATE_PATH.is_file():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"last_discord_id": "0", "grove_cursor": 0}


def _save_state(state: dict) -> None:
    state["updated_at"] = _now_iso()
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _grove_post(channel: str, content: str, sender: str) -> dict:
    from core import grove_db
    try:
        conn = grove_db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM channels WHERE name = %s", (channel,))
            row = cur.fetchone()
            if row:
                cid = row[0]
            else:
                cur.execute(
                    "INSERT INTO channels (name, channel_type) VALUES (%s, 'group') RETURNING id",
                    (channel,),
                )
                cid = cur.fetchone()[0]
                conn.commit()
            msg = grove_db.send_message(conn, channel_id=cid, sender=sender, content=content)
            return {"ok": True, "id": msg["id"]}
        finally:
            grove_db.release_connection(conn)
    except Exception as exc:
        return {"error": str(exc)}


def _grove_poll(channel: str, since_id: int, sender_filter: str) -> tuple[list[dict], int]:
    from core import grove_db
    try:
        conn = grove_db.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM channels WHERE name = %s", (channel,))
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
                if m.get("sender") == sender_filter:
                    results.append(m)
            return results, max_id
        finally:
            grove_db.release_connection(conn)
    except Exception as exc:
        _log(f"grove_poll error: {exc}")
        return [], since_id


def _handle_inbound(state: dict, channel_id: str) -> int:
    last_id = state.get("last_discord_id", "0")
    try:
        messages = _get_messages(channel_id, after_id=last_id)
    except Exception as exc:
        _log(f"inbound poll error: {exc}")
        return 0

    count = 0
    for msg in messages:
        mid = msg.get("id", "0")
        author = msg.get("author") or {}
        if author.get("bot"):
            state["last_discord_id"] = mid
            continue
        content = (msg.get("content") or "").strip()
        if not content:
            state["last_discord_id"] = mid
            continue
        username = author.get("username", "unknown")
        grove_content = f"[Discord/{username}] {content}"
        res = _grove_post(GROVE_CHANNEL, grove_content, GROVE_SENDER)
        if res.get("ok"):
            _log(f"inbound Discord→Grove id={res['id']} | {content[:60]}")
            count += 1
        else:
            _log(f"inbound grove_post failed: {res.get('error')}")
        state["last_discord_id"] = mid

    return count


def _handle_outbound(state: dict, channel_id: str) -> int:
    since_id = int(state.get("grove_cursor", 0))
    msgs, new_cursor = _grove_poll(GROVE_CHANNEL, since_id, sender_filter=CLAUDE_SENDER)
    state["grove_cursor"] = new_cursor

    count = 0
    for m in msgs:
        content = (m.get("content") or "").strip()
        if not content:
            continue
        try:
            _send_discord(channel_id, f"🤖 **hanuman** · {content}")
            count += 1
            _log(f"outbound Grove→Discord grove_id={m['id']} | {content[:60]}")
        except Exception as exc:
            _log(f"outbound send failed: {exc}")

    return count


def run_once(channel_id: str) -> dict:
    state = _load_state()
    n_in = _handle_inbound(state, channel_id)
    n_out = _handle_outbound(state, channel_id)
    _save_state(state)
    if n_in or n_out:
        _log(f"tick inbound={n_in} outbound={n_out}")
    return {"inbound": n_in, "outbound": n_out}


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
    sys.exit(0)


def cmd_run(interval: int) -> int:
    channel_id = _channel_id()
    if _already_running():
        _log("already running")
        return 0
    signal.signal(signal.SIGTERM, _cleanup)
    signal.signal(signal.SIGINT, _cleanup)
    _write_pid()
    _log(f"started channel={channel_id} interval={interval}s")
    run_once(channel_id)
    while True:
        time.sleep(interval)
        run_once(channel_id)
    return 0


def cmd_status() -> int:
    running = _already_running()
    state = _load_state()
    print(json.dumps({"running": running, "state": state}, indent=2))
    return 0 if running else 1


def cmd_test_send(message: str) -> int:
    channel_id = _channel_id()
    res = _send_discord(channel_id, message)
    print(json.dumps(res, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_p = sub.add_parser("run", help="Daemon loop")
    run_p.add_argument("--interval", type=int, default=DEFAULT_INTERVAL)
    sub.add_parser("run-once", help="Single poll cycle")
    sub.add_parser("status", help="Check if running + state")
    ts = sub.add_parser("test-send", help="Send a message to Discord")
    ts.add_argument("message", nargs="?", default="Willow remote control online ΔΣ=42")

    args = parser.parse_args()
    _load_env()

    if args.cmd == "run":
        return cmd_run(args.interval)
    if args.cmd == "run-once":
        run_once(_channel_id())
        return 0
    if args.cmd == "status":
        return cmd_status()
    if args.cmd == "test-send":
        return cmd_test_send(args.message)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
