"""Tests for the Kart-worker restart wired into hot reload / fleet_restart.

Covers sap.sap_mcp._restart_kart_worker:
  - idle-only skip while a Kart task is in-flight (does not interrupt work)
  - force (only_if_idle=False) bounces regardless of in-flight tasks
  - systemctl-unavailable reports cleanly instead of raising
  - success path returns status=restarted
  - error path surfaces the returncode/stderr

The MCP server runs host-side, so it drives `systemctl --user restart
kart-worker` directly — these tests stub shutil.which / subprocess.run so they
run in CI without touching the real unit.
"""
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = str(Path(__file__).parent.parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


@pytest.fixture(scope="module")
def mod():
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


class _FakeProc:
    def __init__(self, returncode=0, stderr=""):
        self.returncode = returncode
        self.stdout = ""
        self.stderr = stderr


def test_idle_only_skips_when_task_running(mod, monkeypatch):
    monkeypatch.setattr(mod, "_kart_tasks_running", lambda: 2)
    out = mod._restart_kart_worker(only_if_idle=True)
    assert out["status"] == "skipped"
    assert out["running"] == 2


def test_force_bounces_even_when_running(mod, monkeypatch):
    monkeypatch.setattr(mod, "_kart_tasks_running", lambda: 2)
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/systemctl")
    monkeypatch.setattr("subprocess.run", lambda *a, **k: _FakeProc(returncode=0))
    out = mod._restart_kart_worker(only_if_idle=False)
    assert out["status"] == "restarted"
    assert out["unit"] == "kart-worker"


def test_systemctl_unavailable(mod, monkeypatch):
    monkeypatch.setattr(mod, "_kart_tasks_running", lambda: 0)
    monkeypatch.setattr("shutil.which", lambda name: None)
    out = mod._restart_kart_worker(only_if_idle=True)
    assert out["status"] == "unavailable"


def test_success_when_idle(mod, monkeypatch):
    monkeypatch.setattr(mod, "_kart_tasks_running", lambda: 0)
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/systemctl")
    calls = []

    def _fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs.get("env")))
        return _FakeProc(returncode=0)

    monkeypatch.setattr("subprocess.run", _fake_run)
    out = mod._restart_kart_worker(only_if_idle=True)
    assert out["status"] == "restarted"
    assert out["unit"] == "kart-worker"
    assert "kart-worker" in out["units"]
    assert "kart-worker-batch" in out["units"]
    assert calls[0][0] == ["systemctl", "--user", "restart", "kart-worker"]
    assert calls[1][0] == ["systemctl", "--user", "restart", "kart-worker-batch"]
    assert calls[0][1] is not None
    assert "DBUS_SESSION_BUS_ADDRESS" in calls[0][1] or "XDG_RUNTIME_DIR" in calls[0][1]


def test_error_surfaces_returncode(mod, monkeypatch):
    monkeypatch.setattr(mod, "_kart_tasks_running", lambda: 0)
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/systemctl")
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **k: _FakeProc(returncode=5, stderr="Failed to restart"),
    )
    out = mod._restart_kart_worker(only_if_idle=True)
    assert out["status"] == "error"
    assert out["returncode"] == 5
    assert "Failed to restart" in out["stderr"]
