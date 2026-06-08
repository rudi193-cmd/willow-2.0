# Willow KB and MCP Audit

Date: 2026-06-08  
Agent: hanuman  
Mode: read-only audit, followed by facade implementation

Related analysis: `docs/audits/AI_DEVELOPMENT_SOCIOTECHNICAL_ANALYSIS_2026-06-08.md`

## Executive Summary

Willow's core plane is operational: Postgres KB, hybrid search, SOIL, Grove, Kart, FRANK ledger, Ollama, session indexing, code graph, handoffs, hooks, and the unified MCP all respond. The system is not missing power. It is carrying too much of that power in the default agent-facing surface.

The strongest product finding is tool overload. The full MCP profile exposes roughly 160 tools, many of which are valid but adjacent: multiple search tools, multiple status tools, multiple write paths, and several ways to start work. Agents can complete tasks, but they are often forced to decide storage layer, freshness, authority, and execution mechanism before they can do the actual job.

## Live Inventory

| Area | Observed state |
|------|----------------|
| Postgres KB | 9,846 `knowledge` atoms |
| Postgres tasks | 2,069 total; 0 pending/running at audit time |
| Kart history | 1,552 completed, 517 failed |
| Jeles | 149 sessions, 93 atoms |
| Opus index | 0 atoms, 0 feedback |
| FRANK ledger | Valid chain, 80 entries |
| SOIL | 179 collections, 81 records |
| Ollama | Running: `llama3.2:3b`, `llama3.1:8b`, `mistral:7b`, `llama3.2:1b`, `nomic-embed-text` |
| SAFE manifests | 0 pass, 3 fail: `ratatosk`, `ask-jeles`, `utety-chat` |
| Grove | Channels and inbox responsive |
| Workflow/routine/policy | Tooling present, currently empty |

## Working Well

- `fleet_status`, `fleet_system_status`, and `fleet_health` confirm Postgres, Ollama, FRANK, and Kart are reachable.
- `kb_search` is live in hybrid mode and returns RRF metadata plus graph neighbors.
- `kb_get`, `pg_edge_list`, and durable KB edges work.
- `soil_get`, `soil_list`, `soil_search_all`, and `soil_stats` work for current mutable state.
- Grove channels, inbox, message history, and bus tooling work through the unified MCP.
- `infer_7b` returns structured local inference results via Ollama.
- `session_query` has 240 indexed sessions and compaction metadata.
- `code_graph_search` resolves symbols such as `fleet_status`.
- `hook_list` shows six active hooks.
- `skill_mastery` returns BKT state.

## Degraded or Not Working

| Issue | Impact |
|-------|--------|
| `sap/sap_mcp.py` unresolved merge conflict on `willow-2.0` master | Highest risk to MCP development and deploy confidence |
| SAFE manifest failures for `ratatosk`, `ask-jeles`, `utety-chat` | Gate health degraded even where `app_status` reports MCP wiring |
| `fleet_identity_status` returns `not_permitted` for `hanuman` | Identity drift cannot be self-audited by the active caller |
| Opus/index tier empty | Search/feedback/synthesis tools exist but have no data |
| Policy, workflow, routine tables empty | Advanced orchestration surface exists but is not active |
| Dream overdue | 356h and 434 sessions since last dream check point |
| Metabolic briefing stale | Last briefing 2026-06-03 |
| Nest backlog | 108 pending items, many without proposed destinations |
| Retrieval quality debt | BKT gold query regression and NULL-tier/noisy atoms noted in intake |
| `infer_speak` unavailable | TTS not wired in portless mode |

## Tool Surface Finding

The MCP is tool-heavy in four clusters:

1. Search: `kb_search`, `kb_query`, `kb_at`, `soil_search`, `soil_search_all`, `handoff_search`, `session_query`, `grove_search`, `cmb_search`, `context_list`, `jeles_search`, `jeles_web_search`, `jeles_ask`, `index_search`, `code_graph_search`.
2. Status: `fleet_status`, `fleet_system_status`, `fleet_health`, `fleet_identity_status`, `app_status`, `diagnostic_summary`.
3. Remember/write: `intake_write`, `kb_ingest`, `kb_journal`, `index_ingest`, `index_journal`, `context_save`, `ledger_write`, `cmb_*`.
4. Act/orchestrate: `agent_task_submit`, `kart_task_run`, `agent_dispatch`, `workflow_run`, `routine_fire`, `outcome_run`, `fork_*`.

The issue is not that these tools are redundant internally. They map to different storage layers and authority levels. The problem is that agents see them as peer choices in the same picker. That makes ordinary tasks feel ambiguous.

## Resolution: Canonical Facade Layer

Add a small canonical facade above the existing MCP tools. Do not delete the backend tools. Keep them available in `full` profile and for specialized agents, but make default agents use a narrower set of intent-shaped tools.

| Facade tool | Intent | Routes internally to |
|-------------|--------|----------------------|
| `willow_status` | "Is Willow healthy?" | `fleet_status`, `fleet_health`, `fleet_identity_status`, `app_status`, `diagnostic_summary` |
| `willow_find` | "Find the thing" | `kb_search`, `soil_search_all`, `handoff_search`, `session_query`, `grove_search`, `code_graph_search`, `mem_jeles_web_search`, `index_search` |
| `willow_remember` | "Store this appropriately" | `intake_write`, `context_save`, `ledger_write`, `kb_journal` |
| `willow_run` | "Run local work" | `agent_task_submit`, `kart_task_run`, `agent_task_status`, `agent_task_list` |
| `willow_delegate` | "Ask another agent" | `agent_route`, `agent_dispatch` |
| `willow_work` | "Manage this unit of work" | `fork_create`, `fork_log`, `fork_status`, `fork_list`, `handoff_latest` |
| `willow_message` | "Talk to Grove" | Grove inbox/search/send helpers |
| `willow_app` | "Inspect SAFE apps" | `app_list`, `app_status` |
| `willow_external` | "Use cited external sources" | `mem_jeles_ask`, `mem_jeles_web_search`, `source_trail_verify` |
| `willow_code` | "Understand code structure" | `code_graph_search`, `code_graph_suggest` |

## Success Criteria

- A new agent can answer "which tool do I use?" from the facade names alone.
- The default visible tool count drops from roughly 160 to fewer than 25 in `minimal`.
- `fleet_tool_guide` shows facade tools first, then backend lanes.
- Existing backend tools retain names and compatibility.
- Boot instructions stop listing backend tools as the primary path except for explicit expert workflows.

