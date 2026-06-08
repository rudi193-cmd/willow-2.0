"""tests/test_retrieval_gold_check.py — launcher shadow must not block willow.bench."""
from __future__ import annotations

import sys
import types

from core.launcher_shadow import clear_willow_launcher_shadow


def _inject_launcher_shadow() -> None:
    sys.modules["willow"] = types.ModuleType("willow")


def _restore_willow_modules(saved: dict[str, object]) -> None:
    for key in list(sys.modules):
        if key == "willow" or key.startswith("willow."):
            del sys.modules[key]
    sys.modules.update(saved)


def test_clear_willow_launcher_shadow_removes_launcher():
    saved = {k: sys.modules[k] for k in list(sys.modules) if k == "willow" or k.startswith("willow.")}
    try:
        _inject_launcher_shadow()
        clear_willow_launcher_shadow()
        assert "willow" not in sys.modules
    finally:
        _restore_willow_modules(saved)


def test_clear_willow_launcher_shadow_preserves_real_package():
    import willow.bench.retrieval_gold  # noqa: F401

    saved = {k: sys.modules[k] for k in list(sys.modules) if k == "willow" or k.startswith("willow.")}
    try:
        clear_willow_launcher_shadow()
        assert "willow" in sys.modules
        assert hasattr(sys.modules["willow"], "__path__")
    finally:
        _restore_willow_modules(saved)


def test_import_retrieval_gold_after_launcher_shadow():
    saved = {k: sys.modules[k] for k in list(sys.modules) if k == "willow" or k.startswith("willow.")}
    try:
        for key in list(sys.modules):
            if key == "willow" or key.startswith("willow."):
                del sys.modules[key]
        _inject_launcher_shadow()
        clear_willow_launcher_shadow()
        from willow.bench.retrieval_gold import run_gold_set

        assert callable(run_gold_set)
    finally:
        _restore_willow_modules(saved)
