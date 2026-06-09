import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / "willow" / "fylgja" / "bin" / "fylgja-hook"


def test_fylgja_hook_cursor_pre_tool_blocks_sqlite3():
    payload = json.dumps({
        "hook_event_name": "beforeShellExecution",
        "conversation_id": "hook-test",
        "command": "sqlite3 /tmp/x.db '.tables'",
    })
    proc = subprocess.run(
        [str(HOOK), "cursor", "pre_tool"],
        input=payload,
        capture_output=True,
        text=True,
        cwd=str(REPO),
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data.get("permission") == "deny"
