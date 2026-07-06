#!/usr/bin/env python3
"""
stuck_loop_watch.py — retrospective stuck-loop watchdog (loop registry tenant).
b17: FLGSLW  ΔΣ=42

Scans recently-modified Claude Code session transcripts for the stuck-loop
chain pattern (see willow/fylgja/stuck_loop.py — a native reimplementation
of dioptx/cctime's analyzer.ts:395-474, decision recorded 2026-07-05 in
project-dioptx-tooling-integration-decision.md). Complementary to
sentinel_watchdog: that watches for silence (a session going dark);
this watches for thrashing (a session burning turns on a failing chain).

One-shot by design — wire to a systemd timer or cron. No sleeps, no loops.

Usage:
    python3 stuck_loop_watch.py [--active-minutes 30] [--min-failures 2] [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WILLOW_ROOT = Path(os.environ.get("WILLOW_ROOT", Path.home() / "github" / "willow-2.0"))
sys.path.insert(0, str(WILLOW_ROOT))

from willow.fylgja.claude_projects import claude_jsonl_paths  # noqa: E402
from willow.fylgja.stuck_loop import detect_stuck_loops_in_jsonl  # noqa: E402

HEARTBEAT_COLLECTION = "willow/loops/heartbeat"
HEARTBEAT_KEY = "stuck_loop_watch"
FLAG_COLLECTION = "willow/flags"
TIMER_INTERVAL_S = 900  # stuck-loop-watch.timer OnUnitActiveSec


def recent_transcripts(active_minutes: int) -> list[Path]:
    cutoff = time.time() - active_minutes * 60
    out = []
    for path in claude_jsonl_paths():
        try:
            if path.stat().st_mtime >= cutoff:
                out.append(path)
        except OSError:
            continue
    return out


def scan(transcripts: list[Path], min_failures: int) -> list[dict]:
    """Run the detector over each transcript; never let one bad file abort the pass."""
    findings: list[dict] = []
    for path in transcripts:
        try:
            loops = detect_stuck_loops_in_jsonl(path, min_failures=min_failures)
        except Exception as exc:
            findings.append({"session": path.stem, "error": str(exc)[:200]})
            continue
        for loop in loops:
            findings.append({"session": path.stem, **loop.to_dict()})
    return findings


def open_flag(findings: list[dict]) -> None:
    """Best-effort: a store problem is reported to stderr, never fatal here."""
    try:
        from core import soil

        unresolved = [f for f in findings if f.get("resolved") is False]
        title = (
            f"Stuck-loop chain detected: {len(findings)} chain(s) across recent sessions"
            f"{f' ({len(unresolved)} unresolved)' if unresolved else ''}"
        )
        soil.put(
            FLAG_COLLECTION,
            f"flag-stuck-loop-{int(time.time())}",
            {
                "type": "flag",
                "flag_state": "open",
                "title": title,
                "source": "stuck_loop_watch",
                "findings": findings[:20],
                "opened_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception as exc:
        print(f"stuck_loop_watch: flag write failed — {exc}", file=sys.stderr, flush=True)


def write_heartbeat(tick_ok: bool, counts: dict, error: str = "") -> None:
    """Prove this watchdog is alive — core/watchmen.py reads this via the loop
    registry (heartbeat.watchmen_key=stuck_loop_watch in loops.json)."""
    try:
        from core import soil

        soil.put(
            HEARTBEAT_COLLECTION,
            HEARTBEAT_KEY,
            {
                "last_tick_at": datetime.now(timezone.utc).isoformat(),
                "interval_sec": TIMER_INTERVAL_S,
                "tick_ok": tick_ok,
                "error": error,
                "counts": counts,
                "pid": os.getpid(),
            },
        )
    except Exception as exc:
        print(f"stuck_loop_watch: heartbeat write failed — {exc}", file=sys.stderr, flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="stuck-loop chain watchdog (loop registry tenant)")
    ap.add_argument("--active-minutes", type=int, default=30,
                     help="transcript mtime window to scan")
    ap.add_argument("--min-failures", type=int, default=2,
                     help="minimum consecutive same-tool failures to flag a chain")
    ap.add_argument("--dry-run", action="store_true",
                     help="report only; do not open a SOIL flag")
    args = ap.parse_args()

    transcripts = recent_transcripts(args.active_minutes)
    findings = scan(transcripts, args.min_failures)

    # Always print — a silent success is indistinguishable from a dead watchdog.
    print(f"stuck_loop_watch: {len(transcripts)} recent session(s), "
          f"{len(findings)} stuck-loop chain(s)", flush=True)

    counts = {"sessions_scanned": len(transcripts), "chains_found": len(findings)}

    if not findings:
        write_heartbeat(tick_ok=True, counts=counts)
        return 0

    for f in findings[:5]:
        print(f"stuck_loop_watch:   {f}", flush=True)
    if not args.dry_run:
        open_flag(findings)
    write_heartbeat(tick_ok=True, counts=counts)
    return 1


if __name__ == "__main__":
    sys.exit(main())
