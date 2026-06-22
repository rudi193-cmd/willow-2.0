#!/usr/bin/env python3
"""kart_scripts_sweep.py — retention sweep for {WILLOW_ROOT}/.kart-scripts/.

Audit finding #5 (SYSTEM_AUDIT_2026-06-10): the dir is a landfill of one-off
probe scripts and auto-generated Kart bodies. Policy:

- Auto-generated bodies (kart_<hex>.py / kart-<hex>.py) older than --days
  are DELETED (they are reproducible exhaust, never sources of truth).
- Everything else is REPORTED only when older than --report-days. Named
  one-offs are never auto-deleted (Tier 3: no autonomous deletes).

Default is dry-run; pass --apply to delete.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

AUTO_RE = re.compile(r"^kart[_-][0-9a-f]{8,12}\.py$")


def kart_scripts_dir() -> Path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from willow.fylgja.kart_queue import kart_scripts_dir as _d

    return _d()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=14,
                    help="delete auto-generated kart_*.py older than this (default 14)")
    ap.add_argument("--report-days", type=int, default=60,
                    help="report named files older than this (default 60)")
    ap.add_argument("--apply", action="store_true",
                    help="actually delete (default: dry-run)")
    args = ap.parse_args()

    root = kart_scripts_dir()
    now = time.time()
    deleted, kept_auto, stale_named = [], 0, []

    for p in sorted(root.iterdir()):
        if not p.is_file():
            continue
        age_days = (now - p.stat().st_mtime) / 86400
        if AUTO_RE.match(p.name):
            if age_days > args.days:
                deleted.append(p.name)
                if args.apply:
                    p.unlink()
            else:
                kept_auto += 1
        elif age_days > args.report_days:
            stale_named.append(f"{p.name} ({age_days:.0f}d)")

    mode = "deleted" if args.apply else "would delete"
    print(f"[kart-sweep] {root}: {mode} {len(deleted)} auto-generated bodies "
          f"(> {args.days}d), kept {kept_auto} recent")
    if stale_named:
        print(f"[kart-sweep] {len(stale_named)} named files older than "
              f"{args.report_days}d (report only, never auto-deleted):")
        for name in stale_named[:40]:
            print(f"  - {name}")
        if len(stale_named) > 40:
            print(f"  … +{len(stale_named) - 40} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
