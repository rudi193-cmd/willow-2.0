#!/usr/bin/env python3
"""
kart_poll.py — drain the pending tasks queue at session close.

Handles three task types:
  1. Shell tasks       — task is a shell command string
  2. Goal tasks        — task is a routine name, goal= is natural language; fires Routine
  3. Workflow phases   — task starts with '{"type":"workflow_phase"'; DAG executor

Wire as a Stop hook in .claude/settings.json alongside session_close.py.
Calls PgBridge directly (no MCP round-trip) so it works even if the MCP server is down.
"""
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


LIMIT   = int(os.environ.get("KART_POLL_LIMIT", "10"))
TIMEOUT = int(os.environ.get("KART_POLL_TIMEOUT", "120"))

_ROUTINE_FIRE_URL = "https://api.anthropic.com/v1/claude_code/routines/{routine_id}/fire"
_ROUTINE_BETA     = "experimental-cc-routine-2026-04-01"


# ── Goal tasks (Routine fire) ─────────────────────────────────────────────────

def _run_goal_task(pg, task_id: str, routine_name: str, goal: str):
    import urllib.request
    started = time.time()

    routine = None
    try:
        routine = pg.routine_get(routine_name)
    except Exception:
        pass

    if routine:
        url     = _ROUTINE_FIRE_URL.format(routine_id=routine["id"])
        payload = json.dumps({"text": goal}).encode()
        req = urllib.request.Request(
            url, data=payload,
            headers={
                "Authorization":     f"Bearer {routine['token']}",
                "anthropic-beta":    _ROUTINE_BETA,
                "anthropic-version": "2023-06-01",
                "Content-Type":      "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read())
            pg.routine_mark_fired(routine_name, body.get("claude_code_session_id", ""))
            return "completed", {
                "type":        "routine_fired",
                "session_id":  body.get("claude_code_session_id"),
                "session_url": body.get("claude_code_session_url"),
                "goal":        goal,
                "elapsed_s":   round(time.time() - started, 2),
            }
        except Exception as e:
            return "failed", {"error": str(e), "type": "routine_fire_failed", "goal": goal}
    else:
        return "completed", {
            "type":      "goal_queued",
            "goal":      goal,
            "note":      f"No routine '{routine_name}' registered. Call routine_register.",
            "elapsed_s": round(time.time() - started, 2),
        }


# ── Workflow phase executor ───────────────────────────────────────────────────

def _resolve_template(text: str, run_input: dict, phase_outputs: dict) -> str:
    """Replace {{input.x}} and {{phases.name.key}} in prompt templates."""
    import re
    def _sub(m):
        expr = m.group(1).strip()
        parts = expr.split(".")
        try:
            if parts[0] == "input":
                val = run_input
                for p in parts[1:]:
                    val = val[p] if isinstance(val, dict) else val
                return str(val)
            elif parts[0] == "phases" and len(parts) >= 2:
                phase_out = phase_outputs.get(parts[1], {})
                val = phase_out
                for p in parts[2:]:
                    val = val[p] if isinstance(val, dict) else val
                return str(val)
        except (KeyError, TypeError):
            pass
        return m.group(0)  # leave unreplaced if not found
    return re.sub(r"\{\{([^}]+)\}\}", _sub, text)


def _call_llm(prompt: str, model: str, output_schema: dict) -> dict:
    """Call Anthropic API directly. Returns parsed JSON output or raw text."""
    import anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY not set", "raw": ""}

    schema_hint = ""
    if output_schema:
        schema_hint = (
            f"\n\nRespond with valid JSON matching this schema: {json.dumps(output_schema)}"
            "\nOutput ONLY the JSON object, no markdown fences."
        )

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=model or "claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt + schema_hint}],
    )
    raw = msg.content[0].text if msg.content else ""

    if output_schema:
        try:
            # Strip optional markdown fences
            clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return json.loads(clean)
        except json.JSONDecodeError:
            return {"raw": raw, "parse_error": "output was not valid JSON"}
    return {"raw": raw}


def _queue_phases(pg, run_id: str, phases: dict, run_input: dict, phase_outputs: dict):
    """Queue any phases whose dependencies are now all completed."""
    completed_names = set(phase_outputs.keys())

    for phase_name, phase_def in phases.items():
        depends_on = phase_def.get("depends_on", [])
        if not all(d in completed_names for d in depends_on):
            continue  # still blocked

        # Check if already queued/running/done
        existing = pg.workflow_phases_for_run(run_id)
        existing_names = {p["phase_name"] for p in existing}
        if phase_name in existing_names:
            continue  # already created

        # Resolve input for this phase
        prompt = _resolve_template(
            phase_def.get("prompt", ""), run_input, phase_outputs
        )
        phase_input = {
            "prompt":        prompt,
            "model":         phase_def.get("model", "claude-haiku-4-5-20251001"),
            "output_schema": phase_def.get("output_schema", {}),
            "phase_name":    phase_name,
        }

        # Submit as a kart task
        payload = json.dumps({
            "type":       "workflow_phase",
            "run_id":     run_id,
            "phase_name": phase_name,
            "phase_input": phase_input,
        })
        task_id = pg.submit_task(payload, submitted_by="kart_workflow", agent="kart")
        pg.workflow_phase_create(run_id, phase_name, phase_input, task_id)
        print(f"kart_poll: workflow {run_id} → queued phase '{phase_name}'", file=sys.stderr)


def _run_workflow_phase(pg, task_id: str, payload: dict):
    """Execute one workflow phase: resolve templates, call LLM, write output, queue next."""
    started    = time.time()
    run_id     = payload["run_id"]
    phase_name = payload["phase_name"]
    phase_input = payload["phase_input"]

    # Mark run as running
    run = pg.workflow_run_get(run_id)
    if not run:
        return "failed", {"error": f"workflow run {run_id} not found"}
    if run["status"] == "cancelled":
        return "failed", {"error": "run cancelled"}
    if run["status"] == "pending":
        pg.workflow_run_update(run_id, "running")

    # Look up workflow definition
    wf = None
    with pg.conn.cursor(pg.conn.cursor_factory if hasattr(pg.conn, "cursor_factory") else None) as _:
        pass
    import psycopg2.extras as _pex
    with pg.conn.cursor(cursor_factory=_pex.RealDictCursor) as cur:
        cur.execute("SELECT * FROM workflows WHERE id=%s",
                    (run["workflow_id"],))
        row = cur.fetchone()
        wf = dict(row) if row else None

    if not wf:
        pg.workflow_run_update(run_id, "failed", "workflow definition not found")
        return "failed", {"error": "workflow definition not found"}

    definition = wf["definition"]
    phases     = definition.get("phases", {})

    # Gather completed phase outputs
    existing = pg.workflow_phases_for_run(run_id)
    phase_outputs = {
        p["phase_name"]: p["output"]
        for p in existing
        if p["status"] == "completed" and p["output"]
    }

    # Find our phase record
    my_phase = next((p for p in existing if p["phase_name"] == phase_name), None)
    phase_id = my_phase["id"] if my_phase else None

    # Call LLM
    try:
        output = _call_llm(
            phase_input["prompt"],
            phase_input.get("model", "claude-haiku-4-5-20251001"),
            phase_input.get("output_schema", {}),
        )
        elapsed = round(time.time() - started, 2)
        output["_elapsed_s"] = elapsed

        if phase_id:
            pg.workflow_phase_complete(phase_id, output, "completed")

        # Update phase_outputs with our result and queue next phases
        phase_outputs[phase_name] = output
        run_input = run.get("input") or {}
        _queue_phases(pg, run_id, phases, run_input, phase_outputs)

        # Check if all phases are done
        all_phases   = pg.workflow_phases_for_run(run_id)
        phase_states = {p["phase_name"]: p["status"] for p in all_phases}
        all_done     = all(s in ("completed", "failed", "skipped")
                           for s in phase_states.values())
        any_failed   = any(s == "failed" for s in phase_states.values())

        if all_done:
            final_status = "failed" if any_failed else "completed"
            pg.workflow_run_update(run_id, final_status)
            print(f"kart_poll: workflow {run_id} → {final_status}", file=sys.stderr)

        return "completed", {"phase": phase_name, "output": output, "run_id": run_id}

    except Exception as e:
        err = str(e)
        if phase_id:
            pg.workflow_phase_complete(phase_id, {}, "failed", err)
        pg.workflow_run_update(run_id, "failed", err)
        return "failed", {"error": err, "phase": phase_name, "run_id": run_id}


# ── Main loop ─────────────────────────────────────────────────────────────────

def main() -> int:
    try:
        from core.pg_bridge import PgBridge
        pg = PgBridge()
    except Exception as e:
        print(f"kart_poll: no Postgres ({e}) — skipping", file=sys.stderr)
        return 0

    try:
        tasks = pg.pending_tasks(agent="kart", limit=LIMIT)
    except Exception as e:
        print(f"kart_poll: pending_tasks failed ({e}) — skipping", file=sys.stderr)
        return 0

    if not tasks:
        return 0

    print(f"kart_poll: {len(tasks)} pending task(s)", file=sys.stderr)

    for t in tasks:
        task_id = t["id"]
        cmd     = t["task"]
        goal    = t.get("goal")
        started = time.time()

        # Route by task type
        if cmd.startswith('{"type":"workflow_phase"'):
            try:
                payload = json.loads(cmd)
            except json.JSONDecodeError as e:
                status, result = "failed", {"error": f"bad workflow payload: {e}"}
            else:
                status, result = _run_workflow_phase(pg, task_id, payload)
        elif goal:
            status, result = _run_goal_task(pg, task_id, cmd, goal)
        else:
            try:
                proc = subprocess.run(
                    shlex.split(cmd), shell=False, capture_output=True,
                    text=True, timeout=TIMEOUT,
                )
                elapsed = round(time.time() - started, 2)
                status  = "completed" if proc.returncode == 0 else "failed"
                result  = {
                    "returncode": proc.returncode,
                    "stdout":     proc.stdout.strip()[-2000:],
                    "stderr":     proc.stderr.strip()[-500:],
                    "elapsed_s":  elapsed,
                }
            except subprocess.TimeoutExpired:
                status = "failed"
                result = {"error": "timeout", "elapsed_s": TIMEOUT}
            except Exception as e:
                status = "failed"
                result = {"error": str(e)}

        try:
            pg.task_complete(task_id, result, status)
        except Exception as e:
            print(f"kart_poll: task_complete failed for {task_id}: {e}", file=sys.stderr)

        print(f"kart_poll: {task_id} → {status} ({cmd[:60]})", file=sys.stderr)

    pg.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
