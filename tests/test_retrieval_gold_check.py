"""tests/test_retrieval_gold_check.py — CLI import resilience."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_retrieval_gold_check_imports_when_willow_py_shadowed():
    """willow.py launcher must not block willow.bench.retrieval_gold."""
    saved = sys.modules.get("willow")
    try:
        launcher = ROOT / "willow.py"
        spec = importlib.util.spec_from_file_location("willow", launcher)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["willow"] = mod
        spec.loader.exec_module(mod)

        check_path = ROOT / "scripts" / "retrieval_gold_check.py"
        spec2 = importlib.util.spec_from_file_location("retrieval_gold_check", check_path)
        loaded = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(loaded)

        assert callable(loaded.run_gold_set)
        assert hasattr(sys.modules["willow"], "__path__")
    finally:
        if saved is None:
            sys.modules.pop("willow", None)
        else:
            sys.modules["willow"] = saved
