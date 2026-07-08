"""Tests for core.metabolic_status.restart_user_systemd_units and watchmen reload."""

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = str(Path(__file__).parent.parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


class _FakeProc:
    def __init__(self, returncode=0, stderr="", stdout=""):
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = stdout


@pytest.fixture(scope="module")
def sap_mod():
    prev = os.environ.get("WILLOW_AGENT_NAME")
    os.environ["WILLOW_AGENT_NAME"] = "test-agent"
    try:
        import sap.sap_mcp as _mod
    finally:
        if prev is None:
            os.environ.pop("WILLOW_AGENT_NAME", None)
        else:
            os.environ["WILLOW_AGENT_NAME"] = prev
    return _mod


def test_restart_user_systemd_units_success(monkeypatch):
    import shutil
    from core import metabolic_status as ms

    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return _FakeProc(returncode=0)

    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/systemctl")
    monkeypatch.setattr(ms.subprocess, "run", fake_run)
    monkeypatch.setattr(ms, "_systemd_user_env", lambda: {"DBUS": "test"})

    out = ms.restart_user_systemd_units(("alpha", "beta"))
    assert out["status"] == "restarted"
    assert out["units"] == ["alpha", "beta"]
    assert calls == [
        ["systemctl", "--user", "restart", "alpha"],
        ["systemctl", "--user", "restart", "beta"],
    ]


def test_restart_user_systemd_units_skips_missing(monkeypatch):
    import shutil
    from core import metabolic_status as ms

    def fake_run(argv, **kwargs):
        unit = argv[-1]
        if unit == "missing":
            return _FakeProc(returncode=1, stderr="Unit missing.service not loaded.")
        return _FakeProc(returncode=0)

    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/systemctl")
    monkeypatch.setattr(ms.subprocess, "run", fake_run)
    monkeypatch.setattr(ms, "_systemd_user_env", lambda: {})

    out = ms.restart_user_systemd_units(("ok", "missing"))
    assert out["status"] == "partial"
    assert out["units"] == ["ok"]
    assert out["skipped"][0]["unit"] == "missing"


def test_restart_watchmen_units_delegates(sap_mod, monkeypatch):
    captured: dict = {}

    def fake_restart(units):
        captured["units"] = units
        return {"status": "restarted", "units": list(units)}

    import core.metabolic_status as ms

    monkeypatch.setattr(ms, "restart_user_systemd_units", fake_restart)

    out = sap_mod._restart_watchmen_units()
    assert out["status"] == "restarted"
    assert "willow-grove-listen" in captured["units"]
    assert "grove-serve" in captured["units"]


def test_hot_reload_watchmen_target(sap_mod, monkeypatch):
    monkeypatch.setattr(
        sap_mod,
        "_restart_watchmen_units",
        lambda: {"status": "restarted", "units": ["nest-watcher"]},
    )
    monkeypatch.setattr(sap_mod, "_code_staleness", lambda: {"stale": False})

    out = sap_mod._hot_reload("watchmen")
    assert out["watchmen"]["status"] == "restarted"
    assert any("watchmen: restarted" in line for line in out["reloaded"])
