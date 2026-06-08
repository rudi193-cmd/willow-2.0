from __future__ import annotations

from pathlib import Path

from willow.fylgja.python_env import venv_candidates, willow_python
from willow.fylgja.kart_queue import prepare_task_command


def test_venv_candidates_include_repo_and_fleet_home(tmp_path, monkeypatch):
    root = tmp_path / "willow-2.0"
    fleet = tmp_path / ".willow"
    root.mkdir()
    fleet.mkdir()
    monkeypatch.setenv("WILLOW_HOME", str(fleet))

    candidates = venv_candidates(root)

    assert root / ".venv-dev" in candidates
    assert fleet / "venv" in candidates


def test_willow_python_honors_env(tmp_path, monkeypatch):
    py = tmp_path / "python3"
    py.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("WILLOW_PYTHON", str(py))

    assert willow_python(tmp_path) == str(py)


def test_kart_script_body_uses_willow_python(tmp_path, monkeypatch):
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "kart_sandbox.py").write_text("", encoding="utf-8")
    monkeypatch.setenv("WILLOW_ROOT", str(tmp_path))

    command, script_path = prepare_task_command(script_body="print('ok')")

    assert command.startswith('"${WILLOW_PYTHON:-python3}" ')
    assert script_path is not None
    assert Path(script_path).is_file()

