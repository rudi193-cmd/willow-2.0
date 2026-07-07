"""Tests for fleet metabolic, witness, and kb-ship sweep orchestrators."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO / "scripts"
_ENV = {**__import__("os").environ, "WILLOW_AGENT_NAME": "willow"}


def _run_list_phases(script: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(_SCRIPTS / script), "--list-phases"],
        cwd=_REPO,
        capture_output=True,
        text=True,
        env=_ENV,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_metabolic_list_phases():
    data = _run_list_phases("fleet_metabolic_sweep.py")
    assert "norn" in data["phases"]
    assert len(data["phases"]) == 5


def test_witness_list_phases():
    data = _run_list_phases("fleet_witness_sweep.py")
    assert "wce" in data["phases"]
    assert "retrieval" in data["phases"]
    assert len(data["phases"]) == 5


def test_kb_ship_list_phases():
    data = _run_list_phases("fleet_kb_ship_sweep.py")
    assert "preflight" in data["phases"]
    assert "embed" in data["phases"]
    assert len(data["phases"]) == 7


def test_kb_ship_default_six_phases_dry_run():
    proc = subprocess.run(
        [sys.executable, str(_SCRIPTS / "fleet_kb_ship_sweep.py"), "--dry-run"],
        cwd=_REPO,
        capture_output=True,
        text=True,
        env=_ENV,
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["ok"] is True


def test_metabolic_dry_run_norn():
    proc = subprocess.run(
        [sys.executable, str(_SCRIPTS / "fleet_metabolic_sweep.py"), "--only", "norn", "--dry-run"],
        cwd=_REPO,
        capture_output=True,
        text=True,
        env=_ENV,
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["ok"] is True


def test_witness_dry_run_retrieval():
    proc = subprocess.run(
        [sys.executable, str(_SCRIPTS / "fleet_witness_sweep.py"), "--only", "retrieval", "--dry-run"],
        cwd=_REPO,
        capture_output=True,
        text=True,
        env=_ENV,
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["ok"] is True


def test_kb_ship_dry_run_preflight():
    proc = subprocess.run(
        [sys.executable, str(_SCRIPTS / "fleet_kb_ship_sweep.py"), "--only", "preflight", "--dry-run"],
        cwd=_REPO,
        capture_output=True,
        text=True,
        env=_ENV,
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["ok"] is True
