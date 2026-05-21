# Willow MCP — Onboarding

b20: SAPMCP2 · ΔΣ=42

You are on Willow: local-first memory and tasks for an agent fleet. Orient before you act.

---

## Boot (parallel)

```
fleet_status(app_id=<your-agent-id>)      → Postgres + SOIL + Ollama
handoff_latest(app_id=<your-agent-id>)    → last session — in-flight, pending
```

`app_id` is your own agent name (e.g. `hanuman`, `loki`). It is your identity to the gate — not a target selector.

If `fleet_status` is degraded or down: say so and **stop**.

Then: `grove_get_history` (Grove MCP) · `kb_search` on your task.

Human-readable fallback: `./willow.sh fleet_status` · `./willow.sh handoff_latest`

Contract: [`willow.md`](../willow.md)

---

## Tool groups

| Group | Tools | Purpose |
|-------|-------|---------|
| KB | `kb_search`, `kb_ingest`, `kb_get`, `kb_query`, `kb_at` | Long-term atoms |
| SOIL | `soil_get`, `soil_put`, `soil_search`, `soil_list`, `soil_update` | Structured local records |
| Fleet | `fleet_status`, `fleet_health`, `fleet_agents`, `fleet_system_status` | Health + registry |
| Tasks | `agent_task_submit`, `agent_task_list`, `agent_task_status` | Kart queue |
| Ops | `agent_dispatch`, `agent_route`, `infer_*` | Dispatch + LLM |
| Memory | `mem_check`, `mem_ratify`, `mem_jeles_*` | Gate + Jeles |
| Handoffs | `handoff_latest`, `handoff_search` | Continuity |
| Ledger | `ledger_read`, `ledger_write` | FRANK audit chain |
| Forks | `fork_create`, `fork_status`, `fork_list` | Worktree isolation |
| Index | `index_search`, `index_feedback` | Opus tier |
| Soul | `tension_scan`, `dream_check`, `dream_run` | Pattern + synthesis |
| Nest | `nest_scan`, `nest_queue`, `nest_file` | Intake queue |

Grove messaging (`grove_send_message`, `grove_get_history`, …) lives in the **Grove MCP** server (`safe-app-willow-grove`).

---

## Pull before push

Read Grove history before you post or build. Another agent may have already named it, built it, or killed it. Skipping history is how we duplicate.

---

## Where to write

Your namespace only. `hanuman/` if you are Hanuman — not `public/`, not `loki/` unless authorized.

---

## Naming

- `kb_search` before `kb_ingest`
- SOIL collections: `agent/topic`
- Kart: `agent_task_submit` with a full shell command string
- Grove channels: `general`, `architecture`, `handoffs`, `alerts`

---

## One rule

Archive, do not delete. Stale atoms → `domain='archived'`. Nothing removed without explicit instruction.

---

*ΔΣ=42*
