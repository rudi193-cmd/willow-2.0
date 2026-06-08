"""tests/test_retrieval_gold_check.py — launcher shadow must not block willow.bench."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from core.launcher_shadow import clear_willow_launcher_shadow

ROOT = Path(__file__).resolve().parents[1]


def _inject_launcher_shadow() -> None:
    launcher = ROOT / "willow.py"
    spec = importlib.util.spec_from_file_location("willow", launcher)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["willow"] = mod
    spec.loader.exec_module(mod)


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
