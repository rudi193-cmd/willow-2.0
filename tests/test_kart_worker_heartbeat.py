"""Tests for kart_worker SOIL heartbeat (watchmen #31)."""

import sys
from pathlib import Path

import pytest

REPO_ROOT = str(Path(__file__).parent.parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


@pytest.fixture
def store_root(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_STORE_ROOT", str(tmp_path))
    return tmp_path


def test_maybe_write_heartbeat_roundtrips(store_root, monkeypatch):
    import core.kart_worker as kw
    from core.loop_heartbeat import reset_throttle

    monkeypatch.setattr("core.kart_lanes.worker_mode", lambda: "fast")
    reset_throttle("kart_worker")
    kw._maybe_write_heartbeat(tick_ok=True, lane="fast")

    from core.watchmen import check_watchmen
    from core import soil

    status = check_watchmen(soil.get)
    assert status["kart_worker"]["status"] == "ok"


def test_watchmen_key_for_batch_mode():
    from core.kart_worker import _watchmen_key_for_mode
    from core.kart_lanes import KART_WORKER_MODE_BATCH, KART_WORKER_MODE_FAST

    assert _watchmen_key_for_mode(KART_WORKER_MODE_FAST) == "kart_worker"
    assert _watchmen_key_for_mode(KART_WORKER_MODE_BATCH) == "kart_worker_batch"
