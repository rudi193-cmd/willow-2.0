"""Restart recovery for explicitly owned Kart claims."""
import json
import socket

import pytest

from core import kart_worker
from core.kart_lanes import KART_LANE_BATCH, KART_LANE_FAST
from core.pg_bridge import PgBridge


@pytest.fixture
def pg():
    bridge = PgBridge()
    yield bridge
    bridge.close()


def test_recovery_is_owner_and_lane_specific_and_never_requeues(pg):
    agent = f"restart_recovery_{pg.gen_id(6)}"
    dead_owner = "dead-owner"
    live_owner = "live-owner"
    replacement = "replacement-owner"

    dead_fast = pg.submit_task("echo MUST_NOT_EXECUTE", "test", agent, lane=KART_LANE_FAST)
    assert pg.claim_kart_tasks(
        agent=agent, lane=KART_LANE_FAST, claim_owner=dead_owner
    )[0]["id"] == dead_fast

    live_fast = pg.submit_task("echo live", "test", agent, lane=KART_LANE_FAST)
    assert pg.claim_kart_tasks(
        agent=agent, lane=KART_LANE_FAST, claim_owner=live_owner
    )[0]["id"] == live_fast

    dead_batch = pg.submit_task("echo batch", "test", agent, lane=KART_LANE_BATCH)
    assert pg.claim_kart_tasks(
        agent=agent, lane=KART_LANE_BATCH, claim_owner=dead_owner
    )[0]["id"] == dead_batch

    failed = pg.fail_orphaned_kart_claims(
        orphaned_owners=[dead_owner],
        replacement_owner=replacement,
        lane=KART_LANE_FAST,
        agent=agent,
    )
    assert failed == [dead_fast]

    dead_row = pg.task_status(dead_fast)
    assert dead_row["status"] == "failed"
    assert dead_row["result"]["error"] == "orphaned_worker_restart"
    assert dead_row["result"]["previous_claim_owner"] == dead_owner
    assert pg.task_status(live_fast)["status"] == "running"
    assert pg.task_status(dead_batch)["status"] == "running"

    # Terminal recovery cannot be claimed again, so the command is neither
    # requeued nor executed by the replacement worker.
    assert pg.pending_tasks(agent=agent, lane=KART_LANE_FAST) == []
    assert pg.claim_kart_tasks(
        agent=agent, lane=KART_LANE_FAST, claim_owner=replacement
    ) == []

    pg.task_complete(live_fast, {"cleanup": True}, "failed")
    pg.task_complete(dead_batch, {"cleanup": True}, "failed")


def test_worker_recovery_leaves_live_and_unknown_owners(monkeypatch):
    class FakePg:
        def __init__(self):
            self.failed = None

        def running_kart_claim_owners(self, lane=None):
            assert lane == KART_LANE_FAST
            return ["dead", "live", "remote"]

        def fail_orphaned_kart_claims(self, **kwargs):
            self.failed = kwargs
            return ["T-DEAD"]

    states = {"dead": False, "live": True, "remote": None}
    monkeypatch.setattr(kart_worker, "_worker_owner_alive", states.get)
    pg = FakePg()

    assert kart_worker._recover_prior_worker_claims(
        pg, "replacement", KART_LANE_FAST
    ) == ["T-DEAD"]
    assert pg.failed["orphaned_owners"] == ["dead"]
    assert pg.failed["lane"] == KART_LANE_FAST


def test_process_identity_distinguishes_live_pid_and_reuse():
    owner = kart_worker._new_worker_owner()
    assert kart_worker._worker_owner_alive(owner) is True

    evidence = json.loads(owner)
    evidence["start_ticks"] = str(int(evidence["start_ticks"]) + 1)
    assert kart_worker._worker_owner_alive(json.dumps(evidence)) is False

    evidence["host"] = socket.gethostname() + "-remote"
    assert kart_worker._worker_owner_alive(json.dumps(evidence)) is None


def test_detached_registry_is_untouched(tmp_path, monkeypatch):
    from core import kart_detached

    detached = tmp_path / "DETACHED1"
    detached.mkdir()
    meta = detached / "meta.json"
    original = '{"task_id":"DETACHED1","detached":true}'
    meta.write_text(original)
    monkeypatch.setattr(kart_detached, "detached_root", lambda: tmp_path)

    class NoClaims:
        def running_kart_claim_owners(self, lane=None):
            return []

        def fail_orphaned_kart_claims(self, **kwargs):
            pytest.fail("no queue claims should be failed")

    assert kart_worker._recover_prior_worker_claims(
        NoClaims(), "replacement", KART_LANE_BATCH
    ) == []
    assert meta.read_text() == original
    assert kart_detached.is_detached("DETACHED1") is True
