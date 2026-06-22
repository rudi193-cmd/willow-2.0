#!/usr/bin/env python3
"""
skill_steward.py — Phase 3 skill surface steward.
b17: SKLSTW · ΔΣ=42

Weekly delta on external SKILL.md trees → SOIL triage queue → Grove #upstream.
Never auto-installs. Human adopts via phase-4 fork when ready.

Usage:
    skill_steward.py run-once [--force] [--dry-run] [--no-git]
    skill_steward.py status
    skill_steward.py list
    skill_steward.py show <skill_id>
    skill_steward.py dismiss <skill_id> [--reason text]
    skill_steward.py adopt <skill_id> [--note text]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, _ROOT)

from agents.hanuman.lib import skill_steward as ss  # noqa: E402
from core.grove_gate import assert_grove as _assert_grove  # noqa: E402


def _cmd_run(args: argparse.Namespace) -> int:
    _assert_grove("skill_steward")
    result = ss.run_once(
        force=args.force,
        dry_run=args.dry_run,
        sync_git=not args.no_git,
        interval_days=args.interval_days,
    )
    print(json.dumps(result, indent=2))
    if result.get("skipped"):
        print(f"  skipped: {result.get('reason', '?')}", flush=True)
        if result.get("hint"):
            print(f"  hint: {result['hint']}", flush=True)
        return 0
    print(
        f"skill_steward: delta {result.get('delta')} · "
        f"queued {result.get('queued')} · grove={result.get('grove_sent')}",
        flush=True,
    )
    return 0


def _cmd_status() -> int:
    from core import soil

    cursor = soil.get(ss._SOIL_CURSOR, "main") or {}
    digest = soil.get(ss._SOIL_DIGEST, "latest") or {}
    snap = soil.get(ss._SOIL_SNAPSHOT, "main") or {}
    pending = ss.list_queue()
    print(f"last_run: {cursor.get('last_run', 'never')}")
    print(f"watch_roots: {', '.join(cursor.get('roots') or []) or '—'}")
    if digest:
        print(f"last_digest: {digest.get('line', '?')} ({digest.get('as_of', '?')})")
    sources = snap.get("sources") or {}
    for name, meta in sources.items():
        print(f"  snapshot {name}: {meta.get('count', 0)} skills @ {meta.get('git_head') or 'n/a'}")
    print(f"pending_queue: {len(pending)}")
    return 0


def _cmd_list() -> int:
    pending = ss.list_queue()
    if not pending:
        print("No pending skill triage items.")
        print("Run: willow.sh skills steward run-once")
        return 0
    for r in pending[:25]:
        print(
            f"  [{r.get('priority', 0):.1f}] {r.get('id')} "
            f"({r.get('change')}) class={r.get('execution_class')} risk={r.get('risk')}"
        )
        desc = (r.get("description") or "")[:70]
        if desc:
            print(f"       {desc}")
    return 0


def _cmd_show(skill_id: str) -> int:
    from core import soil

    r = soil.get(ss._SOIL_QUEUE, skill_id)
    if not r:
        print(f"Not in queue: {skill_id}", file=sys.stderr)
        return 1
    print(json.dumps(r, indent=2))
    return 0


def _cmd_dismiss(skill_id: str, reason: str) -> int:
    from core import soil

    r = soil.get(ss._SOIL_QUEUE, skill_id)
    if not r:
        print(f"Not in queue: {skill_id}", file=sys.stderr)
        return 1
    r["status"] = "dismissed"
    r["dismissed_at"] = ss._now()
    if reason:
        r["dismiss_reason"] = reason
    soil.put(ss._SOIL_QUEUE, skill_id, r)
    print(f"  dismissed: {skill_id}")
    return 0


def _cmd_adopt(skill_id: str, note: str) -> int:
    from core import soil

    r = soil.get(ss._SOIL_QUEUE, skill_id)
    if not r:
        print(f"Not in queue: {skill_id}", file=sys.stderr)
        return 1
    r["status"] = "adopted"
    r["adopted_at"] = ss._now()
    if note:
        r["adopt_note"] = note
    soil.put(ss._SOIL_QUEUE, skill_id, r)
    print(f"  adopted (phase-4 fork when ready): {skill_id}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run-once", help="Scan, diff, queue, notify Grove")
    run_p.add_argument("--force", action="store_true", help="Ignore weekly interval")
    run_p.add_argument("--dry-run", action="store_true", help="Diff only; no SOIL/Grove writes")
    run_p.add_argument("--no-git", action="store_true", help="Skip git pull on source trees")
    run_p.add_argument("--interval-days", type=int, default=7)

    sub.add_parser("status", help="Last run, snapshot counts, queue size")
    sub.add_parser("list", help="Pending triage queue")

    show_p = sub.add_parser("show", help="Show one queue item")
    show_p.add_argument("skill_id")

    dis_p = sub.add_parser("dismiss", help="Dismiss from triage queue")
    dis_p.add_argument("skill_id")
    dis_p.add_argument("--reason", default="")

    ad_p = sub.add_parser("adopt", help="Mark adopted for phase-4 fork")
    ad_p.add_argument("skill_id")
    ad_p.add_argument("--note", default="")

    args = parser.parse_args()
    if args.cmd == "run-once":
        return _cmd_run(args)
    if args.cmd == "status":
        return _cmd_status()
    if args.cmd == "list":
        return _cmd_list()
    if args.cmd == "show":
        return _cmd_show(args.skill_id)
    if args.cmd == "dismiss":
        return _cmd_dismiss(args.skill_id, args.reason)
    if args.cmd == "adopt":
        return _cmd_adopt(args.skill_id, args.note)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
