"""grove_serve Postgres user default."""
from __future__ import annotations

import importlib


def test_willow_pg_user_defaults_to_getpass(monkeypatch):
    monkeypatch.delenv("WILLOW_PG_USER", raising=False)
    monkeypatch.delenv("USER", raising=False)
    monkeypatch.setattr("getpass.getuser", lambda: "fleet-user")
    mod = importlib.import_module("core.grove_serve")
    importlib.reload(mod)
    assert mod._WILLOW_PG_USER == "fleet-user"
