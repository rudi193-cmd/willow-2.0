"""Loop registry — ADR-20260705 MVP."""
from __future__ import annotations

from willow.fylgja.loops.registry import (
    HEARTBEAT_SOIL_COLLECTION,
    WATCHMEN_SOIL_OVERRIDES,
    load_registry,
    load_seed,
    recount,
    validate_loop,
    validate_registry,
    watchmen_targets,
)


def test_seed_loads_twenty_six_loops():
    seed = load_seed()
    assert seed["version"] == 1
    assert len(seed["loops"]) == 26


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
    assert result["missing_daemon_in_reality"] == []
    assert result["untracked_daemons"] == []


def test_recount_daemon_repo_match_seed(monkeypatch):
    monkeypatch.setattr(
        "willow.fylgja.loops.registry._live_systemd_timers",
        lambda: None,
    )
    loops = load_seed()["loops"]
    daemon_units = {
        str((loop.get("trigger") or {}).get("unit"))
        for loop in loops
        if (loop.get("trigger") or {}).get("kind") == "daemon"
    }
    result = recount(loops)
    assert daemon_units
    assert result["registry_daemon_count"] == len(daemon_units)
    assert result["missing_daemon_in_reality"] == []
    assert result["untracked_daemons"] == []


def test_recount_external_timers_excluded(monkeypatch):
    loops = load_seed()["loops"]
    result = recount(loops)
    assert "sentinel-watchdog.timer" in result["external_timers"]
    assert "kb-snapshot-refresh.timer" in result["external_timers"]
    assert "sentinel-watchdog.timer" not in result["missing_in_reality"]


def test_retired_bridge_timer_excluded_from_untracked(monkeypatch):
    monkeypatch.setattr(
        "willow.fylgja.loops.registry._live_systemd_timers",
        lambda: None,
    )
    loops = load_seed()["loops"]
    bridge = next(loop for loop in loops if loop["id"] == "willow-bridge-cross-runtime")
    assert bridge["status"] == "retired"
    result = recount(loops)
    assert "willow-bridge-cross-runtime.timer" in result["retired_timers"]
    assert "willow-bridge-cross-runtime.timer" not in result["untracked_timers"]


def test_recount_hook_registry_match_seed(monkeypatch):
    monkeypatch.setattr(
        "willow.fylgja.loops.registry._live_systemd_timers",
        lambda: None,
    )
    loops = load_seed()["loops"]
    hook_events = {
        str((loop.get("trigger") or {}).get("event"))
        for loop in loops
        if (loop.get("trigger") or {}).get("kind") == "hook"
    }
    monkeypatch.setattr(
        "willow.fylgja.loops.registry._hook_names",
        lambda: hook_events,
    )
    result = recount(loops)
    assert result["hook_drift"]["missing_in_reality"] == []
    assert result["hook_drift"]["missing_in_registry"] == []


def test_validate_registry_ignores_soil_meta_keys():
    loop = dict(load_seed()["loops"][0])
    loop["_id"] = loop["id"]
    loop["_soil_id"] = loop["id"]
    problems = validate_registry([loop])
    assert problems == []


def test_load_registry_soil_overlay():
    captured: dict[str, dict] = {}

    def soil_all(_collection: str) -> list[dict]:
        return list(captured.values())

    hw = next(
        loop for loop in load_seed()["loops"] if loop["id"] == "hook-wiring-audit"
    )
    captured[hw["id"]] = {**hw, "attention": "overlay", "_id": hw["id"]}
    rows = load_registry(soil_all=soil_all)
    by_id = {r["id"]: r for r in rows}
    assert by_id["hook-wiring-audit"]["attention"] == "overlay"
    assert "_id" not in by_id["hook-wiring-audit"]


def test_cli_validate_recount_exit_codes():
    from willow.fylgja.loops import __main__ as cli

    assert cli.main(["--validate", "--json"]) == 0


def test_watchmen_targets_cover_active_seed_loops():
    loops = load_seed()["loops"]
    active = [loop for loop in loops if loop.get("status") != "retired"]
    targets = watchmen_targets(loops)
    assert len(targets) == len(active)
    assert targets["upstream_watcher"] == WATCHMEN_SOIL_OVERRIDES["upstream_watcher"]
    assert targets["kart_worker"] == (HEARTBEAT_SOIL_COLLECTION, "kart_worker")
    assert "willow_bridge_cross_runtime" not in targets


def test_validate_registry_rejects_duplicate_watchmen_key():
    loops = load_seed()["loops"]
    dup = dict(loops[0])
    dup["id"] = "dup-loop"
    problems = validate_registry(loops + [dup])
    assert any("duplicate watchmen_key" in p for p in problems)


def test_get_watchmen_matches_registry():
    from core.watchmen import get_watchmen

    assert get_watchmen() == watchmen_targets(load_seed()["loops"])
