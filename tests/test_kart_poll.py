"""Tests for scripts/kart_poll.py Stop-hook drain."""

import sys
from pathlib import Path

import pytest

REPO_ROOT = str(Path(__file__).parent.parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def test_kart_poll_drains_fast_then_batch(monkeypatch):
    import scripts.kart_poll as kp

    monkeypatch.setattr(kp, "LIMIT", 5)
    monkeypatch.setattr("core.grove_gate.assert_grove", lambda *_a, **_k: None)

    claims: list[tuple[str, int]] = []

    class FakePg:
        def claim_kart_tasks(self, limit=10, lane="fast", agent="kart"):
            claims.append((lane, limit))
            if lane == "fast":
                return [{"id": "F1", "task": "echo fast"}]
            return [{"id": "B1", "task": "echo batch"}]

        def close(self):
            pass

    drained: list[list] = []

    def _fake_drain(pg, tasks, **kwargs):
        drained.append(tasks)

    monkeypatch.setattr("core.kart_execute.drain_claimed_tasks", _fake_drain)
    monkeypatch.setattr("core.pg_bridge.PgBridge", FakePg)

    assert kp.main() == 0
    assert claims == [("fast", 5), ("batch", 4)]
    assert len(drained) == 2
    assert drained[0][0]["id"] == "F1"
    assert drained[1][0]["id"] == "B1"


def test_kart_poll_skips_batch_when_fast_fills_limit(monkeypatch):
    import scripts.kart_poll as kp

    monkeypatch.setattr(kp, "LIMIT", 2)
    monkeypatch.setattr("core.grove_gate.assert_grove", lambda *_a, **_k: None)

    class FakePg:
        def claim_kart_tasks(self, limit=10, lane="fast", agent="kart"):
            if lane == "fast":
                return [
                    {"id": "F1", "task": "a"},
                    {"id": "F2", "task": "b"},
                ]
            pytest.fail("batch should not be claimed when fast fills limit")

        def close(self):
            pass

    monkeypatch.setattr(
        "core.kart_execute.drain_claimed_tasks",
        lambda pg, tasks, **kwargs: None,
    )
    monkeypatch.setattr("core.pg_bridge.PgBridge", FakePg)

    assert kp.main() == 0
