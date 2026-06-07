#!/usr/bin/env python3
"""
upstream_watcher.py — Upstream Steward poll loop.
b17: UPST1  ΔΣ=42

Polls GitHub notifications on an interval, triages each item into a lane,
and writes pending work items to SOIL for Grove to display.

Surfaces to Grove #upstream only when human attention is needed.
Never posts comments. Never auto-acts without explicit allowlist + approval.

Run as a long-lived fleet service (or: python upstream_watcher.py run-once).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, _ROOT)

from core import soil
from core.grove_gate import assert_grove as _assert_grove, grove_alive as _grove_alive
from agents.hanuman.lib.upstream.triage import Notification, classify, work_id
from agents.hanuman.lib.upstream.analyzer import analyze
from agents.hanuman.lib.upstream.voice_drafter import draft
from willow.fylgja.willow_home import willow_home

# ── Config ────────────────────────────────────────────────────────────────────

_FLEET_HOME = willow_home(Path(__file__).resolve().parents[3])
_CURSOR_FILE = _FLEET_HOME / "upstream_steward" / "cursor.json"
_CONFIG_FILE = _FLEET_HOME / "upstream_steward" / "config.yaml"

_SOIL_PENDING = "upstream_steward/pending"
_SOIL_LOG = "upstream_steward/log"
_SOIL_DIGEST = "upstream_steward/digest"

POLL_INTERVAL = int(os.environ.get("UPSTREAM_WATCHER_INTERVAL", "900"))  # 15 min default


_SOIL_CONFIG = "upstream_steward/config"

_CONFIG_DEFAULTS: dict[str, Any] = {
    "author": os.environ.get("GITHUB_ACTOR", "rudi193-cmd"),
    "poll_interval_sec": POLL_INTERVAL,
    "watch_repos": [
        "zeroc00I/DontFeedTheAI",
        "ComposioHQ/awesome-claude-skills",
        "PrefectHQ/fastmcp",
        "liatrio-labs/claude-deep-review",
        "NousResearch/hermes-agent",
        "basicmachines-co/basic-memory",
        "doobidoo/mcp-memory-service",
    ],
    "auto_post_allowlist": [],
}


def _load_config() -> dict:
    """Load config from SOIL (JSONB), seeding from yaml on first run."""
    record = soil.get(_SOIL_CONFIG, "main")
    if record:
        return {**_CONFIG_DEFAULTS, **record}
    # First run: seed SOIL from yaml if present, else use defaults
    loaded: dict = {}
    if _CONFIG_FILE.exists():
        try:
            import yaml  # type: ignore
            with open(_CONFIG_FILE) as f:
                loaded = yaml.safe_load(f) or {}
        except ImportError:
            pass
    config = {**_CONFIG_DEFAULTS, **loaded}
    soil.put(_SOIL_CONFIG, "main", config)
    return config


# ── Cursor ────────────────────────────────────────────────────────────────────

_SOIL_CURSOR = "upstream_steward/cursor"
_CURSOR_DEFAULTS = {"last_poll": None, "seen_ids": [], "last_tracker_run": None}


def _read_cursor() -> dict:
    """Read poll cursor from SOIL, seeding from flat file on first run."""
    record = soil.get(_SOIL_CURSOR, "main")
    if record:
        return {**_CURSOR_DEFAULTS, **{k: v for k, v in record.items() if not k.startswith("_")}}
    # Seed from flat file if present
    try:
        flat = json.loads(_CURSOR_FILE.read_text())
        soil.put(_SOIL_CURSOR, "main", flat)
        return flat
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(_CURSOR_DEFAULTS)


def _write_cursor(cursor: dict) -> None:
    soil.put(_SOIL_CURSOR, "main", cursor)


# ── GitHub helpers ─────────────────────────────────────────────────────────────

def _gh(*args: str) -> dict | list:
    result = subprocess.run(
        ["gh", "api", *args],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh api failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def _fetch_notifications(since: str | None) -> list[dict]:
    url = "/notifications?all=true&per_page=50"
    if since:
        url += f"&since={since}"
    try:
        data = _gh(url)
        return data if isinstance(data, list) else []
    except Exception as exc:
        print(f"upstream_watcher: gh notifications error — {exc}", file=sys.stderr, flush=True)
        return []


def _to_notification(raw: dict) -> Notification:
    repo = raw.get("repository", {}).get("full_name", "")
    subject = raw.get("subject", {})
    return Notification(
        id=str(raw.get("id", "")),
        reason=raw.get("reason", ""),
        subject_type=subject.get("type", ""),
        subject_title=subject.get("title", ""),
        subject_url=subject.get("url", ""),
        repo=repo,
        updated_at=raw.get("updated_at", ""),
        unread=bool(raw.get("unread", False)),
    )


# ── SOIL writers ──────────────────────────────────────────────────────────────

def _write_pending(n: Notification, lane: str) -> str:
    wid = work_id(n)
    existing = soil.get(_SOIL_PENDING, wid)
    # Don't overwrite posted/closed items
    if existing and existing.get("status") in ("posted", "closed", "skipped"):
        return wid

    veto_deadline = (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat()
    record = {
        "work_id": wid,
        "status": "awaiting_human" if lane in ("draft", "urgent") else lane,
        "lane": lane,
        "repo": n["repo"],
        "title": n["subject_title"],
        "url": n["subject_url"],
        "kind": n["subject_type"].lower(),
        "reason": n["reason"],
        "their_comment": "",   # filled by analyzer (P1)
        "open_questions": [],  # filled by analyzer (P1)
        "draft_body": "",      # filled by voice_drafter (P1)
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": n["updated_at"],
        "veto_deadline": veto_deadline,
    }
    soil.put(_SOIL_PENDING, wid, record)
    return wid


def _write_log(entry: dict) -> None:
    date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    existing = soil.get(_SOIL_LOG, date_key) or {"entries": []}
    existing.setdefault("entries", []).append(entry)
    soil.put(_SOIL_LOG, date_key, existing)


def _write_digest(pending_count: int, urgent_count: int) -> None:
    line = f"{pending_count} upstream draft{'s' if pending_count != 1 else ''}"
    if urgent_count:
        line += f" · {urgent_count} urgent"
    soil.put(_SOIL_DIGEST, "latest", {
        "line": line,
        "summary": f"{pending_count} items awaiting human review.",
        "pending_count": pending_count,
        "urgent_count": urgent_count,
        "as_of": datetime.now(timezone.utc).isoformat(),
    })


# ── Enrich + notify (P1) ─────────────────────────────────────────────────────

def _enrich_and_notify(n: Notification, wid: str) -> None:
    """Analyze thread, generate draft, update SOIL, then notify Grove."""
    pending = soil.get(_SOIL_PENDING, wid) or {}

    # Step 1: fetch thread context
    try:
        enriched = analyze(pending)
        pending.update(enriched)
        soil.put(_SOIL_PENDING, wid, pending)
    except Exception as exc:
        print(f"upstream_watcher: analyze error for {wid} — {exc}", file=sys.stderr, flush=True)

    # Step 2: generate voice draft (only if we got a comment to reply to)
    if pending.get("their_comment") and not pending.get("draft_body"):
        try:
            draft_body = draft(pending)
            if draft_body:
                pending["draft_body"] = draft_body
                pending["status"] = "awaiting_human"
                soil.put(_SOIL_PENDING, wid, pending)
        except Exception as exc:
            print(f"upstream_watcher: draft error for {wid} — {exc}", file=sys.stderr, flush=True)

    # Step 3: notify Grove (now draft_body is populated if available)
    _notify_grove(n, wid, has_draft=bool(pending.get("draft_body")))


# ── Grove notify ──────────────────────────────────────────────────────────────

def _notify_grove(n: Notification, wid: str, has_draft: bool = False) -> None:
    """Post a notification to Grove #upstream channel."""
    try:
        from core.pg_bridge import PgBridge
        pg = PgBridge()
        try:
            draft_line = (
                "Draft ready → approve / edit / skip"
                if has_draft else
                "Needs attention (no draft — check thread)"
            )
            msg = (
                f"📬 Upstream — reply needed\n\n"
                f"{n['repo']} — {n['subject_title']}\n"
                f"{draft_line}\n"
                f"  willow.sh upstream show {wid}\n"
                f"  willow.sh upstream approve {wid}"
            )
            with pg.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO grove.messages (channel_id, sender, content, to_agent)
                    SELECT c.id, 'upstream-steward', %s, 'hanuman'
                    FROM grove.channels c WHERE c.name = 'upstream'
                    """,
                    (msg,),
                )
                cur.execute("NOTIFY grove_messages")
            pg.conn.commit()
        finally:
            pg.close()
    except Exception as exc:
        print(f"upstream_watcher: grove notify error — {exc}", file=sys.stderr, flush=True)


# ── Backfill ──────────────────────────────────────────────────────────────────

def _backfill_drafts() -> None:
    """Enrich existing draft/urgent records that are missing draft_body."""
    records = soil.all_records(_SOIL_PENDING)
    for r in records:
        if (
            r.get("lane") in ("draft", "urgent")
            and r.get("status") not in ("posted", "closed", "skipped")
            and not r.get("draft_body")
        ):
            wid = r.get("_id") or r.get("work_id", "")
            if not wid:
                continue
            try:
                if not r.get("their_comment"):
                    enriched = analyze(r)
                    r.update(enriched)
                if r.get("their_comment"):
                    body = draft(r)
                    if body:
                        r["draft_body"] = body
                        r["status"] = "awaiting_human"
                        soil.put(_SOIL_PENDING, wid, r)
                        print(f"upstream_watcher: backfilled draft for {wid}", flush=True)
            except Exception as exc:
                print(f"upstream_watcher: backfill error {wid} — {exc}", file=sys.stderr, flush=True)


# ── Main tick ─────────────────────────────────────────────────────────────────

_notified_this_run: set[str] = set()


def tick(config: dict, cursor: dict) -> dict:
    since = cursor.get("last_poll")
    notifications = _fetch_notifications(since)
    seen_ids: list[str] = cursor.get("seen_ids", [])
    watch_repos: list[str] = config.get("watch_repos", [])

    new_count = draft_count = urgent_count = noise_count = 0

    for raw in notifications:
        n = _to_notification(raw)
        nid = n["id"]

        # Dedupe: skip if we've seen this exact updated_at already
        dedup_key = f"{nid}:{n['updated_at']}"
        if dedup_key in seen_ids:
            continue

        lane = classify(n, watch_repos)
        wid = _write_pending(n, lane)

        log_entry = {
            "notification_id": nid,
            "repo": n["repo"],
            "title": n["subject_title"],
            "lane": lane,
            "reason": n["reason"],
            "at": datetime.now(timezone.utc).isoformat(),
        }
        _write_log(log_entry)

        if lane == "noise":
            noise_count += 1
        elif lane in ("draft", "urgent"):
            if lane == "urgent":
                urgent_count += 1
            draft_count += 1
            new_count += 1
            # P1: analyze + draft before notifying (so Grove message has draft_body ready)
            if wid not in _notified_this_run:
                _notified_this_run.add(wid)
                _enrich_and_notify(n, wid)
        else:
            new_count += 1

        seen_ids.append(dedup_key)

    # Keep seen_ids bounded — last 500 entries
    cursor["seen_ids"] = seen_ids[-500:]
    cursor["last_poll"] = datetime.now(timezone.utc).isoformat()

    # Backfill: enrich any existing draft/urgent items that still lack draft_body
    _backfill_drafts()

    # Update digest
    all_pending = [
        r for r in soil.all_records(_SOIL_PENDING)
        if r.get("status") not in ("posted", "closed", "skipped")
    ]
    _write_digest(
        pending_count=len(all_pending),
        urgent_count=sum(1 for r in all_pending if r.get("lane") == "urgent"),
    )

    if new_count or noise_count:
        print(
            f"upstream_watcher: tick — {new_count} new, {draft_count} draft, "
            f"{urgent_count} urgent, {noise_count} noise",
            flush=True,
        )

    return cursor


# ── CLI ───────────────────────────────────────────────────────────────────────

def _cmd_pending() -> None:
    records = soil.all_records(_SOIL_PENDING)
    active = [r for r in records if r.get("status") not in ("posted", "closed", "skipped")]
    if not active:
        print("upstream_watcher: no pending items")
        return
    for r in sorted(active, key=lambda x: (x.get("lane") != "urgent", x.get("updated_at", ""))):
        lane_tag = f"[{r.get('lane', '?')}]".ljust(10)
        print(f"  {lane_tag} {r.get('work_id', '?')}")
        print(f"           {r.get('repo', '')} — {r.get('title', '')}")


def _cmd_show(wid: str) -> None:
    r = soil.get(_SOIL_PENDING, wid)
    if not r:
        print(f"upstream_watcher: not found: {wid}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(r, indent=2, default=str))


def _cmd_run_once(config: dict) -> None:
    cursor = _read_cursor()
    cursor = tick(config, cursor)
    _write_cursor(cursor)
    print("upstream_watcher: run-once complete", flush=True)


# ── Watch loop ────────────────────────────────────────────────────────────────

def watch(config: dict) -> None:
    _assert_grove("upstream_watcher")
    interval = config.get("poll_interval_sec", POLL_INTERVAL)
    print(f"upstream_watcher: polling every {interval}s (Grove up)", flush=True)
    while True:
        cursor = _read_cursor()
        try:
            cursor = tick(config, cursor)
            _write_cursor(cursor)
        except Exception as exc:
            print(f"upstream_watcher: tick error — {exc}", file=sys.stderr, flush=True)
        time.sleep(interval)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cfg = _load_config()
    args = sys.argv[1:]

    if not args or args[0] == "watch":
        try:
            watch(cfg)
        except KeyboardInterrupt:
            print("upstream_watcher: stopped", flush=True)
    elif args[0] == "run-once":
        _cmd_run_once(cfg)
    elif args[0] == "pending":
        _cmd_pending()
    elif args[0] == "show" and len(args) > 1:
        _cmd_show(args[1])
    else:
        print("Usage: upstream_watcher.py [watch|run-once|pending|show <work_id>]")
        sys.exit(1)
