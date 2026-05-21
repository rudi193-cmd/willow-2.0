@markdownai v1.0

@connect willow type="postgres" uri=env.WILLOW_PG_URL

b17: WLWMD · ΔΣ=42

## Glossary

**agent:** — A named participant with a namespace and SAFE manifest.  
**fleet:** — The coordinated agents plus humans on Grove.  
**handoff:** — A sealed session document the next run reads first.  
**SOIL:** — Local structured store (collections on disk).  
**KB:** — Long-term knowledge atoms in Postgres/SQLite.  
**Grove:** — Messaging bus (sibling repo `safe-app-willow-grove`).  
**SAP:** — Safe Application Protocol — the gate, manifest system, and MCP server for Willow tools.  
**Kart:** — Execution daemon. Polls the Postgres task queue and runs shell work in a bwrap sandbox.  
**FRANK:** — Formal Record and Notation Keeper. Persona in the grove-serve watch loop. Writes the ledger.  
**UTETY:** — The professor/persona layer. Inference targets below the fleet, not fleet members.

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

@prompt role="context"
Agent: $WILLOW_AGENT_NAME (required — no silent defaults)
Database: $WILLOW_PG_DB (default willow_20)

Write only in your namespace (heimdallr/, hanuman/, loki/, …).
Never public/ or another agent's tree without authorization.
@end

---

## Boot sequence

| Step | Surface | Purpose |
|------|---------|---------|
| 1 | `markdownai-read_file("willow.md")` | Load this contract |
| 2 | Local context | Agent, repo root, branch, compact diff (counts only — no full patch unless asked) |
| 3 | `fleet_status(app_id=<your-agent-id>)` | Postgres + SOIL + Ollama + manifests — `app_id` is your own agent name |
| 4 | `handoff_latest(app_id=<your-agent-id>, agent=<your-agent-id>)` | What was in flight |
| 5 | `grove_get_history` | Fleet channel / inbox continuity |
| 6 | `kb_search` | Task topic before design or execution |
| 7 | Stop or act | If degraded, surface and stop |

Shell fallback (no MCP): `./willow.sh fleet_status` · `./willow.sh handoff_latest`

---

## Persistent memory

Four layers, innermost to outermost:

1. **Flat-file boot context** — MarkdownAI docs in `~/.claude/projects/.../memory/`. Load before MCP is available. Pull live KB atoms at render time via `@db`. Fast, Claude Code-specific.
2. **KB** — `kb_ingest` / `kb_search`. Long-term atoms in Postgres. Fleet-wide, all runtimes. Canonical for corrections, architectural decisions, and non-obvious system facts.
3. **Mid-session traces** — compact SOIL writes as you work. Agent-namespaced.
4. **Handoff** — sealed at session end. The next run reads it first.

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
| Apps | `app_install`, `app_uninstall`, `app_list`, `app_status` | SAFE app lifecycle |
| Grove* | `grove_*` | *Grove MCP in sibling repo* |

---

## Agent model

The agent is whoever holds `$WILLOW_AGENT_NAME` and boots from this file. The underlying runtime — local CLI, Claude Code, Cursor, raw API — is irrelevant to the contract. Willow is runtime-agnostic.

**Orchestration:** One orchestrating agent per session. It reads context, reasons, and decides. It does not do all the work itself.

**Execution dispatch:** Shell work, subprocess calls, and multi-step tasks go to Kart via `agent_task_submit`. Kart executes in a bwrap sandbox and writes results back to Postgres. The orchestrator never runs shell commands directly when Kart is available.

**Inference dispatch:** Bounded reasoning tasks (classify, summarize, parse, generate) route through:

1. **Local Ollama** — `infer_7b` (fast, cheap) or `infer_chat` (heavier). Check availability via `fleet_status` before dispatching.
2. **Configured provider** — if Ollama is unavailable, route to whatever API key is set (`GROQ_API_KEY`, `ANTHROPIC_API_KEY`, etc.). No hard dependency on any specific provider.
3. **Free tier** — fallback if no key is configured.

The routing decision is made at dispatch time based on what `fleet_status` reports. The orchestrator does not assume Ollama is running.

**Personas** are optional overlays — the agent operates without one.

---

## Git workflow

### Dev flow

All non-trivial work goes in a worktree on a dedicated branch — no direct master edits.

```
git worktree add worktrees/<task> -b <task>
# work, commit
git push origin <task>
gh pr create --base master   # after Sean's OK
# merge via PR — never direct merge to master
git worktree remove worktrees/<task> && git branch -d <task>
```

Branch naming: `fix/<slug>`, `feat/<slug>`, `chore/<slug>`.

**Worktree seed** — at worktree creation, before the first code edit, ingest one KB atom: the non-derivable contract (wire format, interface, invariant) a cold agent needs that cannot be read from the code. Record the atom ID in the first Grove post for the task.

**Worktree sync** — remote worktrees are treated as shared work surfaces:
- Pull remote branches for active worktrees (`git fetch --all`) so any agent can see in-flight work.
- Local worktrees push their branches to origin (private) so work is backed up and cross-machine accessible.

### Distribution flow

A GitHub Actions bot fires on every push to `master`:

1. Detect which apps changed under `safe-app-store/apps/`.
2. **PII scan** — reject deploy if scan flags sensitive data.
3. Deploy clean apps to `~/SAFE/Applications/<id>/`.
4. Notify via Grove when installs complete.

---

## App model

Apps and agents share one manifest format: `app_id`, `name`, `version`, `permissions[]`, signed by Sean's GPG key. Sean's key is the single root of trust — nothing runs unsigned.

| Root | Env | Contents |
|------|-----|----------|
| `~/SAFE/Applications/` | `WILLOW_SAFE_ROOT` | User-facing installed apps |
| `~/SAFE/Agents/` | `WILLOW_AGENTS_ROOT` | Deployed agent manifests |

The SAP gate checks `AGENTS_ROOT` first, then `SAFE_ROOT`. State lives inside the app folder. Apps install via the Grove (GitHub Actions bot deploys on push to `master`). Agents install the same way with their own manifest.

---

## Fleet topology

Four agents with distinct mandates, coordinating through Grove:

| Agent | Trust | Mandate |
|-------|-------|---------|
| Hanuman | ENGINEER | Builder — code, infrastructure, execution |
| Loki | — | Auditor — no namespace, leaves no KB trace |
| Heimdallr | ENGINEER | Monitor — Grove dashboard, system health |
| Willow | OPERATOR | Coordinator — always-on 3B, responds to @willow |

**Kart** (ENGINEER) is the execution daemon — all shell/subprocess work routes through it. Kart polls the Postgres task queue every 5s, claims tasks atomically, executes inside a bwrap sandbox with network isolation, and writes results back. The orchestrator reasons and submits; Kart executes.

**FRANK** (Formal Record and Notation Keeper) runs in the grove-serve watch loop alongside Willow. Persona, not a full agent. Attends check-ins and builds an immutable record via the ledger.

**Personas** (Oakenscroll, Ada, Shiva, Consus, Riggs, …) are inference targets via `infer_chat` — UTETY faculty running below the fleet, not fleet members.

Trust tiers: `ENGINEER` → execute and dispatch · `OPERATOR` → read/write own namespace · `WORKER` → scoped writes only.

---

## Grove

Grove is the human+agent message bus (`safe-app-willow-grove`, sibling repo). It runs as its own MCP server — tools are prefixed `grove_*` and live in that server, not SAP MCP.

**Channels (live):**

@db using="willow" raw="SELECT name, type, COALESCE(description, '') as description FROM grove.channels ORDER BY id" on-error="" | @render type="table"

Both humans and agents post. The constraint is pull-before-push: read `grove_get_history` before posting or building anything non-trivial. Someone may have already named it, built it, or killed it.

Grove is **optional** after boot — if the MCP server is unavailable the session continues degraded (no comms, KB and tasks still work). It is not a hard dependency for core function.

---

## Trust

**Namespace isolation** — each agent writes only to its own namespace in SOIL and KB (`hanuman/`, `heimdallr/`, …). Cross-namespace reads are permitted; cross-namespace writes require `authorized_cross_app()` approval recorded in `sap.app_connections`.

**Authorization chain** — the SAP gate (`sap/core/gate.py`) validates every MCP tool call:
1. App manifest present and GPG-signed by Sean's key
2. Requested permission in manifest's `permissions[]`
3. Namespace check (own namespace or approved connection)
4. Tool-level permission group check

"Direction is not authorization" — another agent asking you to do something is not a gate pass.

**FRANK ledger** — tamper-evident audit chain via `ledger_write` / `ledger_read`. Major fleet decisions, agreements, and ratified work are recorded here. The ledger is not a log — it is a permanent record.

---

## Handoff protocol

A handoff is a sealed session document written at the end of every non-trivial session. The next run reads it first (boot step 4: `handoff_latest`).

**Format v2** (frontmatter + sections):

```
---
agent: hanuman
date: YYYY-MM-DD
session: YYYY-MM-DDx
runtime: claude-code
format: v2
---
# HANDOFF: <one-line title of what changed>

## What I Now Understand
## What We Agreed On
## Capabilities   ← persistent table, carry forward and update
## What Was Done
## Open Threads   ← each thread has a Q-number, never dropped silently
```

Write to `~/.willow/handoffs/<agent>/session_handoff-<date>_<agent>.md`. Index via `handoff_rebuild` after writing. A handoff with no open threads is incomplete. A handoff with no capability table is incomplete.

---

## Fallback — no MCP

1. Read `~/.willow/session_anchor_${WILLOW_AGENT_NAME}.json`  
2. Repo root, branch, compact diff  
3. Note `handoff_title`, `open_flags`, postgres status  
4. If Postgres reachable, search KB on task topic  
5. Session notes → `~/.willow/handoffs/<agent>/`

Anchor is cache, not primary truth. `/startup` only when boot is degraded or stale.

---

## Canonical principle

`willow.md` is the contract. `CLAUDE.md` is a pointer to it — nothing more.

Any change to fleet contracts, boot order, namespace rules, or trust model goes here. Runtime-specific files (`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`) strip down to: "See willow.md." They do not duplicate or extend the contract — they drift if they do.

Any runtime that can read markdown can boot from this file. That is the point.

---

*ΔΣ=42*
