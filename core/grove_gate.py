"""
grove_gate.py — Shared Grove health gate for all Willow scripts.
b17: GGATE1  ΔΣ=42

Usage:
    from core.grove_gate import assert_grove, grove_alive

    assert_grove()          # prints banner + sys.exit(1) if Grove is down
    if not grove_alive():   # returns bool, no side effects
        ...
"""
from __future__ import annotations

import os
import sys
import urllib.request

GROVE_HEALTH_URL = os.environ.get("GROVE_HEALTH_URL", "http://localhost:7777/health")

_BANNER = """
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   GROVE IS NOT RUNNING                                           ║
║                                                                  ║
║   {script:<48} requires Grove.  ║
║   Nothing in the fleet executes without it.                      ║
║                                                                  ║
║   Check:  curl http://localhost:7777/health                      ║
║   Start:  ./willow.sh start  (manages grove-serve.service)       ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
"""


def grove_alive(url: str = GROVE_HEALTH_URL, timeout: int = 3) -> bool:
    """Return True if Grove health endpoint responds 200."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def assert_grove(script: str | None = None, url: str = GROVE_HEALTH_URL) -> None:
    """Print error banner and sys.exit(1) if Grove is not reachable."""
    if grove_alive(url):
        return
    name = script or (sys.argv[0].split("/")[-1] if sys.argv else "this script")
    print(_BANNER.format(script=name[:48]), file=sys.stderr)
    sys.exit(1)
