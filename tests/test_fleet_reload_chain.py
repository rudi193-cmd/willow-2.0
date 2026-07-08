"""fleet_reload(target=all) chains generation-swap when WILLOW_TRUE_HOTRELOAD=1."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = str(Path(__file__).parent.parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


async def _should_not_run(_loop):
    raise AssertionError("generation reload should not run")


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


def test_all_chains_generation_reload_when_flag_and_stale(mod, monkeypatch):
    monkeypatch.setenv("WILLOW_TRUE_HOTRELOAD", "1")
    monkeypatch.setattr(
        mod,
        "_hot_reload",
        lambda target: {
            "status": "reloaded",
            "reloaded": ["gate: reloaded"],
            "code_version": {"stale": True, "booted_sha": "aaa", "head_sha": "bbb"},
            "warning": "on-disk code is ahead",
        },
    )

    async def _fake_gen(loop):
        return {
            "status": "reloaded",
            "code_version": {"stale": False, "booted_sha": "bbb", "head_sha": "bbb"},
            "list_changed": "sent",
        }

    monkeypatch.setattr(mod, "_generation_reload_result", _fake_gen)
    out = asyncio.run(mod.fleet_reload(app_id="willow", target="all"))
    assert "generation_reload" in out
    assert out["generation_reload"]["status"] == "reloaded"
    assert out["code_version"]["stale"] is False
    assert "warning" not in out


def test_all_skips_generation_reload_without_flag(mod, monkeypatch):
    monkeypatch.delenv("WILLOW_TRUE_HOTRELOAD", raising=False)
    monkeypatch.setattr(
        mod,
        "_hot_reload",
        lambda target: {
            "status": "reloaded",
            "code_version": {"stale": True},
            "warning": "on-disk code is ahead",
        },
    )
    monkeypatch.setattr(mod, "_generation_reload_result", _should_not_run)
    out = asyncio.run(mod.fleet_reload(app_id="willow", target="all"))
    assert "generation_reload" not in out
    assert out["code_version"]["stale"] is True


def test_all_skips_generation_reload_when_fresh(mod, monkeypatch):
    monkeypatch.setenv("WILLOW_TRUE_HOTRELOAD", "1")
    monkeypatch.setattr(
        mod,
        "_hot_reload",
        lambda target: {
            "status": "reloaded",
            "code_version": {"stale": False},
        },
    )
    called = []

    async def _track(loop):
        called.append(True)
        return {"status": "reloaded"}

    monkeypatch.setattr(mod, "_generation_reload_result", _track)
    out = asyncio.run(mod.fleet_reload(app_id="willow", target="all"))
    assert called == []
    assert "generation_reload" not in out


def test_gate_target_does_not_chain_generation_reload(mod, monkeypatch):
    monkeypatch.setenv("WILLOW_TRUE_HOTRELOAD", "1")
    monkeypatch.setattr(
        mod,
        "_hot_reload",
        lambda target: {
            "status": "reloaded",
            "code_version": {"stale": True},
            "warning": "on-disk code is ahead",
        },
    )
    monkeypatch.setattr(mod, "_generation_reload_result", _should_not_run)
    out = asyncio.run(mod.fleet_reload(app_id="willow", target="gate"))
    assert "generation_reload" not in out
