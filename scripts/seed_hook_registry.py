#!/usr/bin/env python3
"""Idempotent seed of built-in hooks into hook_registry."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from willow.hooks.registry import get_active_hooks, seed_builtin_hooks  # noqa: E402


def main() -> int:
    seeded = seed_builtin_hooks()
    hooks = get_active_hooks()
    print(json.dumps({"newly_registered": seeded, "active_count": len(hooks), "hooks": [h["name"] for h in hooks]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
