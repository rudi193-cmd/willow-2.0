#!/usr/bin/env python3
"""
openclaw_discord_watch.py — Keep OpenClaw gateway + Discord bridge healthy; wake agents on issues.

Checks every INTERVAL seconds:
  - openclaw-gateway (systemd user)
  - openclaw_discord_bridge.py process
  - Ollama API reachable
  - Recent Discord session replies (fake tool JSON in assistant text)

Auto-heal (default on): restart gateway, start bridge if missing.

State:  ~/.willow/openclaw-discord-watch-state.json
Log:    ~/.willow/openclaw-discord-watch.log
PID:    ~/.willow/openclaw-discord-watch.pid

Wake sentinel (for Cursor /loop monitors):
  AGENT_LOOP_WAKE_OPENCLAW_DISCORD {"prompt":"...", "changed":true, ...}

Usage:
  python3 scripts/openclaw_discord_watch.py run [--interval 90] [--no-heal]
  python3 scripts/openclaw_discord_watch.py run-once [--emit-wake] [--no-heal]
  python3 scripts/openclaw_discord_watch.py status
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from willow.fylgja.willow_home import willow_home

_FLEET = willow_home(_ROOT)
BRIDGE_SCRIPT = _ROOT / "scripts" / "openclaw_discord_bridge.py"
WILLOW_SH = _ROOT / "willow.sh"

STATE_PATH = _FLEET / "openclaw-discord-watch-state.json"
LOG_PATH = _FLEET / "openclaw-discord-watch.log"
PID_PATH = _FLEET / "openclaw-discord-watch.pid"
BRIDGE_PID_PATH = _FLEET / "openclaw-discord-bridge.pid"
BRIDGE_LOG_PATH = _FLEET / "openclaw-discord-bridge.log"
SESSIONS_DIR = Path.home() / ".openclaw" / "agents" / "main" / "sessions"

BAD_REPLY_RE = re.compile(
    r'sessions_spawn|"name"\s*:\s*"(?:message|sessions_|exec)"|Message failed',
    re.IGNORECASE,
)
DISCORD_SESSION_KEY = "discord:channel"

WAKE_PROMPT = (
    "OpenClaw Discord watch tick: read ~/.willow/openclaw-discord-watch-state.json "
    "and tail ~/.willow/openclaw-discord-watch.log. If gateway down, bridge down, "
    "Ollama down, or bad_bot_reply in issues — fix autonomously on the ThinkPad "
    "(restart openclaw-gateway, start willow openclaw-discord run, patch "
    "~/.openclaw/openclaw.json / models.json supportsTools, smoke-test with "
    "openclaw agent --local). Only report to user if you changed something material; "
    "otherwise stay quiet when all healthy."
)

DEFAULT_INTERVAL = 90


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log(msg: str) -> None:
    line = f"[{_now_iso()}] {msg}"
    print(line, flush=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _user_env() -> dict[str, str]:
    uid = os.getuid()
    env = {**os.environ, "WILLOW_ROOT": str(_ROOT)}
    env.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{uid}/bus")
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{uid}")
    return env


def _load_state() -> dict:
    if STATE_PATH.is_file():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def _save_state(state: dict) -> None:
    state["updated_at"] = _now_iso()
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _watch_already_running() -> bool:
    try:
        pid = int(PID_PATH.read_text(encoding="utf-8").strip())
        return _pid_alive(pid)
    except (FileNotFoundError, ValueError):
        return False


def _write_pid() -> None:
    PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    PID_PATH.write_text(str(os.getpid()), encoding="utf-8")


def _cleanup(*_) -> None:
    try:
        PID_PATH.unlink(missing_ok=True)
    except OSError:
        pass
    sys.exit(0)


def _run(cmd: list[str], *, timeout: int = 30, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env or _user_env(),
        cwd=str(_ROOT),
        check=False,
    )


def check_gateway() -> tuple[bool, str]:
    r = _run(["systemctl", "--user", "is-active", "openclaw-gateway.service"], timeout=10)
    ok = r.stdout.strip() == "active"
    detail = (r.stdout or r.stderr or "").strip() or f"exit {r.returncode}"
    return ok, detail


def restart_gateway() -> bool:
    _log("heal: restarting openclaw-gateway.service")
    r = _run(["systemctl", "--user", "restart", "openclaw-gateway.service"], timeout=60)
    time.sleep(2)
    ok, _ = check_gateway()
    if ok:
        _log("heal: gateway active after restart")
    else:
        _log(f"heal: gateway restart failed: {(r.stderr or r.stdout).strip()}")
    return ok


def _bridge_pgrep() -> list[int]:
    r = _run(["pgrep", "-f", "openclaw_discord_bridge.py"], timeout=10)
    if r.returncode != 0:
        return []
    return [int(x) for x in r.stdout.split() if x.strip().isdigit()]


def check_bridge() -> tuple[bool, str]:
    pids = _bridge_pgrep()
    if pids:
        return True, f"pids={pids}"
    if BRIDGE_PID_PATH.is_file():
        try:
            pid = int(BRIDGE_PID_PATH.read_text(encoding="utf-8").strip())
            if _pid_alive(pid):
                return True, f"pid={pid}"
        except ValueError:
            pass
    return False, "not running"


def start_bridge() -> bool:
    if not BRIDGE_SCRIPT.is_file():
        _log(f"heal: bridge script missing at {BRIDGE_SCRIPT}")
        return False
    BRIDGE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log_f = BRIDGE_LOG_PATH.open("a", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            [sys.executable, str(BRIDGE_SCRIPT), "run"],
            stdout=log_f,
            stderr=subprocess.STDOUT,
            cwd=str(_ROOT),
            env=_user_env(),
            start_new_session=True,
        )
    except OSError as exc:
        _log(f"heal: bridge start failed: {exc}")
        return False
    BRIDGE_PID_PATH.write_text(str(proc.pid), encoding="utf-8")
    _log(f"heal: started bridge pid={proc.pid} log={BRIDGE_LOG_PATH}")
    time.sleep(2)
    ok, detail = check_bridge()
    if not ok:
        _log(f"heal: bridge may have exited early ({detail})")
    return ok


def check_ollama() -> tuple[bool, str]:
    r = _run(
        ["curl", "-sf", "--max-time", "5", "http://127.0.0.1:11434/api/tags"],
        timeout=8,
    )
    if r.returncode == 0:
        return True, "ok"
    return False, (r.stderr or r.stdout or f"exit {r.returncode}").strip()[:200]


def scan_bad_discord_replies(*, max_files: int = 8, max_age_hours: float = 3.0) -> list[dict]:
    """Recent assistant lines in Discord sessions that look like tool JSON spam."""
    if not SESSIONS_DIR.is_dir():
        return []
    hits: list[dict] = []
    jsonl_files = sorted(
        SESSIONS_DIR.glob("*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:max_files]
    cutoff = time.time() - max_age_hours * 3600
    for path in jsonl_files:
        if ".trajectory." in path.name:
            continue
        try:
            if path.stat().st_mtime < cutoff:
                continue
        except OSError:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
        except OSError:
            continue
        session_text = "\n".join(lines)
        if DISCORD_SESSION_KEY not in session_text:
            continue
        for line in lines:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = row.get("message") or {}
            if msg.get("role") != "assistant":
                continue
            text_parts = []
            for block in msg.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text") or "")
            text = " ".join(text_parts)
            if text and BAD_REPLY_RE.search(text):
                hits.append(
                    {
                        "session": path.stem,
                        "snippet": text[:120],
                        "ts": row.get("timestamp", ""),
                    }
                )
                break
    return hits[:5]


def collect_snapshot(*, heal: bool) -> dict:
    gw_ok, gw_detail = check_gateway()
    br_ok, br_detail = check_bridge()
    ol_ok, ol_detail = check_ollama()
    bad = scan_bad_discord_replies()
    issues: list[str] = []

    if not gw_ok:
        issues.append("gateway_down")
        if heal:
            restart_gateway()
            gw_ok, gw_detail = check_gateway()
    if not br_ok:
        issues.append("bridge_down")
        if heal:
            start_bridge()
            br_ok, br_detail = check_bridge()
    if not ol_ok:
        issues.append("ollama_down")
    if bad:
        issues.append("bad_bot_reply")

    return {
        "gateway": {"ok": gw_ok, "detail": gw_detail},
        "bridge": {"ok": br_ok, "detail": br_detail},
        "ollama": {"ok": ol_ok, "detail": ol_detail},
        "bad_replies": bad,
        "issues": issues,
        "healthy": not issues,
    }


def _emit_wake(snapshot: dict, *, changed: bool) -> None:
    payload = {
        "prompt": WAKE_PROMPT,
        "changed": changed,
        "healthy": snapshot.get("healthy"),
        "issues": snapshot.get("issues", []),
    }
    line = f"AGENT_LOOP_WAKE_OPENCLAW_DISCORD {json.dumps(payload, separators=(',', ':'))}"
    _log(line)


def run_once(*, emit_wake: bool = False, heal: bool = True) -> dict:
    prev = _load_state()
    snap = collect_snapshot(heal=heal)
    prev_issues = prev.get("issues") or []
    changed = snap.get("issues") != prev_issues or snap.get("healthy") != prev.get("healthy")
    if not prev:
        changed = True

    out = {**snap, "previous_issues": prev_issues}
    _save_state(out)

    if emit_wake and (changed or snap.get("issues")):
        _emit_wake(snap, changed=changed)
    elif emit_wake and not snap.get("healthy"):
        _emit_wake(snap, changed=False)

    status = "healthy" if snap.get("healthy") else f"issues={snap.get('issues')}"
    _log(f"tick {status} gateway={snap['gateway']['ok']} bridge={snap['bridge']['ok']} ollama={snap['ollama']['ok']}")
    return snap


def cmd_status() -> int:
    snap = collect_snapshot(heal=False)
    print(json.dumps(snap, indent=2))
    return 0 if snap.get("healthy") else 1


def cmd_run(interval: int, *, emit_wake: bool, heal: bool) -> int:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if _watch_already_running():
        existing = PID_PATH.read_text(encoding="utf-8").strip()
        _log(f"already running pid={existing}")
        return 0
    signal.signal(signal.SIGTERM, _cleanup)
    signal.signal(signal.SIGINT, _cleanup)
    _write_pid()
    _log(f"watch started interval={interval}s heal={heal} emit_wake={emit_wake}")

    # First tick immediately (loop skill: run once at arm)
    run_once(emit_wake=emit_wake, heal=heal)

    while True:
        time.sleep(interval)
        run_once(emit_wake=emit_wake, heal=heal)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="One-shot JSON status (no heal)")
    run_p = sub.add_parser("run", help="Daemon loop")
    run_p.add_argument("--interval", type=int, default=DEFAULT_INTERVAL)
    run_p.add_argument("--no-heal", action="store_true")
    run_p.add_argument("--emit-wake", action="store_true", default=True)
    once_p = sub.add_parser("run-once", help="Single check")
    once_p.add_argument("--emit-wake", action="store_true")
    once_p.add_argument("--no-heal", action="store_true")

    args = parser.parse_args()
    heal = not getattr(args, "no_heal", False)

    if args.cmd == "status":
        return cmd_status()
    if args.cmd == "run-once":
        snap = run_once(emit_wake=args.emit_wake, heal=heal)
        return 0 if snap.get("healthy") else 1
    if args.cmd == "run":
        return cmd_run(args.interval, emit_wake=args.emit_wake, heal=heal)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
