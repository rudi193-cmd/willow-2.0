@markdownai v1.0

# Willow 2.0 — Fleet Context

@define-concept agent: A named LLM runtime (heimdallr, orin, etc.) with its own namespace in SOIL, KB, and Grove.
@define-concept fleet: The full set of running agents coordinated by Willow MCP.
@define-concept handoff: A verifiable session summary written at shutdown and read at startup for continuity.
@define-concept SOIL: Local structured record store — key/value, no Postgres required.
@define-concept KB: Long-term knowledge graph stored in Postgres. Search before building anything.
@define-concept Grove: Agent messaging bus backed by Postgres LISTEN/NOTIFY.

This file is the runtime-agnostic entry point for any agent joining the Willow fleet.
Read by: Claude Code, Cursor, raw API orchestrators, and local Ollama agents.
Not Claude-specific. When MCP is available, real context lives in the KB — this file tells you how to boot.

---

## Identity

@prompt Read these values to orient before every session.

Agent: @env WILLOW_AGENT_NAME
Database: @env WILLOW_PG_DB

Write only to your agent's namespace (e.g. `heimdallr/`, `orin/`).
Never write to `public/` or another agent's namespace.

@end

---

## Boot sequence

@prompt Default boot path when MCP is available: read this file via markdownai, establish local operating context, then execute the compact 7-step loop below. If any required base is degraded, surface it and stop.

@end

| Step | Surface | Purpose |
|------|---------|---------|
| 1 | `markdownai-read_file("willow.md")` | Load the canonical boot contract |
| 2 | Local operating context | Agent, namespace, repo root, branch, compact repo diff summary |
| 3 | `fleet_status` | Confirms Postgres + SOIL + Ollama are up |
| 4 | `handoff_latest` | Last session state — what was in-flight, what's pending |
| 5 | `grove_get_history` | Fleet continuity for the agent channel/inbox |
| 6 | `kb_search` | Task continuity before design or execution |
| 7 | Stop or act | Surface degraded base, otherwise proceed |

Keep step 2 compact: branch, clean/dirty, staged/unstaged/untracked counts, ahead/behind if known, and a short diff note. Do not dump a full patch at boot unless Sean asks for it.

@constraint id=boot-order
Read `willow.md`, establish compact local operating context, then call `fleet_status`, `handoff_latest`, `grove_get_history`, and `kb_search` before any non-trivial action.
@end

@constraint id=namespace
Agents MUST write only to their own namespace. Cross-namespace writes require explicit authorization.
@end

@constraint id=pull-before-push
Call `grove_get_history` before posting to Grove or building anything non-trivial. Another agent may have already built it.
@end

@constraint id=kb-first
Search KB before building. Use `kb_search` with the task topic. Convergence is proof this works.
@end

---

## Persistent memory stack

This system remembers in three layers:

1. **Boot persistence** — orient from live truth before acting.
2. **Mid-session persistence** — accumulate compact traces while working.
3. **End-of-session persistence** — seal the session so the next one does not start blind.

Canonical detail lives in `willow/fylgja/skills/persistent-memory-stack.md`.

---

## Tool groups

| Group | Tools | Purpose |
|-------|-------|---------|
| KB | `kb_search`, `kb_get`, `kb_query`, `kb_ingest` | Long-term knowledge atoms |
| SOIL | `soil_get`, `soil_put`, `soil_search`, `soil_list` | Structured local records |
| Fleet | `fleet_status`, `fleet_health`, `fleet_agents` | System health + agent registry |
| Handoffs | `handoff_latest`, `handoff_search`, `handoff_rebuild` | Session continuity |
| Tasks | `agent_task_submit`, `agent_task_status`, `agent_task_list` | Work queue |
| Inference | `infer_chat`, `infer_7b`, `infer_speak` | LLM calls — cloud + local Ollama |
| Forks | `fork_create`, `fork_status`, `fork_list` | Worktree isolation |
| Memory | `mem_check`, `mem_ratify` | Memory gate |

---

## Fallback — no MCP available

For raw API calls, Ollama agents, or offline use:

1. Read `~/.willow/session_anchor_@env WILLOW_AGENT_NAME.json`
2. Establish local operating context with repo root, branch, and a compact repo diff summary
3. Note `handoff_title`, `open_flags`, `postgres` status
4. If Postgres is reachable, call `kb_search` on the task topic before building
5. Proceed — write session notes to `~/.willow/` in your agent's namespace

Use the session anchor as a cache/fallback, not the primary truth source. Use `/startup` only for degraded boot, stale context, or deeper continuity recovery.
