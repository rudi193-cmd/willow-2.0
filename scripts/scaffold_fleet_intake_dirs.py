#!/usr/bin/env python3
"""Create ~/.willow/intake/<agent>/ for every fleet agent (idempotent)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.intake import ensure_fleet_intake_dirs, list_agents  # noqa: E402


def main() -> int:
    ensured = ensure_fleet_intake_dirs()
    print(json.dumps({
        "ensured": len(ensured),
        "agents": ensured,
        "existing_with_records": list_agents(),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
