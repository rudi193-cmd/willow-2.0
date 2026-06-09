#!/usr/bin/env python3
"""kb_preflight.py — read-only KB ship-shape preflight.

Combines graph integrity, embedding completeness, ops health, consolidation
dry-run, and human-required queue into one JSON report.

Exit 0 on PASS/WARN, 1 on FAIL.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "core"):
    ps = str(p)
    if ps not in sys.path:
        sys.path.insert(0, ps)

from core.kb_health import run_preflight  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="KB ship-shape preflight (read-only)")
    parser.add_argument("--threshold", type=float, default=96.0, help="Embedding completeness %%")
    parser.add_argument("--json-only", action="store_true", help="Suppress human summary")
    args = parser.parse_args()

    report = run_preflight(threshold=args.threshold)
    print(json.dumps(report, indent=2, default=str))

    if not args.json_only:
        status = report["summary"]["status"]
        print(f"\n=== KB Preflight: {status} ===", file=sys.stderr)
        for f in report["summary"].get("failures", []):
            print(f"  FAIL: {f}", file=sys.stderr)
        for w in report["summary"].get("warnings", []):
            print(f"  WARN: {w}", file=sys.stderr)
        if status == "PASS":
            print("  All critical checks passed.", file=sys.stderr)

    return 1 if report["summary"]["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
