b17: WLWMD · ΔΣ=42

## Glossary

**agent:** — A named participant with a namespace and SAFE manifest.  
**fleet:** — The coordinated agents plus humans on Grove.  
**handoff:** — A sealed session document the next run reads first.  
**SOIL:** — Local structured store (collections on disk).  
**KB:** — Long-term knowledge atoms in Postgres/SQLite.  
**Grove:** — Messaging bus (sibling repo `safe-app-willow-grove`).

## Constraints

| ID | Severity | Rule |
|----|----------|------|
| boot-order | HIGH | Read `willow.md`, establish compact local operating context, then `fleet_status`, `handoff_latest`, `grove_get_history`, `kb_search` before non-trivial work. |
| namespace | HIGH | Write only in your agent namespace. Cross-namespace writes need explicit authorization. |
| pull-before-push | HIGH | Read Grove history before posting or building. Someone may have already done it. |
| kb-first | HIGH | `kb_search` before you build. Convergence beats duplication. |

---

# Willow 2.0 — Fleet context

Runtime-agnostic entry for any agent: Claude Code, Cursor, Ollama workers, raw API.

When MCP is up, live truth is in the KB and Grove. This file is how you boot.

---

## Identity

[AI INSTRUCTION — context]

Agent: `$WILLOW_AGENT_NAME` (required — no silent defaults)  
Database: `$WILLOW_PG_DB` (default `willow_20`)

Write only in your namespace (`heimdallr/`, `hanuman/`, `orin/`, …).  
Never `public/` or another agent's tree without authorization.

[/AI INSTRUCTION]

---

## Boot sequence

| Step | Surface | Purpose |
|------|---------|---------|
| 1 | `markdownai-read_file("willow.md")` | Load this contract |
| 2 | Local context | Agent, repo root, branch, compact diff (counts only — no full patch unless asked) |
| 3 | `fleet_status` | Postgres + SOIL + Ollama + manifests |
| 4 | `handoff_latest` | What was in flight |
| 5 | `grove_get_history` | Fleet channel / inbox continuity |
| 6 | `kb_search` | Task topic before design or execution |
| 7 | Stop or act | If degraded, surface and stop |

Shell fallback (no MCP): `./willow.sh fleet_status` · `./willow.sh handoff_latest`

---

## Persistent memory

Three layers:

1. **Boot** — orient from live truth.  
2. **Mid-session** — compact traces as you work.  
3. **End-session** — seal the handoff so the next run is not blind.

Detail: `willow/fylgja/skills/persistent-memory-stack.md`

---

## Tool groups (SAP MCP)

| Group | Tools | Purpose |
|-------|-------|---------|
| KB | `kb_search`, `kb_get`, `kb_query`, `kb_ingest`, `kb_at` | Long-term atoms |
| SOIL | `soil_get`, `soil_put`, `soil_search`, `soil_list`, `soil_update` | Local records |
| Fleet | `fleet_status`, `fleet_health`, `fleet_agents` | Health + registry |
| Handoffs | `handoff_latest`, `handoff_search`, `handoff_rebuild` | Session continuity |
| Tasks | `agent_task_submit`, `agent_task_list`, `agent_task_status` | Kart queue |
| Inference | `infer_chat`, `infer_7b`, `infer_speak`, `infer_imagine` | LLM |
| Forks | `fork_create`, `fork_status`, `fork_list` | Worktree isolation |
| Memory | `mem_check`, `mem_ratify`, `mem_jeles_*` | Gate + Jeles |
| Grove* | `grove_*` | *Grove MCP in sibling repo* |

---

## Fallback — no MCP

1. Read `~/.willow/session_anchor_${WILLOW_AGENT_NAME}.json`  
2. Repo root, branch, compact diff  
3. Note `handoff_title`, `open_flags`, postgres status  
4. If Postgres reachable, search KB on task topic  
5. Session notes → `~/.willow/<agent>/`

Anchor is cache, not primary truth. `/startup` only when boot is degraded or stale.

---

*ΔΣ=42*
