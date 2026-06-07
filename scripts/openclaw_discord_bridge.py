#!/usr/bin/env python3
"""
openclaw_discord_bridge.py — Mode A: Discord phone UX ↔ Grove fleet (desktop gateway).

Inbound (Discord → Grove):
  Poll OpenClaw session transcripts for new user lines; parse commands:
    grove:<channel> <text>   → post to Grove channel
    status-all | health | fleet_status | status  → run willow.sh, reply on Discord

Outbound (Grove → Discord):
  Forward new messages from configured Grove channels (default: alerts, handoffs).

Config: ~/.willow/openclaw_discord.json  (see willow/fylgja/config/openclaw_discord.example.json)
State:  ~/.willow/openclaw_discord_state.json

Requires: OpenClaw gateway running with Discord configured; Postgres grove schema on desktop.

b17: OCDCB · ΔΣ=42
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from willow.fylgja.willow_home import willow_home

_FLEET = willow_home(_ROOT)
CONFIG_PATH = _FLEET / "openclaw_discord.json"
STATE_PATH = _FLEET / "openclaw_discord_state.json"
WILLOW_SH = _ROOT / "willow.sh"
_openclaw_bin_cache: Path | None = None

ALLOWED_WILLOW_CMDS = frozenset({"status-all", "health", "fleet_status", "status"})
GROVE_CMD_RE = re.compile(r"^grove:(#?[\w-]+)?\s*(.*)$", re.IGNORECASE | re.DOTALL)
HANDOFF_RE = re.compile(r"^handoff\s+(\S+)\s*$", re.IGNORECASE)
DOCKET_RE = re.compile(
    r"^(?:docket|what(?:'s| is) on the docket)\s*$",
    re.IGNORECASE,
)
DISCORD_SNOWFLAKE_RE = re.compile(r"^\d{17,20}$")
DISCORD_CONFIG_PLACEHOLDERS = frozenset(
    {"REPLACE_WITH_CHANNEL_ID", "replace_with_channel_id", "YOUR_CHANNEL_ID"}
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def find_openclaw_bin() -> Path | None:
    """Resolve openclaw CLI (fnm/npm global PATH, OPENCLAW_BIN, common install dirs)."""
    global _openclaw_bin_cache
    if _openclaw_bin_cache is not None and _openclaw_bin_cache.is_file():
        return _openclaw_bin_cache

    env = os.environ.get("OPENCLAW_BIN", "").strip()
    if env:
        p = Path(env).expanduser()
        if p.is_file():
            _openclaw_bin_cache = p
            return p

    for candidate in (
        shutil.which("openclaw"),
        str(Path.home() / ".local" / "bin" / "openclaw"),
        str(Path.home() / ".openclaw" / "bin" / "openclaw"),
    ):
        if candidate:
            p = Path(candidate)
            if p.is_file():
                _openclaw_bin_cache = p
                return p

    npm = shutil.which("npm")
    if npm:
        try:
            r = subprocess.run(
                [npm, "prefix", "-g"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if r.returncode == 0:
                guess = Path(r.stdout.strip()) / "bin" / "openclaw"
                if guess.is_file():
                    _openclaw_bin_cache = guess
                    return guess
        except (OSError, subprocess.TimeoutExpired):
            pass

    return None


def load_config() -> dict:
    if not CONFIG_PATH.is_file():
        raise FileNotFoundError(
            f"Missing {CONFIG_PATH} — copy willow/fylgja/config/openclaw_discord.example.json"
        )
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def load_state() -> dict:
    if STATE_PATH.is_file():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"inbound_last_ms": 0, "grove_cursors": {}}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def parse_command(text: str, *, default_channel: str = "general") -> dict | None:
    """Parse a Discord user line into an action dict, or None to ignore."""
    raw = (text or "").strip()
    if not raw or raw.startswith("/"):
        return None

    m = GROVE_CMD_RE.match(raw)
    if m:
        ch = (m.group(1) or default_channel).lstrip("#").lower()
        body = (m.group(2) or "").strip()
        if ch in ALLOWED_WILLOW_CMDS:
            return {"type": "willow_cmd", "cmd": ch}
        if not body:
            return None
        return {"type": "grove_send", "channel": ch, "content": body}

    hm = HANDOFF_RE.match(raw)
    if hm:
        return {"type": "handoff", "agent": hm.group(1).lower()}

    if DOCKET_RE.match(raw):
        return {"type": "handoff", "agent": "willow"}

    token = raw.split(None, 1)[0].lower()
    if token in ALLOWED_WILLOW_CMDS:
        return {"type": "willow_cmd", "cmd": token}

    return None


def _openclaw_run(args: list[str], timeout: int = 30) -> dict:
    oc = find_openclaw_bin()
    if oc is None:
        return {
            "error": (
                "openclaw CLI not found — install with `npm install -g openclaw` "
                "or set OPENCLAW_BIN to the binary path"
            ),
        }
    try:
        result = subprocess.run(
            [str(oc), *args, "--json"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return {"error": (result.stderr or result.stdout or f"exit {result.returncode}").strip()}
        try:
            return json.loads(result.stdout) if result.stdout.strip() else {"ok": True}
        except json.JSONDecodeError:
            return {"raw": result.stdout.strip()}
    except Exception as exc:
        return {"error": str(exc)}


def _extract_channel_id(cfg: dict) -> str | None:
    raw = str(cfg.get("discord_channel_id") or "").strip()
    if DISCORD_SNOWFLAKE_RE.match(raw):
        return raw
    target = str(cfg.get("discord_target") or "")
    m = re.match(r"^channel:(\d{17,20})$", target.strip(), re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def validate_discord_targets(cfg: dict) -> str | None:
    """Return a user-facing error if bridge Discord targets are still placeholders."""
    ch = str(cfg.get("discord_channel_id") or "").strip()
    if not ch or ch.upper() in DISCORD_CONFIG_PLACEHOLDERS or "REPLACE" in ch.upper():
        return (
            "discord_channel_id is still a placeholder — in Discord: Settings → Advanced → "
            "Developer Mode ON, then right-click your #willow-fleet channel → Copy Channel ID, "
            f"and set both discord_channel_id and discord_target in {CONFIG_PATH}"
        )
    if not DISCORD_SNOWFLAKE_RE.match(ch):
        return (
            f"discord_channel_id must be a numeric snowflake (17–20 digits), got: {ch!r}"
        )
    target = str(cfg.get("discord_target") or f"channel:{ch}").strip()
    if "REPLACE" in target.upper() or not re.match(r"^channel:\d{17,20}$", target, re.I):
        return (
            f"discord_target must be channel:<numeric_id>, e.g. channel:{ch} — edit {CONFIG_PATH}"
        )
    return None


def send_discord(cfg: dict, message: str) -> dict:
    err = validate_discord_targets(cfg)
    if err:
        return {"error": err}
    ch_id = _extract_channel_id(cfg)
    target = cfg.get("discord_target") or f"channel:{ch_id}"
    # Discord messages cap at 2000 chars
    if len(message) > 1900:
        message = message[:1900] + "\n…(truncated)"
    return _openclaw_run(
        ["message", "send", "--message", message, "--target", target, "--channel", "discord"],
        timeout=45,
    )


def _poll_inbound(since_ms: int, agent_id: str) -> list[dict]:
    from sap.openclaw_ingest import _poll_transcripts

    return _poll_transcripts(since_ms=since_ms, agent_id=agent_id, max_messages=50)


def _ensure_channel(conn, name: str) -> int:

    cur = conn.cursor()
    cur.execute("SELECT id FROM channels WHERE name = %s", (name,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO channels (name, channel_type) VALUES (%s, 'group') RETURNING id",
        (name,),
    )
    cid = cur.fetchone()[0]
    conn.commit()
    return cid


def grove_post(channel: str, content: str, sender: str) -> dict:
    from core import grove_db

    try:
        conn = grove_db.get_connection()
        try:
            cid = _ensure_channel(conn, channel)
            msg = grove_db.send_message(conn, channel_id=cid, sender=sender, content=content)
            return {"ok": True, "id": msg["id"], "channel": channel}
        finally:
            grove_db.release_connection(conn)
    except Exception as exc:
        return {"error": str(exc)}


def run_willow_cmd(cmd: str) -> str:
    if cmd not in ALLOWED_WILLOW_CMDS:
        return f"Command not allowed: {cmd}"
    if not WILLOW_SH.is_file():
        return f"willow.sh not found at {WILLOW_SH}"
    try:
        result = subprocess.run(
            ["bash", str(WILLOW_SH), cmd],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(_ROOT),
            env={**os.environ, "WILLOW_ROOT": str(_ROOT)},
        )
        out = (result.stdout or "") + (result.stderr or "")
        out = out.strip() or f"(exit {result.returncode}, no output)"
        return out[:3500]
    except subprocess.TimeoutExpired:
        return "Command timed out (60s)"
    except Exception as exc:
        return f"Error: {exc}"


def fetch_handoff(agent: str) -> str:
    if not WILLOW_SH.is_file():
        return f"willow.sh not found at {WILLOW_SH}"
    try:
        result = subprocess.run(
            ["bash", str(WILLOW_SH), "handoff_latest", agent],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(_ROOT),
            env={**os.environ, "WILLOW_ROOT": str(_ROOT)},
        )
        out = (result.stdout or "").strip()
        if result.returncode != 0:
            out = (result.stderr or out or f"exit {result.returncode}").strip()
        return out[:3500] or "(empty handoff)"
    except Exception as exc:
        return f"handoff error: {exc}"


def handle_inbound(cfg: dict, state: dict) -> int:
    agent_id = cfg.get("openclaw_agent_id", "main")
    since_ms = int(state.get("inbound_last_ms") or 0)
    messages = _poll_inbound(since_ms, agent_id)
    if not messages:
        return 0

    sender = cfg.get("grove_sender", "discord-bridge")
    default_ch = cfg.get("grove_default_channel", "general")
    handled = 0
    max_ts = since_ms

    for msg in messages:
        ts = int(msg.get("timestamp_ms") or 0)
        if ts > max_ts:
            max_ts = ts
        action = parse_command(msg.get("content", ""), default_channel=default_ch)
        if not action:
            continue

        reply = ""
        if action["type"] == "grove_send":
            res = grove_post(action["channel"], action["content"], sender)
            if res.get("ok"):
                reply = f"✓ Grove #{action['channel']} (id {res.get('id')})"
            else:
                reply = f"✗ Grove post failed: {res.get('error', res)}"
        elif action["type"] == "willow_cmd":
            reply = f"```{action['cmd']}```\n" + run_willow_cmd(action["cmd"])
        elif action["type"] == "handoff":
            reply = fetch_handoff(action["agent"])

        if reply:
            send_discord(cfg, reply)
            handled += 1

    state["inbound_last_ms"] = max_ts
    return handled


def forward_grove(cfg: dict, state: dict) -> int:
    from core import grove_db

    channels = cfg.get("grove_forward_channels") or ["alerts", "handoffs"]
    prefix = cfg.get("discord_forward_prefix", "🌿 ")
    cursors: dict[str, int] = dict(state.get("grove_cursors") or {})
    sent = 0

    try:
        conn = grove_db.get_connection()
        try:
            for name in channels:
                cur = conn.cursor()
                cur.execute("SELECT id FROM channels WHERE name = %s", (name,))
                row = cur.fetchone()
                if not row:
                    continue
                cid = row[0]
                since_id = int(cursors.get(name) or 0)
                msgs = grove_db.get_history(conn, cid, limit=20, since_id=since_id)
                for m in msgs:
                    mid = int(m["id"])
                    sender = m.get("sender") or "?"
                    content = (m.get("content") or "").strip()
                    if not content:
                        cursors[name] = max(cursors.get(name, 0), mid)
                        continue
                    # Skip our own bridge posts echoing back
                    if sender == cfg.get("grove_sender", "discord-bridge"):
                        cursors[name] = max(cursors.get(name, 0), mid)
                        continue
                    line = f"{prefix}**#{name}** · {sender}\n{content}"
                    res = send_discord(cfg, line)
                    if "error" not in res:
                        sent += 1
                    cursors[name] = max(cursors.get(name, 0), mid)
        finally:
            grove_db.release_connection(conn)
    except Exception as exc:
        print(f"[openclaw-discord] grove forward error: {exc}", file=sys.stderr, flush=True)

    state["grove_cursors"] = cursors
    return sent


def run_loop(cfg: dict, *, once: bool = False) -> int:
    interval = max(10, int(cfg.get("poll_interval_sec", 30)))
    state = load_state()
    print(
        f"[openclaw-discord] started — discord target={cfg.get('discord_target')} "
        f"forward={cfg.get('grove_forward_channels')}",
        flush=True,
    )

    while True:
        try:
            n_in = handle_inbound(cfg, state)
            n_out = forward_grove(cfg, state)
            save_state(state)
            if n_in or n_out:
                print(
                    f"[openclaw-discord] {_now_iso()} inbound={n_in} forwarded={n_out}",
                    flush=True,
                )
        except Exception as exc:
            print(f"[openclaw-discord] cycle error: {exc}", file=sys.stderr, flush=True)

        if once:
            break
        time.sleep(interval)
    return 0


def cmd_init_example() -> int:
    example = _ROOT / "willow" / "fylgja" / "config" / "openclaw_discord.example.json"
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.exists():
        print(f"Already exists: {CONFIG_PATH}")
        return 0
    CONFIG_PATH.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Created {CONFIG_PATH}")
    print(
        "Required: replace REPLACE_WITH_CHANNEL_ID with your Discord channel snowflake "
        "(Developer Mode → right-click channel → Copy Channel ID). "
        "Set discord_channel_id and discord_target to channel:<that_id>."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-config", help="Copy example config to ~/.willow/")
    run_p = sub.add_parser("run", help="Poll loop (Ctrl-C to stop)")
    run_p.add_argument("--once", action="store_true", help="Single cycle")
    test_p = sub.add_parser("test-discord", help="Send test message to Discord")
    test_p.add_argument("message", nargs="?", default="Willow OpenClaw Discord bridge test")
    sub.add_parser("test-grove", help="Post test message to Grove #general")

    args = parser.parse_args()
    if args.cmd == "init-config":
        return cmd_init_example()

    if args.cmd == "test-grove":
        cfg = load_config() if CONFIG_PATH.is_file() else {}
        res = grove_post("general", "Discord bridge test (grove)", cfg.get("grove_sender", "discord-bridge"))
        print(json.dumps(res, indent=2))
        return 0 if res.get("ok") else 1

    cfg = load_config()
    if not cfg.get("enabled", True):
        print("Bridge disabled in config (enabled: false)", file=sys.stderr)
        return 0

    if args.cmd == "test-discord":
        res = send_discord(cfg, args.message)
        print(json.dumps(res, indent=2))
        return 0 if "error" not in res else 1

    if args.cmd == "run":
        return run_loop(cfg, once=args.once)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
