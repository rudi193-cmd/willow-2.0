#!/usr/bin/env python3
"""health_report.py — Fleet health snapshot for comfort_check / operators.

Read-only: manifests, dream, metabolic, nest backlog triage.
Exit 0 when no critical findings; 1 when any critical issue is present.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "core"):
    ps = str(p)
    if ps not in sys.path:
        sys.path.insert(0, ps)

from willow.fylgja.willow_home import resolve_store_root, willow_home  # noqa: E402


def _manifest_report() -> dict:
    from sap.core.gate import SAFE_ROOT, PROFESSOR_ROOT, _verify_pgp

    passed, failed = [], []
    for mp in list(SAFE_ROOT.glob("*/safe-app-manifest.json")) + list(
        PROFESSOR_ROOT.glob("*/safe-app-manifest.json")
    ):
        ok, reason = _verify_pgp(mp)
        entry = {"app": mp.parent.name, "ok": ok, "reason": reason}
        (passed if ok else failed).append(entry)
    return {"pass": len(passed), "fail": len(failed), "failed": failed}


def _nest_triage() -> dict:
    queue_file = willow_home(ROOT) / "nest-queue.json"
    if not queue_file.is_file():
        return {"pending": 0, "by_track": {}, "no_dest": 0, "oldest": None}
    items = json.loads(queue_file.read_text())
    pending = [i for i in items if i.get("status") == "pending"]
    by_track = Counter(i.get("track") or "unknown" for i in pending)
    no_dest = sum(1 for i in pending if not i.get("proposed_dest"))
    oldest = min((i.get("staged_at") or "") for i in pending) if pending else None
    return {
        "pending": len(pending),
        "by_track": dict(by_track),
        "no_dest": no_dest,
        "oldest": oldest,
    }


def _metabolic_report() -> dict:
    briefings_db = resolve_store_root(ROOT) / "briefings" / "daily.db"
    last = None
    if briefings_db.is_file():
        import sqlite3
        conn = sqlite3.connect(str(briefings_db))
        try:
            row = conn.execute(
                "SELECT id, created FROM records ORDER BY created DESC LIMIT 1"
            ).fetchone()
            if row:
                last = row[1]
        finally:
            conn.close()
    sock = willow_home(ROOT) / "metabolic.sock"
    return {"last_briefing": last, "socket": "active" if sock.exists() else "missing"}


def _postgres_report() -> dict:
    try:
        import psycopg2
        pg_db = os.environ.get("WILLOW_PG_DB", "willow_20")
        pg_user = os.environ.get("WILLOW_PG_USER", os.environ.get("USER", ""))
        conn = psycopg2.connect(dbname=pg_db, user=pg_user)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"
            )
            total = int(cur.fetchone()[0])
            cur.execute(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE query LIKE 'LISTEN grove_channel%'"
            )
            listen = int(cur.fetchone()[0])
            cur.execute("SHOW max_connections")
            maxconn = int(cur.fetchone()[0])
            return {
                "connections": total,
                "listen_grove": listen,
                "max_connections": maxconn,
                "pressure": round(total / maxconn, 2) if maxconn else 0,
            }
        finally:
            conn.close()
    except Exception as exc:
        return {"error": str(exc)}


def _human_required_report() -> dict:
    try:
        from core.human_required import list_items, operator_load_state, stats
        from core.pg_bridge import get_connection, release_connection

        conn = get_connection()
        try:
            summary = stats(conn)
            items = list_items(conn, status="open", limit=10)
            return {
                "stats": summary,
                "open": items,
                "operator_load": operator_load_state(conn),
            }
        finally:
            release_connection(conn)
    except Exception as exc:
        return {"error": str(exc)}


def _dream_report() -> dict:
    try:
        from core.dream_state import dream_conditions
        from willow_store import WillowStore
        from willow.fylgja.willow_home import resolve_store_root

        root = os.environ.get(
            "WILLOW_STORE_ROOT",
            str(resolve_store_root(ROOT)),
        )
        store = WillowStore(root)
        who = os.environ.get("WILLOW_AGENT_NAME") or "willow"
        return dream_conditions(who, store, pg=None)
    except Exception as exc:
        return {"error": str(exc)}


def main() -> int:
    report = {
        "manifests": _manifest_report(),
        "postgres": _postgres_report(),
        "nest": _nest_triage(),
        "metabolic": _metabolic_report(),
        "dream": _dream_report(),
        "human_required": _human_required_report(),
    }
    print(json.dumps(report, indent=2))

    critical = 0
    if report["manifests"]["fail"]:
        critical += 1
        print("\nCRITICAL: SAFE manifest verification failures", file=sys.stderr)
    pg = report.get("postgres") or {}
    if pg.get("pressure", 0) >= 0.85:
        critical += 1
        print(
            f"\nCRITICAL: Postgres connection pressure "
            f"{pg.get('connections')}/{pg.get('max_connections')} "
            f"({pg.get('listen_grove', 0)} LISTEN grove_channel)",
            file=sys.stderr,
        )
    dream = report["dream"]
    if dream.get("should_dream"):
        print(
            f"\nWARN: dream overdue ({dream.get('hours_since_dream', '?')}h)",
            file=sys.stderr,
        )
    nest = report["nest"]
    if nest.get("pending", 0) > 50:
        print(
            f"\nWARN: nest backlog {nest['pending']} pending "
            f"({nest.get('no_dest', 0)} without destination)",
            file=sys.stderr,
        )
    human = report.get("human_required") or {}
    if not human.get("error"):
        stats = human.get("stats") or {}
        open_total = int(stats.get("open_total") or 0)
        by_priority = stats.get("by_priority") or {}
        if open_total:
            print(
                f"\nWARN: human-required queue has {open_total} open item(s) "
                f"(critical={by_priority.get('critical', 0)}, "
                f"high={by_priority.get('high', 0)})",
                file=sys.stderr,
            )
        for item in (human.get("open") or [])[:5]:
            print(
                f"  - [{item.get('kind')}] {item.get('title')} ({item.get('priority')})",
                file=sys.stderr,
            )
        load = human.get("operator_load") or {}
        if load.get("level") in {"elevated", "high"}:
            print(
                f"\nWARN: operator load {load.get('level')} — {load.get('guidance')}",
                file=sys.stderr,
            )
    meta = report["metabolic"]
    if meta.get("last_briefing"):
        try:
            last = datetime.fromisoformat(str(meta["last_briefing"]).replace("Z", "+00:00"))
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            age_h = (datetime.now(timezone.utc) - last).total_seconds() / 3600
            if age_h > 72:
                print(f"\nWARN: metabolic briefing stale ({age_h:.0f}h)", file=sys.stderr)
        except Exception:
            pass

    return 1 if critical else 0


if __name__ == "__main__":
    raise SystemExit(main())
