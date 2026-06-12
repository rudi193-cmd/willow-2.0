"""
kart_execute.py — unified Kart task execution (shell, workflow, goal/routine).

All shell work goes through kart_sandbox.run_shell (full-string bash -c).
Used by: core/kart_worker.py, scripts/kart_poll.py, sap kart_task_run fallback.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.pg_bridge import PgBridge

_ROUTINE_FIRE_URL = "https://api.anthropic.com/v1/claude_code/routines/{routine_id}/fire"
_ROUTINE_BETA = "experimental-cc-routine-2026-04-01"
_DEFAULT_WORKFLOW_MODEL = os.environ.get("KART_WORKFLOW_MODEL", "mistral:7b")
_ALLOW_NET_LINE = "# allow_net"
_FENCE_RE = re.compile(r"```(bash|sh|python3?|python)?\n?(.*?)```", re.DOTALL)


def kart_timeout(context: str = "poll") -> int:
    if context == "daemon":
        return int(os.environ.get("KART_DAEMON_TIMEOUT", "1800"))
    return int(os.environ.get("KART_POLL_TIMEOUT", "120"))


def _strip_allow_net_directive(task_text: str) -> tuple[str, bool]:
    from core.kart_sandbox import task_allows_network

    allow_net = task_allows_network(task_text)
    lines = [
        line
        for line in task_text.splitlines()
        if line.strip() != _ALLOW_NET_LINE
    ]
    return "\n".join(lines).strip(), allow_net


def _normalize_shell_result(raw: dict) -> dict:
    stdout = (raw.get("stdout") or "").strip()
    stderr = (raw.get("stderr") or "").strip()
    out: dict[str, Any] = {
        "returncode": raw.get("returncode"),
        "stdout": stdout,
        "stderr": stderr,
        "response": stdout,
        "elapsed_s": raw.get("elapsed_s"),
        "sandbox": raw.get("sandbox"),
        "provider": "shell",
    }
    if raw.get("error"):
        out["error"] = raw["error"]
    # KP3: carry the boundary manifest + setup state through to the task result.
    for _k in ("sandbox_manifest", "sandbox_setup"):
        if raw.get(_k) is not None:
            out[_k] = raw[_k]
    return out


def _iter_fenced_blocks(task_text: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    for lang, block in _FENCE_RE.findall(task_text):
        body = block.strip()
        if not body:
            continue
        kind = "python" if lang in ("python", "python3") else "script"
        if kind != "python":
            real_lines = [
                ln
                for ln in body.splitlines()
                if ln.strip() and not ln.strip().startswith("#")
            ]
            if len(real_lines) == 1:
                kind = "shell"
                body = real_lines[0]
        blocks.append((kind, body))
    return blocks


def _run_one_shell(
    cmd: str,
    *,
    timeout: int,
    allow_net: bool,
) -> tuple[str, dict]:
    from core.kart_sandbox import bwrap_available, run_shell_result_for_task, use_bwrap

    if use_bwrap() and not bwrap_available():
        return "failed", {"error": "bwrap not found — install bubblewrap"}

    status, result = run_shell_result_for_task(
        cmd, timeout=timeout, allow_net=allow_net
    )
    return status, _normalize_shell_result(result)


def run_shell_task(
    task_text: str,
    *,
    timeout: int | None = None,
    context: str = "poll",
) -> tuple[str, dict]:
    """Execute a shell-class task string. Returns (status, result)."""
    timeout = timeout if timeout is not None else kart_timeout(context)
    cmd_body, allow_net = _strip_allow_net_directive(task_text)
    blocks = _iter_fenced_blocks(cmd_body)

    if blocks:
        outputs: list[str] = []
        steps = 0
        errors: list[str] = []
        for kind, body in blocks:
            steps += 1
            label = body.splitlines()[0][:80] if kind == "script" else body
            if kind == "python":
                cmd = f"python3 - <<'KART_PY'\n{body}\nKART_PY"
            elif kind == "script":
                cmd = f"bash <<'KART_SH'\n{body}\nKART_SH"
            else:
                cmd = body
            status, result = _run_one_shell(
                cmd, timeout=timeout, allow_net=allow_net
            )
            chunk = result.get("response") or result.get("stdout") or ""
            err = result.get("stderr") or result.get("error") or ""
            outputs.append(f"$ {label}\n{chunk}" + (f"\nSTDERR: {err}" if err else ""))
            if status != "completed":
                errors.append(result.get("error") or err or f"{label} failed")
        merged = _normalize_shell_result(
            {
                "returncode": 0 if not errors else 1,
                "stdout": "\n\n".join(outputs),
                "stderr": "; ".join(errors),
                "elapsed_s": None,
                "sandbox": blocks and "bwrap" or "none",
            }
        )
        merged["steps"] = steps
        if errors:
            merged["error"] = "; ".join(errors)
            return "failed", merged
        return "completed", merged

    if not cmd_body:
        return "failed", {"error": "empty command"}

    status, result = _run_one_shell(
        cmd_body, timeout=timeout, allow_net=allow_net
    )
    result["steps"] = 1
    return status, result


def run_goal_task(
    pg: PgBridge,
    task_id: str,
    routine_name: str,
    goal: str,
) -> tuple[str, dict]:
    import urllib.request

    started = time.time()
    routine = None
    try:
        routine = pg.routine_get(routine_name)
    except Exception:
        pass

    if routine:
        url = _ROUTINE_FIRE_URL.format(routine_id=routine["id"])
        payload = json.dumps({"text": goal}).encode()
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {routine['token']}",
                "anthropic-beta": _ROUTINE_BETA,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read())
            pg.routine_mark_fired(routine_name, body.get("claude_code_session_id", ""))
            return "completed", {
                "type": "routine_fired",
                "session_id": body.get("claude_code_session_id"),
                "session_url": body.get("claude_code_session_url"),
                "goal": goal,
                "elapsed_s": round(time.time() - started, 2),
            }
        except Exception as e:
            return "failed", {
                "error": str(e),
                "type": "routine_fire_failed",
                "goal": goal,
            }

    return "completed", {
        "type": "goal_queued",
        "goal": goal,
        "note": f"No routine '{routine_name}' registered. Call routine_register.",
        "elapsed_s": round(time.time() - started, 2),
    }


def _resolve_template(text: str, run_input: dict, phase_outputs: dict) -> str:
    def _sub(m: re.Match[str]) -> str:
        expr = m.group(1).strip()
        parts = expr.split(".")
        try:
            if parts[0] == "input":
                val: Any = run_input
                for p in parts[1:]:
                    val = val[p] if isinstance(val, dict) else val
                return str(val)
            if parts[0] == "phases" and len(parts) >= 2:
                val = phase_outputs.get(parts[1], {})
                for p in parts[2:]:
                    val = val[p] if isinstance(val, dict) else val
                return str(val)
        except (KeyError, TypeError):
            pass
        return m.group(0)

    return re.sub(r"\{\{([^}]+)\}\}", _sub, text)


def _call_llm(prompt: str, model: str, output_schema: dict) -> dict:
    from core.llm_edge import respond as _llm_respond

    schema_hint = ""
    if output_schema:
        schema_hint = (
            f"\n\nRespond with valid JSON matching this schema: {json.dumps(output_schema)}"
            "\nOutput ONLY the JSON object, no markdown fences."
        )

    ollama_model = model if model and "claude" not in model else _DEFAULT_WORKFLOW_MODEL
    raw = _llm_respond(
        system_prompt=(
            "You are a workflow execution agent. Be precise and follow instructions exactly."
        ),
        context_atoms=[],
        input_text=prompt + schema_hint,
        ollama_model=ollama_model,
    )

    if output_schema:
        try:
            clean = (
                raw.strip()
                .removeprefix("```json")
                .removeprefix("```")
                .removesuffix("```")
                .strip()
            )
            return json.loads(clean)
        except json.JSONDecodeError:
            return {"raw": raw, "parse_error": "output was not valid JSON"}
    return {"raw": raw}


def _queue_phases(
    pg: PgBridge,
    run_id: str,
    phases: dict,
    run_input: dict,
    phase_outputs: dict,
) -> None:
    completed_names = set(phase_outputs.keys())

    for phase_name, phase_def in phases.items():
        depends_on = phase_def.get("depends_on", [])
        if not all(d in completed_names for d in depends_on):
            continue

        existing = pg.workflow_phases_for_run(run_id)
        existing_names = {p["phase_name"] for p in existing}
        if phase_name in existing_names:
            continue

        prompt = _resolve_template(
            phase_def.get("prompt", ""), run_input, phase_outputs
        )
        phase_input = {
            "prompt": prompt,
            "model": phase_def.get("model", _DEFAULT_WORKFLOW_MODEL),
            "output_schema": phase_def.get("output_schema", {}),
            "phase_name": phase_name,
        }
        payload = json.dumps(
            {
                "type": "workflow_phase",
                "run_id": run_id,
                "phase_name": phase_name,
                "phase_input": phase_input,
            }
        )
        new_task_id = pg.submit_task(
            payload, submitted_by="kart_workflow", agent="kart"
        )
        pg.workflow_phase_create(run_id, phase_name, phase_input, new_task_id)


def run_workflow_phase(
    pg: PgBridge,
    task_id: str,
    payload: dict,
) -> tuple[str, dict]:
    started = time.time()
    run_id = payload["run_id"]
    phase_name = payload["phase_name"]
    phase_input = payload["phase_input"]

    run = pg.workflow_run_get(run_id)
    if not run:
        return "failed", {"error": f"workflow run {run_id} not found"}
    if run["status"] == "cancelled":
        return "failed", {"error": "run cancelled"}
    if run["status"] == "pending":
        pg.workflow_run_update(run_id, "running")

    import psycopg2.extras as _pex

    with pg.conn.cursor(cursor_factory=_pex.RealDictCursor) as cur:
        cur.execute("SELECT * FROM workflows WHERE id=%s", (run["workflow_id"],))
        row = cur.fetchone()
        wf = dict(row) if row else None

    if not wf:
        pg.workflow_run_update(run_id, "failed", "workflow definition not found")
        return "failed", {"error": "workflow definition not found"}

    definition = wf["definition"]
    phases = definition.get("phases", {})

    existing = pg.workflow_phases_for_run(run_id)
    phase_outputs = {
        p["phase_name"]: p["output"]
        for p in existing
        if p["status"] == "completed" and p["output"]
    }

    my_phase = next((p for p in existing if p["phase_name"] == phase_name), None)
    phase_id = my_phase["id"] if my_phase else None

    phase_def = phases.get(phase_name, {})
    rubric = phase_def.get("rubric") or phase_input.get("rubric")

    try:
        if rubric:
            agent_name = phase_def.get("outcome_agent") or phase_input.get("outcome_agent")
            if not agent_name:
                raise ValueError("phase has rubric but no outcome_agent specified")
            agent_rec = pg.outcome_agent_get(agent_name)
            if not agent_rec:
                raise ValueError(f"outcome agent '{agent_name}' not registered")
            import core.outcomes as _outcomes

            outcome = _outcomes.run_outcome(
                agent_id=agent_rec["agent_id"],
                environment_id=agent_rec["environment_id"],
                prompt=phase_input["prompt"],
                rubric=rubric,
                max_iterations=phase_def.get("max_iterations", 3),
                title=f"{wf.get('name', 'workflow')}/{phase_name}",
            )
            output = {
                "result": outcome["result"],
                "explanation": outcome.get("explanation", ""),
                "success": outcome.get("success", False),
                "iterations": outcome.get("iterations", 0),
                "session_id": outcome.get("session_id"),
            }
        else:
            output = _call_llm(
                phase_input["prompt"],
                phase_input.get("model", _DEFAULT_WORKFLOW_MODEL),
                phase_input.get("output_schema", {}),
            )
        elapsed = round(time.time() - started, 2)
        output["_elapsed_s"] = elapsed

        if phase_id:
            pg.workflow_phase_complete(phase_id, output, "completed")

        phase_outputs[phase_name] = output
        run_input = run.get("input") or {}
        _queue_phases(pg, run_id, phases, run_input, phase_outputs)

        all_phases = pg.workflow_phases_for_run(run_id)
        phase_states = {p["phase_name"]: p["status"] for p in all_phases}
        all_done = all(
            s in ("completed", "failed", "skipped") for s in phase_states.values()
        )
        any_failed = any(s == "failed" for s in phase_states.values())

        if all_done:
            final_status = "failed" if any_failed else "completed"
            pg.workflow_run_update(run_id, final_status)

        return "completed", {
            "phase": phase_name,
            "output": output,
            "run_id": run_id,
        }

    except Exception as e:
        err = str(e)
        if phase_id:
            pg.workflow_phase_complete(phase_id, {}, "failed", err)
        pg.workflow_run_update(run_id, "failed", err)
        return "failed", {"error": err, "phase": phase_name, "run_id": run_id}


def execute_task_row(
    row: dict,
    pg: PgBridge,
    *,
    timeout: int | None = None,
    context: str = "poll",
) -> tuple[str, dict]:
    """Route one claimed task row. Returns (status, result)."""
    task_id = row["id"]
    cmd = row.get("task") or ""
    goal = row.get("goal")

    if cmd.startswith('{"type":"workflow_phase"'):
        try:
            payload = json.loads(cmd)
        except json.JSONDecodeError as e:
            return "failed", {"error": f"bad workflow payload: {e}"}
        return run_workflow_phase(pg, task_id, payload)

    if goal:
        return run_goal_task(pg, task_id, cmd, goal)

    try:
        return run_shell_task(cmd, timeout=timeout, context=context)
    except Exception as e:
        return "failed", {"error": str(e)}


def drain_claimed_tasks(
    pg: PgBridge,
    rows: list[dict],
    *,
    context: str = "poll",
    log_prefix: str = "kart",
) -> list[tuple[str, str, dict]]:
    """Execute claimed rows and mark complete. Returns [(task_id, status, result), ...]."""
    import sys

    outcomes: list[tuple[str, str, dict]] = []
    for row in rows:
        task_id = row["id"]
        cmd = row.get("task") or ""
        status, result = execute_task_row(row, pg, context=context)
        try:
            pg.task_complete(task_id, result, status)
        except Exception as e:
            print(
                f"{log_prefix}: task_complete failed for {task_id}: {e}",
                file=sys.stderr,
            )
        print(
            f"{log_prefix}: {task_id} → {status} ({cmd[:60]})",
            file=sys.stderr,
        )
        outcomes.append((task_id, status, result))
    return outcomes
