#!/usr/bin/env python3
"""Cross-IDE parity orchestrator — surfaces, hooks, commands (+ optional live host checks).

CI default: surfaces + hooks + commands (repo-only).
Local strict: add --live for ~/.claude and ~/.codex install verification.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from willow.fylgja.surface_parity import (  # noqa: E402
    DEFAULT_CI_PHASES,
    PHASES,
    run_phases,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify cross-IDE Fylgja surface parity")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero when any phase fails (default mode)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON report on stdout",
    )
    parser.add_argument(
        "--only",
        metavar="PHASE",
        action="append",
        dest="phases",
        choices=PHASES,
        help=f"Run subset of phases (repeatable). Default CI: {', '.join(DEFAULT_CI_PHASES)}",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Include host install checks (~/.claude, ~/.codex)",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Run sync_remote_cursor_surface.py then re-check repo phases",
    )
    args = parser.parse_args()

    if args.fix:
        from scripts.sync_remote_cursor_surface import sync_all

        sync_all()
        print("Synced remote agent surfaces — re-checking parity")

    phases = args.phases or list(DEFAULT_CI_PHASES)
    results = run_phases(phases, root=ROOT, live=args.live)

    if args.json:
        payload = {
            "ok": all(not r.errors for r in results),
            "phases": [
                {"phase": r.phase, "ok": not r.errors, "errors": r.errors}
                for r in results
            ],
        }
        print(json.dumps(payload, indent=2))
    else:
        failed = False
        for res in results:
            if res.errors:
                failed = True
                print(f"[FAIL] {res.phase}:")
                for err in res.errors:
                    print(f"  - {err}")
            else:
                print(f"[OK] {res.phase}")
        if failed:
            print("\nIDE parity check failed.")
            return 1
        print("\nIDE parity check OK")
        return 0

    if any(r.errors for r in results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
