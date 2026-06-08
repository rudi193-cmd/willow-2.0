# Willow fleet contract (public snapshot)

b17: PUBCNT · ΔΣ=42

> **Auto-generated** from `~/github/.willow/willow.md` on 2026-05-31.
> Run `python3 scripts/sync_contract_snapshot.py` after editing the private contract.
>
> This file is a **redacted snapshot** for GitHub-only clones. Machine-specific paths,
> persona tables, and operator secrets stay in **willow-config** — see [`WILLOW_CONFIG.md`](WILLOW_CONFIG.md).

---


## Glossary

**agent:** — A named participant with a namespace and SAFE manifest.  
**fleet:** — The coordinated agents plus humans on Grove.  
**handoff:** — A sealed session document the next run reads first.  
**KB:** — Long-term knowledge atoms in Postgres. Three tiers: `knowledge` (main), `jeles_atoms` (cited/external), `opus.atoms` (Opus-tier synthesis).  
**SOIL:** — Local structured store (collections on disk). Use for fast-changing session state; graduate stable facts to KB.  
**Jeles:** — The fleet librarian. Multi-source academic search (29 trusted sources, no Wikipedia). Verifies KB atoms against external citations. Source of the `jeles_atoms` tier.  
**Intake:** — Unified annotated write path (`core/intake.py`). Every agent, tool, and script writes here first: `~/github/.willow/intake/<agent>/YYYY-MM-DD.jsonl`. Schema: `{id, content, title, source, agent, tier, confidence, keywords, tags, created_at, promoted, promote_tier}`.  
**norn-pass:** — Promotion daemon (`scripts/promote_intake.py`). Reads intake records and routes them to the right KB tier via infer_7b classify. Fallback routing is tier+confidence heuristic.  
**Binder:** — Human-reviewed filing system. `mem_binder_file` proposes an edge; `mem_binder_edge` registers the link; `mem_ratify` stamps it as human-confirmed. Final tier for low-confidence intake records.  
**Grove:** — Messaging bus (sibling repo `safe-app-willow-grove`).  
**SAP:** — Safe Application Protocol — the gate, manifest system, and MCP server for Willow tools.  
**Kart:** — Execution daemon. Polls the Postgres task queue and runs shell work in a bwrap sandbox.  
**FRANK:** — Formal Record and Notation Keeper. Persona in the grove-serve watch loop. Writes the ledger.  
**UTETY:** — The professor/persona layer. Inference targets below the fleet, not fleet members.

## Constraints

| ID | Severity | Rule |
|----|----------|------|
| boot-order | CRITICAL | `/boot` is a gate. Do not produce any response to the user until it completes. A greeting, short message, or casual opening is not an exception. Exceptions are narrow and explicit: user says to skip it, or user is in a verified emergency. If all connection attempts fail, use the Fallback section — not silence, not steps from memory. |
| mcp-first | HIGH | **Use MCP tools. Not standard tools.** Full annotated registry: `sap/mcp_registry.json` (80+ tools, grouped by prefix). When you reach for a standard tool, stop and check the registry first. Substitutions: `Read` → `mai_read_file` (for .md) or `kb_get` (for atoms); `grep`/`find` → `kb_search`, `soil_search`, `code_graph_search`; `Bash` (shell work) → `agent_task_submit`; direct Grove/handoff reads → `grove_get_history`, `handoff_latest`; direct KB writes → `intake_write` then norn-pass. Fall back to standard tools only when `fleet_status` confirms MCP unavailable. |
| namespace | HIGH | Write only in your agent namespace. Cross-namespace writes need explicit authorization. |
| pull-before-push | HIGH | Applies to all builds. Read Grove history before posting or building. Check open worktrees. |
| worktree-pr | CRITICAL | **Every code change goes through a worktree + PR. No direct commits to master — ever.** Use `fork_create` to open a worktree. Merge only after CI passes and Sean approves. Branch naming: `fix/<slug>`, `feat/<slug>`, `chore/<slug>`. |
| kb-first | HIGH | `kb_search` before you ask a user for information. Depth limit 3. |
| kb-first2 | HIGH | `kb_search` before you build. If no node present, search authorized local storage for pieces that fit. >.75 match, bring to user. Convergence beats duplication. |
| intake-first | HIGH | Any fact, artifact, or observation worth keeping goes to intake first (`intake_write` or `core/intake.py`). Do not write directly to `knowledge` or `jeles_atoms` from ad-hoc code unless you are norn-pass or a trusted promotion path. |
| no-dogfooding | CRITICAL | **No dogfooding.** Do not ship a “demo path” that only works in the current session while leaving production wiring broken. If you change a default, path, or service, update every layer that still points at the old value — not just the file you touched first. |
| finish-to-completion | CRITICAL | **Finish the task to completion.** When Sean asks to fix something, fix it end-to-end and verify it. No partial cleanup, no “next steps for you,” no deferring systemd/MCP/hooks/cron/install scripts while claiming the job is done. If you cannot finish, say what is blocked and what remains — do not pretend it is wired. |

---

# Willow 2.0 — Fleet context

Runtime-agnostic entry for any agent: Claude Code, Cursor, Ollama workers, raw API.

When MCP is up, live truth is in the KB and Grove. This file is how you boot.

---

## Identity



## Runtime vs inference (CLI and provider agnostic)

| Layer | What it is |
|-------|------------|
| **Runtime** | Cursor, Claude Code, Codex, Gemini CLI — transport only |
| **Agent** | `$WILLOW_AGENT_NAME` — Postgres, Grove sender, SOIL namespace |
| **Inference** | Ollama / Gemini / Groq 70b — `core/inference_router.py`, env `WILLOW_INFERENCE_PROVIDER` |

The IDE model is not the agent. Do not let Claude (or any provider) take credit for another agent's dispatch rows.

Detail: `willow-2.0/docs/RUNTIME_AND_INFERENCE.md`


## Agent identity (separate entities)

Each agent is its own namespace in Postgres, Grove, and SOIL. **Do not** run every session as hanuman.

- Set identity: `cd ~/github/willow-2.0 && ./willow.sh agents active <id> && ./willow.sh agents install <id> --ide <cursor|claude|codex>`
- `WILLOW_AGENT_NAME` / MCP `app_id` = **caller**; `agent_dispatch(to=…)` = **recipient**
- `install_project` updates `.willow/active-agent` — it does **not** set `fleet.default_agent` unless `--set-fleet-default`
- Open **`willow-2.0`** in the IDE, not `~/github/.willow` (private config only)

Detail: `willow-2.0/docs/AGENT_IDENTITY.md`

Your identity is `$WILLOW_AGENT_NAME`. Your namespace is that name. Your SAFE manifest lives at `~/github/SAFE/Agents/<agent_id>/safe-app-manifest.json`. All SOIL and KB writes go under your namespace. Your persona is optional.

Full agent registry: [`AGENTS.md`](../AGENTS.md)

---

## Boot sequence

Run `/boot`. Steps, fallbacks, and exceptions are defined in [`willow/fylgja/skills/boot.md`](../willow/fylgja/skills/boot.md).

---

## Knowledge architecture

Three tiers, one intake funnel:

```
Any source (MCP tool, script, Nest confirm, session extract)
        |
  core/intake.py  —  annotated JSONL, ~/github/.willow/intake/<agent>/
        |
  norn-pass (promote_intake.py)
        |  infer_7b classify -> route decision
   +----+-----------------------------+
   |                                  |
jeles_atoms                     knowledge (main KB)
(cited, external)               (stable, fleet-wide)
   |                                  |
   +------- low confidence ---------> Binder
                                      (human review queue)
                                           |
                                           v
                                      opus.atoms (Opus synthesis)
```

**Tier rules:**

| Tier | Table | When |
|------|-------|------|
| `jeles_atoms` | `jeles_atoms` | External citation exists, relevance_score >= 0.5 |
| `knowledge` | `knowledge` | Stable fleet fact, verified, confidence >= 0.80 |
| `opus.atoms` | `opus.atoms` | Opus-tier synthesis, high-signal cross-domain |
| `binder_queue` | Binder edge proposal | Low confidence, or needs human review |

**Intake tiers** (set at write time):

| Tier string | Meaning |
|-------------|---------|
| `observed` | Raw session fact, unverified |
| `fetched` | Retrieved from an external source |
| `verified` | Checked against trusted source (Jeles or human) |
| `ratified` | Human-confirmed via Binder |

**Jeles verification** (`agents/hanuman/bin/extract_jeles_corpus.py`): queries 14+ trusted academic sources per KB atom, runs infer_7b classify (corroborates / unrelated / contradicts), writes `jeles_relevance_score` + `jeles_citations` back into the atom's JSONB content field.

**Fleet intake directories:** Every registered fleet agent has a staging dir at `~/github/.willow/intake/<agent>/`. Created idempotently on SessionStart and via `scripts/scaffold_fleet_intake_dirs.py`. Norn-pass (`promote_intake.py --fleet`) promotes all agents with pending JSONL records.

**Promotion parity:**

| Path | Behavior |
|------|----------|
| `intake_write` / `core/intake.py` | Annotated JSONL staging — default write path |
| `promote_intake.py --fleet` | Fleet-wide norn-pass (also runs at end of metabolic/norn pass) |
| `kb_ingest` | Direct KB write — use for rubric-passing summaries only |
| Stop hook (`stop_slow`) | Friction sessions → intake; clean sessions → KB only if session quality gate passes |
| `tier=canonical` | Requires provenance + minimum summary quality; failures route to Binder |

---

## Persistent memory

Five layers (innermost to outermost):

1. **Flat-file boot context** — `~/github/.willow/session_anchor_<agent>.json`, `willow.md`
2. **Intake** — `~/github/.willow/intake/<agent>/YYYY-MM-DD.jsonl` — annotated staging area, not yet promoted
3. **KB** — Postgres `knowledge` / `jeles_atoms` / `opus.atoms` — promoted, durable
4. **SOIL** — Local structured records on disk — session-scoped or fast-changing state
5. **Handoff** — Sealed session document — what the next agent needs to resume

**Write rules:**
- Stable, fleet-wide facts → KB (via intake → norn-pass).
- Session-scoped or fast-changing state → SOIL.
- Human-confirmed files or edges → Binder (`mem_binder_file` / `mem_binder_edge` / `mem_ratify`).
- Nest confirms (human files a document) → intake at tier=verified, confidence=1.0.
- What the next agent needs to resume → handoff.

Detail: [`willow/fylgja/skills/persistent-memory-stack.md`](../willow/fylgja/skills/persistent-memory-stack.md)

---

## Tool groups (SAP MCP)

Full annotated registry: [`sap/mcp_registry.json`](../sap/mcp_registry.json)

| Group prefix | Purpose |
|---|---|
| `kb_` | Knowledge Base — long-term atoms in Postgres |
| `soil_` | SOIL Store — structured local records on disk |
| `fleet_` | Fleet — health, status, registry, reload |
| `agent_` | Agent — dispatch, routing, task queue (Kart) |
| `fork_` | Forks — worktree isolation and session branching |
| `skill_` | Skills — Fylgja skill registry |
| `mem_` | Memory — Jeles search/extract/register, Binder edge proposals, gate ratification |
| `mem_jeles_*` | Jeles — multi-source academic search, corpus seeding, cache promotion |
| `intake_write` | Intake — write an annotated record to the unified intake layer |
| `index_` | Index — Opus-tier search and feedback |
| `ledger_` | Ledger — FRANK tamper-evident audit chain |
| `handoff_` | Handoffs — session continuity documents |
| `soul_` | Soul — tension scan, dream synthesis |
| `nest_` | Nest — file intake queue (human drop zone → classified → Binder/KB) |
| `infer_` | Inference — LLM routing (local or provider, resolved by fleet status) |
| `grove_` | Grove — human+agent message bus |
| `mai_` | MarkdownAI — document rendering and phase execution |
| `code_graph_` | Code Graph — symbol indexing, impact analysis |
| `app_` | Apps — SAFE app lifecycle |
| `policy_` | Policy — SAFE policy management |

---

## Agent message protocol

When agents communicate via Willow MCP tools, the `content` field carries a canonical JSONB envelope. Any agent, any runtime — same shape.

```jsonc
{
  "v":          1,
  "from":       "<agent_id>",
  "to":         "<agent_id | __all__>",
  "intent":     "<verb>",
  "ref":        "<atom_id | task_id | null>",
  "tier":       "<observed | fetched | verified | ratified>",
  "confidence": 0.85,
  "body":       {}
}
```

**intent vocabulary:**

| Intent | Meaning |
|--------|---------|
| `dispatch` | Send work to an agent or Kart |
| `query` | Request information; expects a response with matching `ref` |
| `notify` | Informational — no action required |
| `promote` | Ask norn-pass to promote an intake record |
| `ratify` | Request Binder confirmation |
| `flag` | Mark something for review |
| `reject` | Decline — include reason in `body` |
| `handoff` | Session handoff — attach document path in `body` |

`tier` and `confidence` mirror the intake schema. An agent promoting a record via message uses the same vocabulary as `intake_write`. The transport (Grove bus, task queue, direct dispatch) is irrelevant — the envelope is what every reader expects.

---

## Agent model

The agent is whoever holds `$WILLOW_AGENT_NAME` and boots from this file. The underlying runtime — local CLI, Claude Code, Cursor, raw API — is irrelevant to the contract. Willow is runtime-agnostic.

**Orchestration:** One orchestrating agent per session. It reads context, reasons, and decides. It does not do all the work itself.

**Execution dispatch:** Shell work goes to Kart via `agent_task_submit`. Kart executes in a bwrap sandbox and writes results back to Postgres. The orchestrator never runs shell commands directly when Kart is available.

**Inference dispatch:** Use `infer_7b` (classify/extract/summarize) or `infer_chat` (generation). The SAP layer resolves the backend — local Ollama, remote provider, or whichever is available per `fleet_status`. Do not hardcode a backend. Check `fleet_status` before dispatching.

**Personas** are optional overlays.
---

## Execution discipline — no dogfooding

**No dogfooding** means: do not satisfy the agent’s immediate context while leaving the fleet’s real wiring stale. A change is not done when it works once in chat. It is done when everything that *runs* agrees on the new truth.

**Finish to completion** means: when Sean asks to fix, migrate, or wire something, carry the change through every surface that consumes it, then verify. Stop only when the live system matches the intent — or when you report a concrete blocker.

### What “done” requires

| Layer | Examples |
|-------|----------|
| **Private config** | `willow-config` (`~/github/.willow`): `willow.md`, `env`, `settings.global.json`, handoffs |
| **Public code** | `willow-2.0`: code, skills, systemd templates — symlinks in from `~/github/.willow` |
| **User install** | `install_project`, `link_fleet_home`, `~/.config/systemd/user/` |
| **Services** | `systemctl --user` active; health endpoints OK |
| **Verification** | Grep live paths for `willow-1.9` / `willow_19`; no circular symlinks |

#

## Fleet path truth (ThinkPad)

| What | Canonical value |
|------|-----------------|
| Private config repo | `github.com/rudi193-cmd/willow-config` → `~/github/.willow` |
| Fleet code repo | `~/github/willow-2.0` (`WILLOW_ROOT`) |
| Postgres DB | `willow_20` |
| Grove repo | `~/github/safe-app-willow-grove` |
| Fleet env | `~/github/.willow/env` |
| `willow-1.9` / `willow_19` | Archive only — not live defaults |

## Git workflow

**Every change goes in a worktree on a dedicated branch. No exceptions. No direct master edits, ever.**

Use `fork_create` to open a worktree. Work on the branch. Open a PR. CI must pass. Sean approves. Then merge. Branch naming: `fix/<slug>`, `feat/<slug>`, `chore/<slug>`.

This is a hard constraint (`worktree-pr`), not a guideline.

**Worktree seed:** At creation, before first code edit, ingest one KB atom — the non-derivable contract a cold agent needs. Record the atom ID in the first Grove post for the task.

Detail: [`willow/fylgja/skills/worktree.md`](../willow/fylgja/skills/worktree.md) · [`willow/fylgja/skills/willow-worktree.md`](../willow/fylgja/skills/worktree.md)

**Distribution:** GitHub Actions deploys on push to `master` — PII scan → deploy to `~/github/SAFE/Applications/<id>/` → Grove notification.

---

## App model

Apps and agents share one manifest format: `app_id`, `name`, `version`, `permissions[]`, signed by Sean's GPG key. Sean's key is the single root of trust — nothing runs unsigned.

| Root | Env | Contents |
|------|-----|----------|
| `~/github/SAFE/Applications/` | `WILLOW_SAFE_ROOT` | User-facing installed apps |
| `~/github/SAFE/Agents/` | `WILLOW_AGENTS_ROOT` | Deployed agent manifests |

Detail: [`sap/ONBOARDING.md`](../sap/ONBOARDING.md) · [`sap/README.md`](../sap/README.md)

---

## Fleet topology

Full registry: [`AGENTS.md`](../AGENTS.md)

| Agent | Trust | Mandate |
|-------|-------|---------|
| Heimdallr | ENGINEER | Builder — code, infrastructure, execution |
| Willow | OPERATOR | Coordinator — always-on 3B, responds to @willow |

**Kart** (ENGINEER) — execution daemon. Polls Postgres task queue every 5s, executes in bwrap sandbox, writes results back.

**FRANK** — Formal Record and Notation Keeper. Runs in grove-serve watch loop. Writes the ledger.

**Jeles** — Fleet librarian. Runs as `mem_jeles_*` tools. Searches 29 trusted academic/archival sources. Verifies KB atoms. Seeds the `jeles_atoms` tier. Not a conversational agent — a tool layer.

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

Detail: [`willow/fylgja/skills/handoff.md`](../willow/fylgja/skills/handoff.md)

Write to `~/github/.willow/handoffs/<agent>/session_handoff-<date>_<agent>.md`. Index via `handoff_rebuild`. A handoff with no open threads is incomplete. A handoff with no capability table is incomplete.

---

## Fallback — no MCP

1. Read `~/github/.willow/session_anchor_${WILLOW_AGENT_NAME}.json`
2. Repo root, branch, compact diff
3. Note `handoff_title`, `open_flags`, postgres status
4. If Postgres reachable, `kb_search` on task topic
5. Session notes → `~/github/.willow/handoffs/<agent>/`

Anchor is cache, not primary truth. Use `/startup` for deeper recovery.

---

## Canonical principle

`willow.md` is the contract. `CLAUDE.md` is a pointer to it — nothing more.

Any change to fleet contracts, boot order, namespace rules, or trust model goes here. Runtime-specific files (`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`) strip down to: "See willow.md." They do not duplicate or extend the contract — they drift if they do.

Any runtime that can read markdown can boot from this file. That is the point.

---

*ΔΣ=42*

---

*Public snapshot · canonical contract lives in willow-config · ΔΣ=42*
