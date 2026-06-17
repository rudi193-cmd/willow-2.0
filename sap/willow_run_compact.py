"""Compact willow_run(run_now=True) responses — one copy of Kart stdout."""


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
            out["result"] = matched["result"]
    elif status_row:
        out["status"] = status_row.get("status") or out.get("status")
        if status_row.get("result") is not None:
            out["result"] = status_row["result"]

    if run_payload:
        run_meta: dict = {"executed": run_payload.get("executed", 0)}
        if run_payload.get("reaped_stale"):
            run_meta["reaped_stale"] = run_payload["reaped_stale"]
        out["run"] = run_meta

    return out
