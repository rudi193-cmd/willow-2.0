"""Tests for the Stop hook (willow/fylgja/events/stop.py) and its detached slow path.

Guards the bug classes that have bitten this hook before:
  - `_infer_3b_summarize` raising NameError or failing to parse the model's
    occasional multi-JSON-object reply.
  - `stop_slow.py` importing names that no longer exist on `stop` (refactor
    drift — the detached process fails silently, so CI must catch it).
  - the fast path not spawning the slow path or not clearing its temp files.

These are pure-logic / mocked tests: no Ollama, no Postgres, no MCP required.
"""
import json
import os
import sys
from pathlib import Path

import pytest

# Deterministic identity before importing the hook (resolve_agent_name reads
# WILLOW_AGENT first; otherwise it falls back to the repo's active-agent file).
os.environ.setdefault("WILLOW_AGENT", "test-agent")

REPO_ROOT = str(Path(__file__).resolve().parents[1])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import willow.fylgja.events.stop as stop  # noqa: E402


# --- _infer_3b_summarize parsing ------------------------------------------

class _FakeResp:
    """Minimal context-manager stand-in for urllib's HTTPResponse."""

    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _patch_ollama(monkeypatch, content: str):
    """Make urllib.request.urlopen return an Ollama-/chat-style response."""
    import urllib.request

    payload = json.dumps({"message": {"content": content}}).encode()
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _FakeResp(payload))


def test_infer_3b_single_json(monkeypatch):
    _patch_ollama(monkeypatch, json.dumps({"one_line": "did a thing", "bullets": ["a", "b"]}))
    out = stop._infer_3b_summarize("trace text", timeout=1)
    assert out["one_line"] == "did a thing"
    assert out["bullets"] == ["a", "b"]


def test_infer_3b_double_json_merges(monkeypatch):
    # The model sometimes emits two concatenated JSON objects. Historically this
    # raised (NameError) / parse-failed; the merge loop must recover both.
    content = (
        json.dumps({"one_line": "summary here"})
        + "\n\n"
        + json.dumps({"bullets": ["x", "y", "z"]})
    )
    _patch_ollama(monkeypatch, content)
    out = stop._infer_3b_summarize("trace", timeout=1)
    assert out["one_line"] == "summary here"
    assert out["bullets"] == ["x", "y", "z"]


def test_infer_3b_dict_bullets_flattened(monkeypatch):
    content = json.dumps(
        {"one_line": "s", "bullets": [{"keyword": "k1"}, {"keyword": "k2"}]}
    )
    _patch_ollama(monkeypatch, content)
    out = stop._infer_3b_summarize("trace", timeout=1)
    assert out["bullets"] == ["k1", "k2"]


def test_infer_3b_garbage_returns_empty(monkeypatch):
    _patch_ollama(monkeypatch, "not json at all <<<")
    out = stop._infer_3b_summarize("trace", timeout=1)
    assert out == {"one_line": "", "bullets": []}


def test_infer_3b_urlopen_error_returns_empty(monkeypatch):
    import urllib.request

    def _boom(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    out = stop._infer_3b_summarize("trace", timeout=1)
    assert out == {"one_line": "", "bullets": []}


# --- slow-path import integrity -------------------------------------------

def test_stop_slow_imports_resolve_on_stop():
    """Every name stop_slow.py imports from stop must exist on stop.

    A rename in stop.py without updating the slow path breaks the detached
    background process silently (it swallows the ImportError) — this is the
    one place CI can see that drift.
    """
    slow_src = (Path(stop.__file__).parent / "stop_slow.py").read_text()
    marker = "from willow.fylgja.events.stop import"
    assert marker in slow_src, "stop_slow.py no longer imports from stop"
    block = slow_src.split(marker, 1)[1]
    block = block.split("(", 1)[1].split(")", 1)[0]
    names = [n.strip() for n in block.split(",") if n.strip()]
    assert names, "could not parse stop_slow import list"
    missing = [n for n in names if not hasattr(stop, n)]
    assert not missing, f"stop_slow imports names absent from stop: {missing}"


# --- fast path ------------------------------------------------------------

def test_launch_slow_path_detached(monkeypatch):
    import subprocess

    calls = {}

    def _fake_popen(args, **kwargs):
        calls["args"] = args
        calls["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    stop._launch_slow_path("sess-1")

    # python <repo>/willow/fylgja/events/stop_slow.py sess-1 — fully detached.
    assert calls["args"][1].endswith("stop_slow.py")
    assert calls["args"][2] == "sess-1"
    assert calls["kwargs"].get("start_new_session") is True
    assert calls["kwargs"].get("stdout") == subprocess.DEVNULL
    assert calls["kwargs"].get("stderr") == subprocess.DEVNULL


def test_launch_slow_path_noop_when_script_missing(monkeypatch):
    # If stop_slow.py is absent, _launch_slow_path must return quietly and never
    # spawn — guards against a half-applied refactor breaking the fast path.
    import subprocess

    monkeypatch.setattr(stop.Path, "is_file", lambda self: False)

    def _boom(*a, **k):
        raise AssertionError("Popen must not run when stop_slow.py is missing")

    monkeypatch.setattr(subprocess, "Popen", _boom)
    stop._launch_slow_path("sess-1")  # must not raise


# --- read_turns_since -----------------------------------------------------

def test_read_turns_since_filters_by_cursor(tmp_path):
    f = tmp_path / "turns.txt"
    f.write_text(
        "[2026-05-30T10:00:00] early\n"
        "[2026-05-30T12:00:00] late\n"
        "no-timestamp line\n"
    )
    out = stop.read_turns_since("2026-05-30T11:00:00", f)
    assert out == ["[2026-05-30T12:00:00] late"]


def test_read_turns_since_missing_file(tmp_path):
    assert stop.read_turns_since("2026-01-01", tmp_path / "nope.txt") == []
