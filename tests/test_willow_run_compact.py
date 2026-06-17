"""willow_run(run_now=True) must not echo Kart stdout three times."""

from sap.willow_run_compact import compact_willow_run_outcome

_MARKER = "UNIQUE_STDOUT_MARKER"
_HEAVY = {
    "returncode": 0,
    "stdout": _MARKER,
    "stderr": "",
    "sandbox_setup": "ok",
}


def _count_marker(payload: object) -> int:
    if isinstance(payload, dict):
        return sum(_count_marker(v) for v in payload.values())
    if isinstance(payload, list):
        return sum(_count_marker(v) for v in payload)
    if isinstance(payload, str):
        return payload.count(_MARKER)
    return 0


def test_run_now_single_stdout_copy_from_run_results():
    submitted = {
        "task_id": "ABC123",
        "status": "pending",
        "agent": "kart",
        "command": "echo ok",
    }
    run_payload = {
        "executed": 1,
        "results": [
            {
                "task_id": "ABC123",
                "status": "completed",
                "cmd": "echo ok",
                "result": dict(_HEAVY),
            }
        ],
    }
    out = compact_willow_run_outcome(submitted, run_payload)
    assert _count_marker(out) == 1
    assert out["task_id"] == "ABC123"
    assert out["status"] == "completed"
    assert out["result"] == _HEAVY
    assert out["run"] == {"executed": 1}
    assert "submitted" not in out
    assert "results" not in out.get("run", {})


def test_run_now_falls_back_to_status_row_without_run_match():
    submitted = {"task_id": "XYZ", "status": "pending", "agent": "kart"}
    status_row = {"status": "completed", "result": dict(_HEAVY)}
    out = compact_willow_run_outcome(submitted, {"executed": 0, "results": []}, status_row)
    assert _count_marker(out) == 1
    assert out["result"] == _HEAVY


def test_submit_only_unchanged_shape():
    submitted = {"task_id": "T1", "status": "pending", "agent": "kart", "command": "true"}
    out = compact_willow_run_outcome(submitted)
    assert out["task_id"] == "T1"
    assert out["command"] == "true"
    assert "result" not in out
    assert "run" not in out


def test_submit_error_passthrough():
    out = compact_willow_run_outcome({"error": "blocked"})
    assert out == {
        "facade": "willow_run",
        "backend": "agent_task_submit",
        "error": "blocked",
    }


def test_old_facade_shape_duplicated_stdout():
    """Regression: pre-fix run_now returned stdout in both run.results and result."""
    submitted = {"task_id": "A", "status": "pending", "command": "echo x"}
    run_payload = {
        "executed": 1,
        "results": [{"task_id": "A", "status": "completed", "result": dict(_HEAVY)}],
    }
    status_row = {"status": "completed", "result": dict(_HEAVY), "task": "echo x"}
    old_shape = {"submitted": submitted, "run": run_payload, "result": status_row}
    assert _count_marker(old_shape) == 2
    assert _count_marker(compact_willow_run_outcome(submitted, run_payload)) == 1


def test_reaped_stale_preserved_in_run_meta():
    submitted = {"task_id": "A", "status": "pending", "agent": "kart"}
    run_payload = {"executed": 0, "reaped_stale": 2, "results": []}
    out = compact_willow_run_outcome(submitted, run_payload)
    assert out["run"] == {"executed": 0, "reaped_stale": 2}
