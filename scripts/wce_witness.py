#!/usr/bin/env python3
"""WCE weekly witness — Willow Continuity Eval heartbeat.

Runs the full WCE vector (``run_wce.py --tasks all``), persists the JSON artifact,
updates SOIL ``{agent}/wce/state``, and optionally ingests a frontier KB summary atom.

Scheduled weekly by ``systemd/willow-wce.timer``. Run manually:

    ./willow.sh wce
    python3 scripts/wce_witness.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

SENDER = os.environ.get("WILLOW_AGENT_NAME", "willow")
REPORT_CHANNEL_ID = int(os.environ.get("WCE_REPORT_CHANNEL_ID", "0"))
INGEST_KB = os.environ.get("WCE_INGEST_KB", "true").lower() in ("1", "true", "yes")


def _post_grove(content: str, *, dry_run: bool) -> None:
    if not REPORT_CHANNEL_ID:
        return
    if dry_run:
        print(f"[grove dry-run] would post to channel {REPORT_CHANNEL_ID}: {content}")
        return
    try:
        from core.grove_db import bus_send, get_connection, release_connection

        conn = get_connection()
        try:
            bus_send(
                conn,
                channel_id=REPORT_CHANNEL_ID,
                sender=SENDER,
                content=content,
                bus_type="EVENT",
                priority=4,
            )
        finally:
            release_connection(conn)
        print(f"[grove] report posted to channel {REPORT_CHANNEL_ID}")
    except Exception as exc:  # noqa: BLE001
        print(f"[grove] report post FAILED ({type(exc).__name__}: {exc})", file=sys.stderr)


def _run_wce_subprocess(
    *,
    agent: str,
    pair_limit: int,
    output_path: Path,
) -> int:
    cmd = [
        sys.executable,
        str(REPO / "willow" / "bench" / "continuity" / "run_wce.py"),
        "--tasks",
        "all",
        f"--agent={agent}",
        f"--output={output_path}",
    ]
    if pair_limit:
        cmd.append(f"--pair-limit={pair_limit}")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO)
    proc = subprocess.run(cmd, env=env, cwd=str(REPO), check=False)
    return int(proc.returncode)


def _save_soil_state(agent: str, *, metrics: dict, output_path: Path, locked: bool = False) -> None:
    from core import soil

    soil.put(
        f"{agent}/wce",
        "state",
        {
            "last_run_at": datetime.now(timezone.utc).isoformat(),
            "last_run_path": str(output_path),
            "metrics": metrics,
            "locked": locked,
        },
    )


def _ingest_kb_summary(agent: str, metrics: dict, summary_line: str, *, dry_run: bool) -> None:
    if not INGEST_KB or dry_run:
        return
    try:
        from core.pg_bridge import PgBridge

        title = f"WCE weekly {metrics.get('timestamp', 'run')}"
        with PgBridge() as pg:
            atom_id = pg.gen_id(8)
            pg.knowledge_put(
                {
                    "id": atom_id,
                    "title": title[:200],
                    "summary": summary_line[:2000],
                    "content": {
                        "metrics": metrics,
                        "category": "wce",
                        "agent": agent,
                        "detail": json.dumps(metrics, indent=2, default=str),
                    },
                    "tier": "frontier",
                    "category": "bench",
                    "project": agent,
                    "agent": agent,
                }
            )
        print(f"[kb] ingested frontier atom {atom_id}")
    except Exception as exc:  # noqa: BLE001
        print(f"[kb] ingest skipped ({type(exc).__name__}: {exc})", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description="WCE weekly witness")
    ap.add_argument("--agent", default=SENDER, help="agent id for handoff tasks")
    ap.add_argument("--pair-limit", type=int, default=0, help="max handoff pairs (0=all)")
    ap.add_argument("--force", action="store_true", help="run even if interval not elapsed")
    ap.add_argument("--check-first", action="store_true", help="skip unless wce_conditions due")
    ap.add_argument("--dry-run", action="store_true", help="no SOIL/KB/Grove writes")
    args = ap.parse_args()

    from core import soil
    from core.wce_state import extract_wce_metrics, format_wce_summary_line, wce_conditions

    if args.check_first and not args.force:
        check = wce_conditions(args.agent, soil)
        if not check.get("should_run"):
            print(f"WCE skipped: {check.get('reason')}")
            return 0

    if not args.dry_run:
        state = soil.get(f"{args.agent}/wce", "state") or {}
        soil.put(f"{args.agent}/wce", "state", {**state, "locked": True})

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    runs_dir = REPO / "willow" / "bench" / "continuity" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    output_path = runs_dir / f"wce_{stamp}.json"

    rc = _run_wce_subprocess(agent=args.agent, pair_limit=args.pair_limit, output_path=output_path)
    if rc != 0:
        if not args.dry_run:
            state = soil.get(f"{args.agent}/wce", "state") or {}
            soil.put(
                f"{args.agent}/wce",
                "state",
                {**state, "locked": False, "last_error": f"run_wce exited {rc}"},
            )
        print(f"WCE witness FAILED (run_wce exit {rc})", file=sys.stderr)
        return rc

    if not output_path.is_file():
        print(f"WCE witness FAILED — expected output missing: {output_path}", file=sys.stderr)
        return 1

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    metrics = extract_wce_metrics(payload)
    summary_line = format_wce_summary_line(metrics)
    print(summary_line)

    if not args.dry_run:
        _save_soil_state(args.agent, metrics=metrics, output_path=output_path, locked=False)
        _ingest_kb_summary(args.agent, metrics, summary_line, dry_run=False)
        _post_grove(summary_line, dry_run=False)
    else:
        _post_grove(summary_line, dry_run=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
