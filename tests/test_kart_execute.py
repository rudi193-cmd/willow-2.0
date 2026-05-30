"""Tests for core/kart_execute.py — unified shell execution."""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("WILLOW_PG_DB", "willow_20_test")

from core.kart_execute import (  # noqa: E402
    _strip_allow_net_directive,
    execute_task_row,
    run_shell_task,
)


@pytest.fixture(autouse=True)
def _no_bwrap(monkeypatch):
    monkeypatch.setenv("WILLOW_KART_NO_BWRAP", "1")


def test_strip_allow_net_directive():
    text = "echo hi\n# allow_net\n"
    body, allow = _strip_allow_net_directive(text)
    assert body == "echo hi"
    assert allow is True


def test_run_shell_task_echo():
    status, result = run_shell_task("echo kart-unify-ok", timeout=10)
    assert status == "completed"
    assert "kart-unify-ok" in result.get("response", "")


def test_run_shell_task_pipeline():
    status, result = run_shell_task("echo ok | wc -c", timeout=10)
    assert status == "completed"
    assert result.get("returncode") == 0


def test_run_shell_task_command_substitution():
    status, result = run_shell_task('echo sub-$(echo xy)', timeout=10)
    assert status == "completed"
    assert "sub-xy" in result.get("response", "")


def test_run_shell_task_compound():
    status, result = run_shell_task("echo a; echo b", timeout=10)
    assert status == "completed"
    assert "a" in result.get("response", "")
    assert "b" in result.get("response", "")


def test_run_shell_task_fenced_blocks():
    task = "```bash\necho one\necho two\n```"
    status, result = run_shell_task(task, timeout=10)
    assert status == "completed"
    assert "one" in result.get("response", "")
    assert "two" in result.get("response", "")
    assert result.get("steps") == 1


def test_execute_task_row_shell():
    pg = MagicMock()
    row = {"id": "TEST1234", "task": "echo row-ok", "goal": None}
    status, result = execute_task_row(row, pg, timeout=10)
    assert status == "completed"
    assert "row-ok" in result.get("response", "")


def test_execute_task_row_workflow_bad_json():
    pg = MagicMock()
    row = {"id": "TEST1234", "task": '{"type":"workflow_phase"', "goal": None}
    status, result = execute_task_row(row, pg)
    assert status == "failed"
    assert "bad workflow payload" in result.get("error", "")
