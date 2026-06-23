"""Compact willow_run(run_now=True) responses — one copy of Kart stdout."""

_RESULT_STRIP_KEYS = frozenset({"response", "sandbox_manifest"})
"""Fields stripped from the Kart result dict in compact output.

- ``response``: legacy duplicate of ``stdout``. No longer emitted by
  _normalize_shell_result (removed at source), but kept here so older stored
  task rows still compact cleanly.
- ``sandbox_manifest``: large bwrap config; kept on the stored DB task row for
  audit_verify S-gates; not needed in the facade response.
"""


def _strip_result(result: dict) -> dict:
    """Return a copy of *result* with noisy/redundant fields removed."""
    return {k: v for k, v in result.items() if k not in _RESULT_STRIP_KEYS}


def compact_willow_run_outcome(
    submitted: dict,
    run_payload: dict | None = None,
    status_row: dict | None = None,
) -> dict:
    """Collapse submit + kart_task_run + optional status into a single result blob.

    Avoids the triple echo (submitted / run.results[].result / result) that burned
    context when agents called willow_run with run_now=True.
    """
    if submitted.get("error"):
        return {
            "facade": "willow_run",
            "backend": "agent_task_submit",
            "error": submitted["error"],
        }

    tid = submitted.get("task_id")
    out: dict = {
        "facade": "willow_run",
        "backend": "agent_task_submit",
        "task_id": tid,
        "status": submitted.get("status"),
        "agent": submitted.get("agent"),
    }
    if submitted.get("command"):
        out["command"] = submitted["command"]
    if submitted.get("script_path"):
        out["script_path"] = submitted["script_path"]

    matched = None
    if run_payload and tid:
        for row in run_payload.get("results") or []:
            if row.get("task_id") == tid:
                matched = row
                break

    if matched:
        out["status"] = matched.get("status") or out.get("status")
        if matched.get("result") is not None:
            r = matched["result"]
            out["result"] = _strip_result(r) if isinstance(r, dict) else r
    elif status_row:
        out["status"] = status_row.get("status") or out.get("status")
        if status_row.get("result") is not None:
            r = status_row["result"]
            out["result"] = _strip_result(r) if isinstance(r, dict) else r

    if run_payload:
        run_meta: dict = {"executed": run_payload.get("executed", 0)}
        if run_payload.get("reaped_stale"):
            run_meta["reaped_stale"] = run_payload["reaped_stale"]
        out["run"] = run_meta

    return out
