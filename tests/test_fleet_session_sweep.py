"""Tests for scripts/fleet_session_sweep.py and scripts/fleet_repos.py."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path


_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"


def test_fleet_repos_has_four_repos():
    sys.path.insert(0, str(_SCRIPTS))
    from fleet_repos import FLEET_REPOS

    names = {r.name for r in FLEET_REPOS}
    assert names == {
        "willow",
        "willow-2.0",
        "safe-app-store-public",
        "DispatchesFromReality",
    }


def test_discover_jsonl_paths_since_filter():
    sys.path.insert(0, str(_SCRIPTS))
    from fleet_repos import discover_jsonl_paths

    all_paths = discover_jsonl_paths()
    recent = discover_jsonl_paths(since=date(2099, 1, 1))
    assert len(recent) <= len(all_paths)
    assert len(recent) == 0


def test_list_phases():
    proc = subprocess.run(
        [sys.executable, str(_SCRIPTS / "fleet_session_sweep.py"), "--list-phases"],
        cwd=_REPO,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert "index" in data["phases"]
    assert "benchmark" in data["phases"]
    assert "sonnet5" in data["phases"]
    assert len(data["phases"]) == 13


def test_dry_run_benchmark_only(monkeypatch, tmp_path):
    nest = tmp_path / "Nest"
    nest.mkdir()
    monkeypatch.setenv("NEST", str(nest))
    proc = subprocess.run(
        [
            sys.executable,
            str(_SCRIPTS / "fleet_session_sweep.py"),
            "--since",
            "2099-01-01",
            "--only",
            "benchmark",
            "--dry-run",
            "--nest",
            str(nest),
        ],
        cwd=_REPO,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "WILLOW_AGENT_NAME": "willow"},
    )
    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out["ok"] is True
