#!/usr/bin/env python3
"""
dead_reckoning.py — Weekly heading estimate CLI.
b17: DRCK1  ΔΣ=42

Usage:
    dead_reckoning.py run          — collect signals, synthesise, write KB atom
    dead_reckoning.py dry-run      — collect + synthesise, skip KB write
    dead_reckoning.py last         — show the most recent heading atom
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from agents.hanuman.lib.dead_reckoning.analyzer import run as _run


def _last() -> None:
    try:
        from willow.fylgja._mcp import call
        result = call("kb_search", {
            "app_id": "hanuman",
            "query": "Dead Reckoning heading weekly",
            "limit": 3,
        })
        atoms = []
        if isinstance(result, dict):
            atoms = result.get("knowledge", [])
        atoms = [a for a in atoms if a.get("category") == "dead_reckoning"]
        if not atoms:
            print("No Dead Reckoning atoms found. Run: dead_reckoning.py run")
            return
        a = atoms[0]
        print(f"\n{a['title']}")
        print(f"{'─' * 60}")
        print(a.get("summary", ""))
        print(f"{'─' * 60}")
        print(f"atom: {a['id']}  tier: {a.get('tier','?')}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    args = sys.argv[1:]
    cmd = args[0] if args else "run"

    if cmd == "run":
        result = _run(dry_run=False)
        if result.get("error") or result.get("skipped"):
            sys.exit(1)

    elif cmd == "dry-run":
        _run(dry_run=True)

    elif cmd == "last":
        _last()

    else:
        print(__doc__)
        sys.exit(1)
