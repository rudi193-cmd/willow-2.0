#!/usr/bin/env python3
"""Run fleet retrieval gold queries against live Postgres (read-only)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in (_ROOT, _ROOT / "core"):
    _ps = str(_p)
    if _ps not in sys.path:
        sys.path.insert(0, _ps)


from core.launcher_shadow import clear_willow_launcher_shadow  # noqa: E402

clear_willow_launcher_shadow()

from core.pg_bridge import PgBridge, try_connect  # noqa: E402
from willow.bench.retrieval_gold import run_gold_set  # noqa: E402


def main() -> int:
    if try_connect() is None:
        print(json.dumps({"error": "postgres_not_connected"}, indent=2))
        return 2
    pg = PgBridge()
    try:
        report = run_gold_set(pg)
    finally:
        pg.close()
    print(json.dumps(report, indent=2))
    return 0 if report.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
