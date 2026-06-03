"""Tests for bridge_factory.py — explicit SQLite fallback gate."""
import importlib
import sys
import pytest


def _reload_factory(monkeypatch, backend=None, allow_fallback=None):
    """Reload bridge_factory with given env vars so module-level consts are re-evaluated."""
    if backend is not None:
        monkeypatch.setenv("WILLOW_BACKEND", backend)
    else:
        monkeypatch.delenv("WILLOW_BACKEND", raising=False)
    if allow_fallback is not None:
        monkeypatch.setenv("WILLOW_ALLOW_SQLITE_FALLBACK", allow_fallback)
    else:
        monkeypatch.delenv("WILLOW_ALLOW_SQLITE_FALLBACK", raising=False)
    if "core.bridge_factory" in sys.modules:
        del sys.modules["core.bridge_factory"]
    return importlib.import_module("core.bridge_factory")


def test_explicit_sqlite_backend_returns_sqlite_bridge(monkeypatch):
    mod = _reload_factory(monkeypatch, backend="sqlite")
    bridge = mod.get_bridge()
    assert type(bridge).__name__ == "SqliteBridge"


def test_auto_no_postgres_no_flag_raises(monkeypatch):
    """auto mode with Postgres unreachable and no flag must raise, not silently use SQLite."""
    mod = _reload_factory(monkeypatch, backend=None, allow_fallback=None)
    # Patch try_connect to always fail
    import core.pg_bridge as pgb
    monkeypatch.setattr(pgb, "try_connect", lambda: None)
    with pytest.raises(RuntimeError, match="WILLOW_ALLOW_SQLITE_FALLBACK"):
        mod.get_bridge()


def test_auto_no_postgres_with_flag_returns_sqlite(monkeypatch):
    """auto mode with Postgres unreachable but flag set must fall back to SQLite."""
    mod = _reload_factory(monkeypatch, backend=None, allow_fallback="1")
    import core.pg_bridge as pgb
    monkeypatch.setattr(pgb, "try_connect", lambda: None)
    bridge = mod.get_bridge()
    assert type(bridge).__name__ == "SqliteBridge"


def test_auto_no_postgres_flag_zero_raises(monkeypatch):
    """WILLOW_ALLOW_SQLITE_FALLBACK=0 must not enable fallback."""
    mod = _reload_factory(monkeypatch, backend=None, allow_fallback="0")
    import core.pg_bridge as pgb
    monkeypatch.setattr(pgb, "try_connect", lambda: None)
    with pytest.raises(RuntimeError):
        mod.get_bridge()


def test_auto_postgres_exception_no_flag_raises(monkeypatch):
    """try_connect raising an exception must also trigger the fail-loud path."""
    mod = _reload_factory(monkeypatch, backend=None, allow_fallback=None)
    import core.pg_bridge as pgb
    monkeypatch.setattr(pgb, "try_connect", lambda: (_ for _ in ()).throw(OSError("refused")))
    with pytest.raises(RuntimeError, match="WILLOW_ALLOW_SQLITE_FALLBACK"):
        mod.get_bridge()
