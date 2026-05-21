import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
RUNNER = REPO / "tools" / "run_cursor_hook.py"


def test_session_start_translates_additional_context():
    payload = json.dumps({"hook_event_name": "sessionStart", "conversation_id": "test-1"})
    env = {
        **dict(__import__("os").environ),
        "WILLOW_AGENT_NAME": "heimdallr",
        "PYTHONPATH": str(REPO),
    }
    proc = subprocess.run(
        [sys.executable, str(RUNNER), "willow.fylgja.events.session_start"],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO),
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert "additional_context" in data
    assert "[ANCHOR]" in data["additional_context"]


def test_pre_tool_blocks_sqlite3_via_cursor_adapter():
    payload = json.dumps({
        "hook_event_name": "beforeShellExecution",
        "conversation_id": "test-2",
        "command": "sqlite3 /tmp/x.db '.tables'",
    })
    env = {
        **dict(__import__("os").environ),
        "WILLOW_AGENT_NAME": "heimdallr",
        "PYTHONPATH": str(REPO),
    }
    proc = subprocess.run(
        [sys.executable, str(RUNNER), "willow.fylgja.events.pre_tool"],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO),
        timeout=15,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data.get("permission") == "deny"
