"""Clear willow.py launcher shadow from sys.modules before package imports."""
from __future__ import annotations

import sys


def clear_willow_launcher_shadow() -> None:
    """willow.py at repo root is a launcher, not the willow/ package."""
    mod = sys.modules.get("willow")
    if mod is not None and not hasattr(mod, "__path__"):
        del sys.modules["willow"]
