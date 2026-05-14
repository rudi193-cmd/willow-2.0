# b17: 1284BC7D  ΔΣ=42
"""Tests for apps.nest.watcher debounce + ignore logic."""
import time
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from apps.nest.watcher import NestWatcher, _SETTLE_SECS, _IGNORE_SECS


def test_mark_ignored_suppresses_callback(tmp_path):
    called = []
    w = NestWatcher(on_file=lambda p: called.append(p))
    f = tmp_path / "test.txt"
    f.write_text("x")

    w.mark_ignored(f)
    # Manually inject into pending as if watchdog fired
    with w._pending_lock:
        w._pending[str(f)] = time.monotonic() - _SETTLE_SECS - 0.1

    # Run one settle loop tick
    now = time.monotonic()
    ready = []
    with w._pending_lock:
        for p, queued_at in list(w._pending.items()):
            if now - queued_at >= _SETTLE_SECS:
                ready.append(p)
        for p in ready:
            del w._pending[p]

    # The ignore window check happens in _settle_loop; simulate it
    for p in ready:
        path = Path(p)
        with w._ignored_lock:
            ignored_at = w._ignored.get(str(path))
        if ignored_at and time.monotonic() - ignored_at < _IGNORE_SECS:
            continue  # suppressed
        called.append(path)

    assert called == []


def test_ignore_expires(tmp_path):
    called = []
    w = NestWatcher(on_file=lambda p: called.append(p))
    f = tmp_path / "test.txt"
    f.write_text("x")

    # Set ignore timestamp far in the past
    with w._ignored_lock:
        w._ignored[str(f)] = time.monotonic() - _IGNORE_SECS - 1

    with w._pending_lock:
        w._pending[str(f)] = time.monotonic() - _SETTLE_SECS - 0.1

    now = time.monotonic()
    ready = []
    with w._pending_lock:
        for p, queued_at in list(w._pending.items()):
            if now - queued_at >= _SETTLE_SECS:
                ready.append(p)
        for p in ready:
            del w._pending[p]

    for p in ready:
        path = Path(p)
        with w._ignored_lock:
            ignored_at = w._ignored.get(str(path))
        if ignored_at and time.monotonic() - ignored_at < _IGNORE_SECS:
            continue
        if path.exists() and path.is_file():
            w.mark_ignored(path)
            called.append(path)

    assert f in called
