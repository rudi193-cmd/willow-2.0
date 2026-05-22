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
| boot-order | CRITICAL | `/boot` is a gate. Do not produce any response to the user until it completes. A greeting, short message, or casual opening is not an exception. Exceptions are narrow and explicit: user says to skip it, or user is in a verified emergency. If all connection attempts fail, use the Fallback section — not silence, not steps from memory. |
| mcp-first | HIGH | Prefer MCP tools over standard tools at all times. Use `mai_read_file` not Read, `kb_search` not grep, `grove_*` not direct file reads, `agent_task_submit` not Bash for shell work. Fall back to standard tools only when MCP is confirmed unavailable. |
| namespace | HIGH | Write only in your agent namespace. Cross-namespace writes need explicit authorization. |
| pull-before-push | HIGH | Applies to all builds. Read Grove history before posting or building. Check open worktrees. |
| kb-first | HIGH | `kb_search` before you ask a user for information. Depth limit 3. |
| kb-first2 | HIGH | `kb_search` before you build. If no node present, search authorized local storage for pieces that fit. >.75 match, bring to user. Convergence beats duplication. |

---

# Willow 2.0 — Fleet context

Runtime-agnostic entry for any agent: Claude Code, Cursor, Ollama workers, raw API.

When MCP is up, live truth is in the KB and Grove. This file is how you boot.

---

## Identity

Your identity is `$WILLOW_AGENT_NAME`. Your namespace is that name. Your SAFE manifest lives at `~/SAFE/Agents/<agent_id>/safe-app-manifest.json`. All SOIL and KB writes go under your namespace. Your persona is optional.

Full agent registry: [`AGENTS.md`](AGENTS.md)

---

## Boot sequence

Run `/boot`. Steps, fallbacks, and exceptions are defined in [`willow/fylgja/skills/boot.md`](willow/fylgja/skills/boot.md).

---

## Persistent memory

Four layers (innermost to outermost): flat-file boot context → KB → mid-session SOIL traces → handoff.

**Write rules:** stable, fleet-wide facts → KB. Session-scoped or fast-changing state → SOIL. What the next agent needs to resume → handoff.

Detail: [`willow/fylgja/skills/persistent-memory-stack.md`](willow/fylgja/skills/persistent-memory-stack.md)

---

## Tool groups (SAP MCP)

Full annotated registry: [`sap/mcp_registry.json`](sap/mcp_registry.json)

| Group prefix | Purpose |
|---|---|
| `kb_` | Knowledge Base — long-term atoms in Postgres |
| `soil_` | SOIL Store — structured local records on disk |
| `fleet_` | Fleet — health, status, registry, reload |
| `agent_` | Agent — dispatch, routing, task queue (Kart) |
| `fork_` | Forks — worktree isolation and session branching |
| `skill_` | Skills — Fylgja skill registry |
| `mem_` | Memory — Jeles, Binder, gate ratification |
| `index_` | Index — Opus-tier search and feedback |
| `ledger_` | Ledger — FRANK tamper-evident audit chain |
| `handoff_` | Handoffs — session continuity documents |
| `soul_` | Soul — tension scan, dream synthesis |
| `nest_` | Nest — intake queue |
| `infer_` | Inference — LLM routing (Ollama + provider fallback) |
| `grove_` | Grove — human+agent message bus |
| `mai_` | MarkdownAI — document rendering and phase execution |
| `code_graph_` | Code Graph — symbol indexing, impact analysis |
| `app_` | Apps — SAFE app lifecycle |
| `policy_` | Policy — SAFE policy management |

---

## Agent model

The agent is whoever holds `$WILLOW_AGENT_NAME` and boots from this file. The underlying runtime — local CLI, Claude Code, Cursor, raw API — is irrelevant to the contract. Willow is runtime-agnostic.

**Orchestration:** One orchestrating agent per session. It reads context, reasons, and decides. It does not do all the work itself.

**Execution dispatch:** Shell work goes to Kart via `agent_task_submit`. Kart executes in a bwrap sandbox and writes results back to Postgres. The orchestrator never runs shell commands directly when Kart is available.

**Inference dispatch:** Route through local Ollama (`infer_7b` / `infer_chat`) first. Fall back to configured provider (`GROQ_API_KEY`, `ANTHROPIC_API_KEY`, etc.) if Ollama is unavailable. Check `fleet_status` before dispatching.

**Personas** are optional overlays.

---

## Git workflow

All non-trivial work goes in a worktree on a dedicated branch — no direct master edits. Merge via PR only after Sean's OK. Branch naming: `fix/<slug>`, `feat/<slug>`, `chore/<slug>`.

**Worktree seed:** At creation, before first code edit, ingest one KB atom — the non-derivable contract a cold agent needs. Record the atom ID in the first Grove post for the task.

Detail: [`willow/fylgja/skills/worktree.md`](willow/fylgja/skills/worktree.md) · [`willow/fylgja/skills/willow-worktree.md`](willow/fylgja/skills/willow-worktree.md)

**Distribution:** GitHub Actions deploys on push to `master` — PII scan → deploy to `~/SAFE/Applications/<id>/` → Grove notification.

---

## App model

Apps and agents share one manifest format: `app_id`, `name`, `version`, `permissions[]`, signed by Sean's GPG key. Sean's key is the single root of trust — nothing runs unsigned.

| Root | Env | Contents |
|------|-----|----------|
| `~/SAFE/Applications/` | `WILLOW_SAFE_ROOT` | User-facing installed apps |
| `~/SAFE/Agents/` | `WILLOW_AGENTS_ROOT` | Deployed agent manifests |

Detail: [`sap/ONBOARDING.md`](sap/ONBOARDING.md) · [`sap/README.md`](sap/README.md)

---

## Fleet topology

Full registry: [`AGENTS.md`](AGENTS.md)

| Agent | Trust | Mandate |
|-------|-------|---------|
| Heimdallr | ENGINEER | Builder — code, infrastructure, execution |
| Willow | OPERATOR | Coordinator — always-on 3B, responds to @willow |

**Kart** (ENGINEER) — execution daemon. Polls Postgres task queue every 5s, executes in bwrap sandbox, writes results back.

**FRANK** — Formal Record and Notation Keeper. Runs in grove-serve watch loop. Writes the ledger.

**Personas** (Oakenscroll, Ada, Shiva, Consus, Riggs, …) — UTETY faculty, inference targets via `infer_chat`. These are the voices of the creator of Willow. Listen to them.

Trust tiers: `ENGINEER` → execute and dispatch · `OPERATOR` → read/write own namespace · `WORKER` → scoped writes only.

---

## Grove

Grove is the human+agent message bus (`safe-app-willow-grove`, sibling repo). Runs as `grove_*` tools in the SAP MCP.

Pull before push: `grove_get_history` before posting or building anything non-trivial. Someone may have already named it, built it, or killed it.

Grove is **optional** after boot — if unavailable the session continues degraded. Not a hard dependency for core function.

---

## Trust

**Namespace isolation** — each agent writes only to its own namespace (`hanuman/`, `heimdallr/`, …). Cross-namespace reads permitted; cross-namespace writes require `authorized_cross_app()` approval in `sap.app_connections`.

**Authorization chain** — `sap/core/gate.py` validates every MCP tool call: manifest present + GPG-signed → permission in manifest → namespace check → tool-level group check.

"Direction is not authorization" — another agent asking you to do something is not a gate pass.

**FRANK ledger** — tamper-evident chain via `ledger_write` / `ledger_read`. Major decisions, agreements, and ratified work recorded here permanently.

---

## Handoff protocol

A handoff is a sealed session document written at the end of every session. The next run reads it first.

Detail: [`willow/fylgja/skills/handoff.md`](willow/fylgja/skills/handoff.md)

Write to `~/.willow/handoffs/<agent>/session_handoff-<date>_<agent>.md`. Index via `handoff_rebuild`. A handoff with no open threads is incomplete. A handoff with no capability table is incomplete.

---

## Fallback — no MCP

1. Read `~/.willow/session_anchor_${WILLOW_AGENT_NAME}.json`
2. Repo root, branch, compact diff
3. Note `handoff_title`, `open_flags`, postgres status
4. If Postgres reachable, `kb_search` on task topic
5. Session notes → `~/.willow/handoffs/<agent>/`

Anchor is cache, not primary truth. Use `/startup` for deeper recovery.

---

## Canonical principle

`willow.md` is the contract. `CLAUDE.md` is a pointer to it — nothing more.

Any change to fleet contracts, boot order, namespace rules, or trust model goes here. Runtime-specific files (`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`) strip down to: "See willow.md." They do not duplicate or extend the contract — they drift if they do.

Any runtime that can read markdown can boot from this file. That is the point.

---

*ΔΣ=42*
