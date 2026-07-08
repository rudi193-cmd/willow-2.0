#!/usr/bin/env python3
"""
grove_listen.py — Auto-launched Grove LISTEN/NOTIFY background monitor.
b17: GRVLS  ΔΣ=42

Launched by SessionStart hook. Writes one line per new message to stdout
(redirected to /tmp/grove-monitor.log). Automatically discovers new channels.
Claude Code tails this log via Monitor(tail -f /tmp/grove-monitor.log).

Mentions logged as [MENTION:BROADCAST] for @all; [MENTION:DIRECT:<identity>] for
@handles tied to WILLOW_AGENT_NAME, GROVE_MENTION_WATCH extras, or (by default)
Auto when primary agent is fleet (not Auto).
"""
import os
from core.agent_identity import require_agent_name
from core.grove_gate import assert_grove as _assert_grove
import re
import select
import sys
import tempfile
import time
import portalocker
from functools import lru_cache
from pathlib import Path

AGENT = require_agent_name()
_LOCK_PATH = Path(os.environ.get("GROVE_MONITOR_LOCK", str(Path(tempfile.gettempdir()) / "grove-monitor.lock")))
_PID_PATH = Path(os.environ.get("GROVE_MONITOR_PID", str(Path(tempfile.gettempdir()) / "grove-monitor.pid")))

# ── Mention watch list ────────────────────────────────────────────────────────
# Primary identity: WILLOW_AGENT_NAME (@handles via ALIASES + default @AGENT).
# Optional GROVE_MENTION_WATCH=comma,separated extras (e.g. Auto,heimdallr).
# Default when GROVE_MENTION_WATCH unset: also watch Auto if primary is not Auto
# (“Auto + @all broadcasts” fleet layout without systemd/env churn).


def _verbose_channels() -> set[str]:
    """Channel names that log every message (not only @mentions)."""
    raw = os.environ.get("GROVE_VERBOSE_CHANNELS", "")
    return {x.strip().lower() for x in raw.split(",") if x.strip()}


def _extra_watch_targets() -> list[str]:
    raw = os.environ.get("GROVE_MENTION_WATCH")
    if raw is None:
        if AGENT.strip().lower() != "auto":
            return ["Auto"]
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def _watch_identities_ordered() -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for n in [AGENT.strip(), *_extra_watch_targets()]:
        if not n:
            continue
        key = n.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(n)
    return out


def direct_mention_identity(content: str) -> str | None:
    """Which watched identity (if any) is @mentioned in content."""
    for name in _watch_identities_ordered():
        if is_direct_mention(content, name):
            return name
    return None


class _PidLock:
    """Best-effort single-instance guard plus pidfile for tooling discovery."""

    def __init__(self, lock_path: Path, pid_path: Path):
        self.lock_path = lock_path
        self.pid_path = pid_path
        self._fh = None

    def __enter__(self):
        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            self.pid_path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = open(self.lock_path, "a+", encoding="utf-8")
            portalocker.lock(self._fh, portalocker.LOCK_EX | portalocker.LOCK_NB)
            self._fh.seek(0)
            self._fh.truncate()
            self._fh.write(f"{os.getpid()}\n")
            self._fh.flush()
            self.pid_path.write_text(str(os.getpid()) + "\n")
        except BlockingIOError:
            print("[grove-listen] already running — exiting", flush=True)
            raise SystemExit(0)
        except Exception as exc:
            print(f"[grove-listen] lock failed — exiting: {exc}", file=sys.stderr, flush=True)
            raise SystemExit(1)
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if self._fh:
                self._fh.close()
        except Exception:
            pass
        try:
            if self.pid_path.exists() and self.pid_path.read_text().strip() == str(os.getpid()):
                self.pid_path.unlink(missing_ok=True)
        except Exception:
            pass
        return False


def connect():
    import psycopg2
    dsn = (
        os.environ.get("WILLOW_DB_URL")
        or f"dbname={os.environ.get('WILLOW_PG_DB', 'willow_20')} "
           f"user={os.environ.get('WILLOW_PG_USER', os.environ.get('USER', ''))}"
    )
    c = psycopg2.connect(dsn)
    c.autocommit = True
    return c


def load_channels(cur):
    cur.execute("SELECT id, name FROM grove.channels WHERE is_archived = FALSE")
    return {row[0]: row[1] for row in cur.fetchall()}


ALIASES = {
    "hanuman": ["@hanuman", "@hanu"],
    "vishwakarma": ["@vishwakarma", "@vish", "@karma"],
    "auto": ["@auto"],
}


_BROADCAST_RE = re.compile(r"(?:^|[^a-z0-9_])@all(?:[^a-z0-9_]|$)", re.IGNORECASE)


@lru_cache(maxsize=64)
def _alias_regex(alias: str) -> re.Pattern:
    """Compile once per alias string; cached for the process lifetime."""
    handle = alias.lstrip("@")
    return re.compile(rf"(?:^|[^a-z0-9_])@{re.escape(handle)}(?:[^a-z0-9_]|$)", re.IGNORECASE)


def is_broadcast_mention(content: str) -> bool:
    return _BROADCAST_RE.search(content or "") is not None


def is_direct_mention(content: str, agent: str) -> bool:
    for alias in ALIASES.get(agent.lower(), [f"@{agent}"]):
        if _alias_regex(alias).search(content or ""):
            return True
    return False


def main():
    _assert_grove("grove_listen")
    with _PidLock(_LOCK_PATH, _PID_PATH):
        _run()


def _drain_channel(cur, ch_id: int, ch_name: str, cursors: dict, verbose: set) -> None:
    """Fetch and print all messages for ch_id since cursors[ch_id]. Updates cursors in place.

    Using WHERE id > cursor means missed/coalesced notifies are harmless — the next
    drain always catches up from the last acknowledged id.
    """
    since = cursors.get(ch_id, 0)
    cur.execute(
        "SELECT id, sender, content FROM grove.messages"
        " WHERE channel_id = %s AND id > %s AND is_deleted = 0"
        " ORDER BY id ASC",
        (ch_id, since),
    )
    for row in cur.fetchall():
        cursors[ch_id] = row[0]
        msg_id, sender, content = row[0], row[1], str(row[2])
        broadcast = is_broadcast_mention(content)
        direct_id = None if broadcast else direct_mention_identity(content)
        if broadcast:
            tag = "BROADCAST"
        elif direct_id and sender.lower() != direct_id.lower():
            tag = f"DIRECT:{direct_id}"
        else:
            tag = ""
        preview = content.strip()[:80]
        if tag:
            line = f"[MENTION:{tag}] #{ch_name} id={msg_id} {sender}"
            if preview:
                line += f": {preview}"
            print(line, flush=True)
        elif ch_name.lower() in verbose:
            line = f"[CHANNEL] #{ch_name} id={msg_id} {sender}"
            if preview:
                line += f": {preview}"
            print(line, flush=True)


def _run():
    try:
        conn = connect()
        cur = conn.cursor()
    except Exception as e:
        print(f"[grove-listen] connect failed: {e}", flush=True)
        sys.exit(1)

    ch_map = load_channels(cur)
    verbose = _verbose_channels()
    cursors = {ch_id: 0 for ch_id in ch_map}
    if ch_map:
        cur.execute(
            "SELECT channel_id, COALESCE(MAX(id), 0) FROM grove.messages"
            " WHERE channel_id = ANY(%s) GROUP BY channel_id",
            (list(ch_map.keys()),)
        )
        for row in cur.fetchall():
            cursors[row[0]] = row[1]

    cur.execute("LISTEN grove_channel")

    # Announce presence via HEARTBEAT bus message
    try:
        cur.execute("SELECT id FROM grove.channels WHERE name = 'general' LIMIT 1")
        row = cur.fetchone()
        if row:
            cur.execute(
                "INSERT INTO grove.messages (channel_id, sender, content, bus_type, to_agent, priority)"
                " VALUES (%s, %s, %s, 'HEARTBEAT', '__all__', 6)",
                (row[0], AGENT, f"{AGENT} online"),
            )
            conn.commit()
    except Exception:
        pass

    print(
        f"[grove-listen] ready as {AGENT} — "
        + ", ".join(f"#{n}" for n in ch_map.values()),
        flush=True,
    )

    while True:
        try:
            from core.loop_heartbeat import write_throttled

            write_throttled("grove_listen")
            if select.select([conn], [], [], 30.0)[0]:
                conn.poll()
                notified = set()
                while conn.notifies:
                    n = conn.notifies.pop(0)
                    try:
                        notified.add(int(n.payload))
                    except ValueError:
                        pass
                for ch_id in notified:
                    if ch_id not in ch_map:
                        ch_map = load_channels(cur)
                        cursors.setdefault(ch_id, 0)
                    ch_name = ch_map.get(ch_id, str(ch_id))
                    _drain_channel(cur, ch_id, ch_name, cursors, verbose)
        except Exception as e:
            print(f"[grove-listen-error] {e}", flush=True)
            try:
                stale = conn
                conn = connect()
                try:
                    stale.close()
                except Exception:
                    pass
                cur = conn.cursor()
                ch_map = load_channels(cur)
                # Keep existing cursors — only seed new channels at 0.
                # Re-seeding to MAX would skip messages from the disconnect window.
                for ch_id in ch_map:
                    cursors.setdefault(ch_id, 0)
                cur.execute("LISTEN grove_channel")
                # Drain all channels immediately to catch any messages from the
                # disconnect window — the WHERE id > cursor query is idempotent.
                for ch_id, ch_name in list(ch_map.items()):
                    try:
                        _drain_channel(cur, ch_id, ch_name, cursors, verbose)
                    except Exception:
                        pass
            except Exception:
                time.sleep(5)


if __name__ == "__main__":
    main()
