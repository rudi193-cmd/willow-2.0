---
name: kart
description: Kart execution plane — queue shell work via agent_task_submit instead of agent Bash.
---

# Kart — execution plane

Kart runs **all shell-class work** (ls, git, pytest, pipelines, scripts). Agent Bash is blocked for that; Willow MCP is the **data** lane (kb, soil, fleet, handoff).

**Why Kart over agent Bash:**
- Auditable Postgres task log (status, stdout, stderr, elapsed)
- `bash -c` in bwrap — pipelines and `&&` work (not shlex-split argv)
- Survives session close (`kart_poll` on Stop + `kart-worker` daemon)
- `script_body` writes under `{WILLOW_ROOT}/.kart-scripts/` (inside bwrap rw bind), not fragile `/tmp` agent paths

## Pattern: submit → run → status

```
# Simple shell
agent_task_submit(app_id="hanuman", task="ls -la /home/sean-campbell/github/willow-2.0")
kart_task_run(app_id="hanuman")
agent_task_status(app_id="hanuman", task_id="<task_id>")

# Python / nested quotes — use script_body (writes .kart-scripts/kart-*.py under WILLOW_ROOT)
agent_task_submit(
    app_id="hanuman",
    script_body='import json\nprint(json.dumps({"ok": True}))',
)
kart_task_run(app_id="hanuman")
```

Do **not** paste huge escaped one-liners into `task=` when `script_body` is available.

## What runs where

| Work | Lane |
|------|------|
| ls, git, pytest, curl, shell pipelines | Kart (`agent_task_submit`) |
| kb_search, soil_get, fleet_status, handoff_latest | Willow MCP |
| Read repo source files | `Read` tool (or Kart for non-repo paths) |

## Daemon + Stop drain

- `kart-worker.service` claims pending tasks continuously
- `kart_task_run` polls until tasks complete (does not need to spawn shell itself)
- `stop.py` runs `scripts/kart_poll.py` at session Stop

## allow_net

`agent_task_submit(..., allow_net=True)` for git push, `gh`, curl, etc.

## Timeouts

Default 120s (`KART_POLL_TIMEOUT`). Stop drain uses `KART_POLL_STOP_TIMEOUT` (default 130s).

## Pending tasks

```
agent_task_list(app_id="hanuman", agent="kart", limit=10)
```
