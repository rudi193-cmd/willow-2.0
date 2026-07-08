"""Tests for cross-IDE surface parity library and orchestrator."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_ide_surfaces_manifest_loads():
    from willow.fylgja.surface_parity import load_manifest

    manifest = load_manifest(ROOT)
    assert manifest["version"] == 1
    assert "cursor" in manifest["surfaces"]
    assert manifest["surfaces"]["cursor"]["tier"] == 1
    assert "beforeMCPExecution" in manifest["hooks"]["cursor_required_events"]


def test_hook_parity_passes_on_repo():
    from willow.fylgja.surface_parity import check_hook_parity

    errors = check_hook_parity(ROOT)
    assert errors == [], errors


def test_commands_parity_passes_on_repo():
    from willow.fylgja.surface_parity import check_commands_parity

    errors = check_commands_parity(ROOT)
    assert errors == [], errors


def test_surfaces_parity_matches_sync_script():
    from willow.fylgja.surface_parity import check_surfaces
    from scripts.sync_remote_cursor_surface import check_surfaces as sync_check

    lib_errors = check_surfaces(ROOT)
    sync_errors = sync_check()
    assert lib_errors == sync_errors, (lib_errors, sync_errors)


def test_check_ide_parity_script_passes():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_ide_parity.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_check_ide_parity_json_report():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_ide_parity.py"), "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    phase_names = {p["phase"] for p in payload["phases"]}
    assert {"surfaces", "hooks", "commands"}.issubset(phase_names)


def test_cursor_before_mcp_wires_pre_tool():
    from willow.fylgja.surface_parity import load_manifest

    hooks = json.loads(
        (ROOT / "willow" / "fylgja" / "config" / "cursor-hooks.json").read_text(
            encoding="utf-8"
        )
    )
    want = load_manifest(ROOT)["hooks"]["cursor_required_events"]["beforeMCPExecution"]
    wired = {
        entry.get("command", "")
        for entry in hooks["hooks"]["beforeMCPExecution"]
    }
    assert any(want in cmd for cmd in wired)
