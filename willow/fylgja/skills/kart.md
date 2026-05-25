---
name: kart
description: How to use Kart — the fleet task queue. Submit shell work here instead of running Bash directly. Covers submit→run→status flow and common pitfalls.
---

# Kart — Fleet Task Queue

Kart is the execution daemon. Shell work goes to Kart, not directly to Bash. This keeps shell execution auditable, Grove-gated, and out of the LLM token budget.

**Why Kart over Bash:**
- Every task is logged to Postgres with status, output, and elapsed time
- Tasks survive session close (kart_poll drains the queue at Stop)
- No LLM call for pure shell work — subprocess only

## The pattern: submit → run → status

```
# 1. Submit
agent_task_submit(app_id="hanuman", task="python3 /tmp/my_script.py", submitted_by="hanuman")
# Returns: {task_id, status: "pending"}

# 2. Run
kart_task_run(app_id="hanuman")
# Executes all pending tasks (default limit: 5), updates DB

# 3. Check output
agent_task_status(app_id="hanuman", task_id="<task_id>")
# Returns: {status, result: {stdout, stderr, returncode, elapsed_s}}
```

## Rules for commands

**Always write scripts to `/tmp/`, never submit inline Python.**

`kart_task_run` uses `shlex.split(cmd)` — complex shell quoting breaks it:

```bash
# BREAKS — nested quotes in -c string
python3 -c "import json; print(json.dumps({'key': 'val'}))"

# WORKS — script file
python3 /tmp/my_task.py
```

For grep, find, and other shell work: write a Python script that does it, submit the path.

## Commands that work fine via Kart

```
python3 /tmp/script.py
/path/to/venv/bin/python3 /path/to/script.py
git -C /repo status
```

## Commands that fail via Kart

```
python3 -c "..."        # nested quotes break shlex.split
grep -r "pattern" .     # also blocked by pre_tool hook (use kb_search instead)
bash -c "cmd1 && cmd2"  # shell operators not supported (shell=False)
```

For multi-step shell pipelines: write a `.py` file that does the work with `subprocess`.

## Timeout

Default: 120 seconds per task. Override via `KART_POLL_TIMEOUT` env var.

## Viewing pending tasks

```
agent_task_list(app_id="hanuman", agent="kart", limit=10)
```

## Kart drains at session Stop

`kart_poll.py` is wired to the Stop hook in `~/.claude/settings.json`. Pending tasks run automatically when the session closes. You don't need to call `kart_task_run` manually at the end of a session.
