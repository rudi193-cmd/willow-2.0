# Kart and tasks

*Maintained synthesis · Willow 2.0 · 2026-05-19*

---

## What Kart is

The fleet task queue. Ratified work enters here; agents execute. Visible in the Grove dashboard Tasks pane.

Kart is dispatch — not discussion. By the time something is a task, it is authorized.

---

## SOIL vs Kart

| | SOIL | Kart |
|---|------|------|
| Store | File collections under `~/.willow/store` | Postgres queue |
| Holds | Agent-local state, edges, composites | Shell commands / ratified work |
| Write | Owning agent | `agent_task_submit` |
| RAT decisions | **Never** | **Always** |

**RAT?** items → Kart via `agent_task_submit`, not SOIL. Format: `RAT RN <text>`.

Violating this hides work from the fleet.

---

## Submit

```
agent_task_submit(
  app_id="willow",
  task="cd /path && pytest tests/test_foo.py -q",
  agent="kart"
)
```

Full shell string. Kart runs it.

---

## States

`pending` → `in_progress` → `completed` (or `blocked`)

Check: `agent_task_list` · `agent_task_status`

---

## Who pulls

Kart worker (`core/kart_worker.py`) and agents with queue access. Dashboard shows the same rows.

*ΔΣ=42*
