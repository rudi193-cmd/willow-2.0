"""tests/test_fylgja/test_kart_queue.py"""
from pathlib import Path

from willow.fylgja import kart_queue
from willow.fylgja.kart_queue import prepare_task_command


def test_prepare_task_command_plain():
    cmd, path = prepare_task_command("ls -la /tmp")
    assert cmd == "ls -la /tmp"
    assert path is None


def test_prepare_task_command_script_body(tmp_path, monkeypatch):
    scripts = tmp_path / ".kart-scripts"
    scripts.mkdir()
    monkeypatch.setattr(kart_queue, "kart_scripts_dir", lambda: scripts)
    cmd, path = prepare_task_command(script_body="print(42)\n")
    assert cmd.startswith('"${WILLOW_PYTHON:-python3}" ')
    assert path is not None
    written = Path(path)
    assert written.parent == scripts
    assert written.read_text().strip() == "print(42)"


def test_prepare_task_command_requires_one():
    import pytest

    with pytest.raises(ValueError):
        prepare_task_command("")


def test_prepare_task_command_rejects_shell_script_body():
    import pytest
    with pytest.raises(ValueError, match="python3"):
        prepare_task_command(script_body="#!/bin/bash\necho hi\n")


def test_prepare_task_command_allows_python_shebang(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_ROOT", str(tmp_path))
    cmd, path = prepare_task_command(script_body="#!/usr/bin/env python3\nprint(1)\n")
    assert path is not None


def test_clip_output_keeps_head_and_tail_with_marker():
    from core.kart_sandbox import clip_output

    s = "A" * 5000 + "B" * 5000
    c = clip_output(s, 1000)
    assert c.startswith("A")
    assert c.endswith("B")
    assert "clipped" in c
    assert clip_output("short", 1000) == "short"
