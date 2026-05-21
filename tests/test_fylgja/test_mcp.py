import json
import subprocess
from unittest.mock import patch, MagicMock
from willow.fylgja._mcp import call, _subprocess_call

# Subprocess fallback is used for non-store, non-grove tools (e.g. willow_status).
# call() delegates to _subprocess_call — patch that, not subprocess.run/Popen.


def test_call_returns_result_dict():
    with patch("willow.fylgja._mcp._subprocess_call", return_value={"postgres": "up"}):
        result = call("willow_status", {"app_id": "hanuman"})
    assert result == {"postgres": "up"}


def test_call_timeout_returns_error():
    with patch(
        "willow.fylgja._mcp._subprocess_call",
        return_value={"error": "timeout", "tool": "willow_status"},
    ):
        result = call("willow_status", {"app_id": "hanuman"}, timeout=10)
    assert result["error"] == "timeout"
    assert result["tool"] == "willow_status"


def test_call_nonzero_exit_returns_error():
    with patch(
        "willow.fylgja._mcp._subprocess_call",
        return_value={"error": "subprocess_error", "tool": "willow_status"},
    ):
        result = call("willow_status", {"app_id": "hanuman"})
    assert result["error"] == "subprocess_error"


def test_call_sends_correct_jsonrpc_envelope():
    """Subprocess fallback sends proper MCP init + tool call envelope."""
    captured = {"chunks": []}

    class FakeStdout:
        def __init__(self):
            self._lines = iter([
                '{"jsonrpc":"2.0","id":0,"result":{"protocolVersion":"2024-11-05"}}\n',
                '{"jsonrpc":"2.0","id":1,"result":{"ok":true}}\n',
            ])

        def readline(self):
            try:
                return next(self._lines)
            except StopIteration:
                return ""

    def fake_popen(*args, **kwargs):
        proc = MagicMock()
        proc.stdin = MagicMock()
        proc.stdout = FakeStdout()
        proc.stderr = MagicMock()
        proc.returncode = 0
        proc.wait = MagicMock(return_value=0)
        proc.kill = MagicMock()

        def write(data):
            captured["chunks"].append(data)

        proc.stdin.write.side_effect = write
        proc.stdin.flush = MagicMock()
        proc.stdin.close = MagicMock()
        return proc

    with patch("subprocess.Popen", side_effect=fake_popen):
        _subprocess_call("willow_status", {"app_id": "hanuman"}, timeout=10)

    payload = "".join(captured["chunks"])
    lines = [l.strip() for l in payload.splitlines() if l.strip()]
    init_payload = json.loads(lines[0])
    initialized = json.loads(lines[1])
    tool_payload = json.loads(lines[2])
    assert init_payload["method"] == "initialize"
    assert initialized["method"] == "notifications/initialized"
    assert tool_payload["jsonrpc"] == "2.0"
    assert tool_payload["method"] == "tools/call"
    assert tool_payload["params"]["name"] == "willow_status"


def test_store_list_uses_direct_dispatch():
    """store_* tools bypass subprocess and go direct — no subprocess.run call."""
    with patch("subprocess.run", side_effect=AssertionError("should not call subprocess for store_*")):
        # Will error if store isn't reachable, but will NOT call subprocess
        try:
            call("store_list", {"collection": "corpus/corrections"})
        except AssertionError:
            raise
        except Exception:
            pass  # DB not available in CI — that's fine, just no subprocess
