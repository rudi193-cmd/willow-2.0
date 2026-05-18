# Kart and Tasks

*Maintained synthesis — last updated 2026-05-04.*

---

## What Kart Is

Kart is the fleet's task queue. Ratified work items get submitted to Kart; agents pull from it. Kart is visible in the dashboard Tasks pane.

Kart is not a discussion forum. It's a dispatch mechanism. By the time something enters Kart, it's been authorized.

---

## SOIL vs Kart — The Critical Distinction

This distinction has caused routing failures. Get it right:

| | SOIL | Kart |
|-|------|------|
| **What it is** | File-per-collection SQLite store | Postgres task queue |
| **What goes there** | Agent-local structured state (atoms, edges, session composites) | Ratified work items requiring dispatch or execution |
| **Who writes** | The agent in its own namespace | The ratifying agent (`willow_task_submit`) |
| **Who reads** | The owning agent | Any agent pulling tasks |
| **RAT decisions** | Never | Always |

**RAT? decisions go to Kart, never SOIL agent namespace.** Format: `RAT RN <decision text>` — submit via `willow_task_submit`. The R1-R9 decisions in WILLOW_DECISIONS.md are exactly this.

When this distinction was violated earlier (writing RAT decisions to SOIL), the task was invisible to the fleet and required manual recovery.

---

## Submitting Tasks

```
willow_task_submit(
    title="Short task name",
    description="What needs to happen and why",
    app_id="hanuman"
)
```

Returns a task ID. Tasks appear in the dashboard Tasks pane.

---

## Task States

Tasks move through: `pending` → `in_progress` → `completed` (or `blocked`).

Use `willow_task_status` to check, `willow_task_list` to see the queue.

---

## What Belongs in Kart

- Ratified decisions (R1-R9 calls, once Sean makes them)
- Multi-step builds that need explicit tracking
- Cross-agent work items where dispatch matters
- Anything that needs to be visible in the dashboard

---

## What Doesn't Belong in Kart

- In-progress work within the current session (use task tracking in the conversation)
- Discussion items (use Grove)
- KB writes (use `willow_knowledge_ingest` directly)
- SOIL state updates (write directly to the agent's namespace)

---

## The Dashboard Tasks Pane

The Tasks pane in the Grove dashboard reads from Kart. R1-R9 decisions (visible there) are the current outstanding items.

As of 2026-05-04: 9 tasks pending Sean's ratification. Once ratified, each one becomes executable by the fleet without further check-in.
