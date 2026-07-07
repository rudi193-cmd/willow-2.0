"""Tests for scripts/fleet_hygiene_sweep.py."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"


def test_list_phases():
    proc = subprocess.run(
        [sys.executable, str(_SCRIPTS / "fleet_hygiene_sweep.py"), "--list-phases"],
        cwd=_REPO,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "WILLOW_AGENT_NAME": "willow"},
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert "repos" in data["phases"]
    assert "hooks" in data["phases"]
    assert "groom" in data["phases"]
    assert len(data["phases"]) == 8


def test_dry_run_repos_only():
    proc = subprocess.run(
        [
            sys.executable,
            str(_SCRIPTS / "fleet_hygiene_sweep.py"),
            "--only",
            "repos",
            "--dry-run",
        ],
        cwd=_REPO,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "WILLOW_AGENT_NAME": "willow"},
    )
    assert proc.returncode == 0
    out = json.loads(proc.stdout)
    assert out["ok"] is True


def test_unknown_phase_fails():
    proc = subprocess.run(
        [
            sys.executable,
            str(_SCRIPTS / "fleet_hygiene_sweep.py"),
            "--only",
            "not-a-phase",
            "--dry-run",
        ],
        cwd=_REPO,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "WILLOW_AGENT_NAME": "willow"},
    )
    assert proc.returncode == 1
    out = json.loads(proc.stdout)
    assert out["ok"] is False
