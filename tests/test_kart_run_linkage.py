"""tests/test_kart_run_linkage.py — Kart run-ledger parent linkage.

Regression guard for flag-dream-kart-runs-pollution: the kart-worker daemon
ran current_run_id() in its own process, which always resolved None, so every
Kart run landed as a NULL-parent top-level run and polluted session analytics.
The fix captures the submitter's run_id at submit_task() time and threads it
through the task row to _kart_run_open as the parent.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import core.kart_worker as kart_worker  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_run_ids():
    kart_worker._KART_RUN_IDS.clear()
    yield
    kart_worker._KART_RUN_IDS.clear()


@pytest.fixture
def _capture_open_run(monkeypatch):
    """Stub run_ledger so _kart_run_open records the parent it would persist."""
    captured = {}

    def fake_open_run(purpose="", parent_run_id=None, write_tmp=True, **_kw):
        captured["purpose"] = purpose
        captured["parent_run_id"] = parent_run_id
        captured["write_tmp"] = write_tmp
        return "NEW-RUN-ID"

    monkeypatch.setattr("core.run_ledger.open_run", fake_open_run)
    monkeypatch.setattr("core.run_ledger.current_run_id", lambda: "FALLBACK-CURRENT")
    # Don't depend on a real WILLOW_ROOT on disk.
    monkeypatch.setattr(kart_worker, "_ensure_willow_on_path", lambda: Path("/tmp"))
    return captured


def test_kart_run_open_prefers_submitter_run_id(_capture_open_run):
    """When a submitter run_id is threaded through the task, it becomes the parent."""
    kart_worker._kart_run_open(
        "task1234", "echo hi", "willow", submitter_run_id="SUBMIT-RUN-99"
    )
    assert _capture_open_run["parent_run_id"] == "SUBMIT-RUN-99"
    # Nested run must not clobber the session tmp pointer.
    assert _capture_open_run["write_tmp"] is False
    assert kart_worker._KART_RUN_IDS["task1234"] == "NEW-RUN-ID"


def test_kart_run_open_falls_back_to_current_run_id(_capture_open_run):
    """With no threaded run_id, behaviour is unchanged (current_run_id fallback)."""
    kart_worker._kart_run_open("task5678", "echo hi", "willow")
    assert _capture_open_run["parent_run_id"] == "FALLBACK-CURRENT"


def test_sqlite_submit_task_persists_submitter_run_id(tmp_path, monkeypatch):
    """submit_task captures the session run_id at submit time and stores it."""
    monkeypatch.setenv("WILLOW_SQLITE_PATH", str(tmp_path / "t.db"))
    import core.sqlite_bridge as sqlite_bridge

    monkeypatch.setattr(sqlite_bridge, "_current_run_id_safe", lambda: "RUN-XYZ")
    bridge = sqlite_bridge.SqliteBridge()
    task_id = bridge.submit_task("echo hi", submitted_by="willow", agent="kart")
    assert task_id

    row = bridge.task_status(task_id)
    assert row is not None
    assert row["submitter_run_id"] == "RUN-XYZ"


def test_sqlite_submit_task_explicit_run_id_overrides(tmp_path, monkeypatch):
    """An explicit submitter_run_id arg wins over the ambient resolver."""
    monkeypatch.setenv("WILLOW_SQLITE_PATH", str(tmp_path / "t.db"))
    import core.sqlite_bridge as sqlite_bridge

    monkeypatch.setattr(sqlite_bridge, "_current_run_id_safe", lambda: "AMBIENT")
    bridge = sqlite_bridge.SqliteBridge()
    task_id = bridge.submit_task(
        "echo hi", submitted_by="willow", submitter_run_id="EXPLICIT-RUN"
    )
    row = bridge.task_status(task_id)
    assert row["submitter_run_id"] == "EXPLICIT-RUN"
