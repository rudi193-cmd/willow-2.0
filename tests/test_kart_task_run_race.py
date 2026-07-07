"""kart_task_run must report tasks the background kart-worker finishes
during the grace sleep, not just tasks still active after it.

Regression: the active-task snapshot (initial_active_ids) was taken AFTER
the grace sleep. A worker fast enough to finish a task during that sleep
left it already "completed" by snapshot time, excluding it from
initial_active_ids and reporting executed:0 for work that had actually
already succeeded (flag-kart-task-run-empty-when-worker-drained).
"""
import asyncio
from unittest.mock import patch

from sap import sap_mcp


class _FakePg:
    def reap_stale_tasks(self, **kwargs):
        return 0

    def tasks_by_status(self, agent="kart", statuses=None, limit=20):
        if statuses == ["pending", "running"]:
            # Snapshot at call start: task is still pending.
            return [{"id": "T1", "status": "pending", "task": "echo hi"}]
        if statuses == ["pending"] or statuses == ["running"]:
            return []
        # Loop poll (default statuses=None): the background worker has
        # already finished the task by the time this runs.
        return [{
            "id": "T1",
            "status": "completed",
            "task": "echo hi",
            "result": {"stdout": "hi", "returncode": 0},
        }]

    def claim_kart_tasks(self, limit=5, agent="kart"):
        return []


def test_kart_task_run_reports_fast_worker_completion(monkeypatch):
    monkeypatch.setenv("KART_POLL_TIMEOUT", "1")

    async def _run():
        with patch.object(sap_mcp, "pg", _FakePg()):
            return await sap_mcp.kart_task_run(app_id="willow", agent="kart", limit=5)

    out = asyncio.run(_run())
    assert out["executed"] == 1
    assert out["results"][0]["task_id"] == "T1"
    assert out["results"][0]["status"] == "completed"
