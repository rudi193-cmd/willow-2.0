"""Loop registry — ADR-20260705 MVP."""
from __future__ import annotations

import pytest

from willow.fylgja.loops.registry import (
    load_registry,
    load_seed,
    recount,
    validate_loop,
    validate_registry,
)


def test_seed_loads_eight_loops():
    seed = load_seed()
    assert seed["version"] == 1
    assert len(seed["loops"]) == 8


def test_validate_registry_seed_ok():
    problems = validate_registry(load_seed()["loops"])
    assert problems == []


def test_validate_loop_requires_watchmen_key():
    loop = dict(load_seed()["loops"][0])
    loop["heartbeat"] = {}
    problems = validate_loop(loop)
    assert any("watchmen_key" in p for p in problems)


def test_containment_requires_review_queue():
    loop = {
        "id": "demo",
        "status": "active",
        "trigger": {"kind": "hook", "event": "shutdown"},
        "task": {"kind": "script", "ref": "x.py", "model": None},
        "verify": {"class": "containment", "predicate": "never self-complete"},
        "attention": "bounded",
        "exit": "one pass",
        "on_failure": "open_flag",
        "heartbeat": {"watchmen_key": "demo_loop", "interval_sec": 3600},
        "harness": "briefing_draft",
    }
    problems = validate_loop(loop)
    assert any("queue_decision" in p for p in problems)
    assert any("review_queue" in p for p in problems)


def test_recount_repo_timers_match_seed(monkeypatch):
    monkeypatch.setattr(
        "willow.fylgja.loops.registry._live_systemd_timers",
        lambda: None,
    )
    loops = load_seed()["loops"]
    result = recount(loops)
    assert result["reality_timer_source"] == "repo_systemd_dir"
    assert result["missing_in_reality"] == []
    assert result["untracked_timers"] == []


def test_recount_external_timers_excluded(monkeypatch):
    loops = load_seed()["loops"]
    result = recount(loops)
    assert "sentinel-watchdog.timer" in result["external_timers"]
    assert "kb-snapshot-refresh.timer" in result["external_timers"]
    assert "sentinel-watchdog.timer" not in result["missing_in_reality"]


def test_load_registry_soil_overlay():
    captured: dict[str, dict] = {}

    def soil_all(_collection: str) -> list[dict]:
        return list(captured.values())

    hw = next(l for l in load_seed()["loops"] if l["id"] == "hook-wiring-audit")
    captured[hw["id"]] = {**hw, "attention": "overlay"}
    rows = load_registry(soil_all=soil_all)
    by_id = {r["id"]: r for r in rows}
    assert by_id["hook-wiring-audit"]["attention"] == "overlay"


def test_cli_validate_recount_exit_codes(tmp_path, monkeypatch):
    from willow.fylgja.loops import __main__ as cli

    assert cli.main(["--validate", "--json"]) == 0
