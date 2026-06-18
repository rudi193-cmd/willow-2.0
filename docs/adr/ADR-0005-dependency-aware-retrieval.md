@markdownai v1.0

# ADR-0005: Dependency-Aware Global Context Retrieval

**Status:** Accepted
**Date:** 2026-06-18
**Issue:** [#267](https://github.com/rudi193-cmd/willow-2.0/issues/267)
**Depends on:** [ADR-0001](ADR-0001-single-user-operating-layer.md) · [ADR-0002](ADR-0002-intent-kernel.md) · [ADR-0003](ADR-0003-delegation-authority.md) · [ADR-0004](ADR-0004-persona-policy-precedence.md)
**Supersedes:** none

---

## Context

Willow retrieves code and KB atoms reliably. It does not reliably retrieve the operational
context that surrounds them: the environment a file runs in, the service state a tool depends
on, the manifest that governs a task, or the prior decision that constrains a choice.

This is the **implicit dependency hole** failure pattern named in ADR-0001: an agent solves
the visible problem while missing the invisible context that would change the solution.

---

## Decision

Define **context bundles** — named sets of dependencies that must be retrieved alongside the
primary task context. Bundle composition is determined by task type at classification time
(same moment as delegation level classification in ADR-0003).

### The three bundle types

#### Bundle C — Code task
*Triggered by: editing files, running tests, reviewing diffs, debugging*

| Dependency | Source | Why |
|-----------|--------|-----|
| Environment config | `.env`, `docker-compose`, `flake.nix`, system env | Code that works locally may fail under different env |
| SAFE manifest for this agent | `sap/mcp_registry.json` + active manifest | Governs which tools are available |
| Service state | `fleet_status` (Postgres, Ollama, Grove, metabolic) | A test that hits a down service is not a code failure |
| Active branch + divergence | `git status`, `git log --oneline -5` | Code review without branch context misses merge risk |
| Prior decisions in KB | `willow_find(scope=kb, query=<file or module name>)` | ADRs, closed issues, session atoms that constrain this area |
| Intent kernel posture | `willow/intent/current` posture + hard_constraints | Active constraints may prohibit certain changes |

#### Bundle M — Memory task
*Triggered by: ingesting KB atoms, updating SOIL, writing handoffs, running dreams*

| Dependency | Source | Why |
|-----------|--------|-----|
| Existing atoms on this topic | `kb_search` + `mem_check` | Gate on REDUNDANT/CONTRADICTION before ingesting |
| Atom provenance | `source_type`, `valid_at`, `fork_id`, `tier` | A superseded atom cannot be ratified without context |
| Atom lifecycle | `invalid_at`, `visit_count`, `weight` | Stale atoms with low weight should be archived, not updated |
| Related edges | `pg_edge_list` for the atom | Missing edges = disconnected knowledge |
| Ledger state | `ledger_read(limit=3)` | Avoid writing an atom that contradicts a recent ledger entry |

#### Bundle E — External action
*Triggered by: L3b or L4 tasks (per ADR-0003) — GitHub PRs, messages to humans, credentials, deployments*

| Dependency | Source | Why |
|-----------|--------|-----|
| Delegation level classification | ADR-0003 ladder | Must confirm L3b/L4 ceiling is not exceeded |
| Active identity | `grove_get_identity` + `active-agent` | Sender identity must match the intended author |
| Channel/target policy | Intent kernel `hard_constraints` | "No external comms until CLA confirmed" etc. |
| Prior communications on this thread | `grove_get_history` or `gh issue view --comments` | Duplicate or contradictory messages are irreversible |
| User ratification state | Was this action explicitly authorised this session? | L4 requires explicit User permission — not inferred |

### When bundles are loaded

Bundle loading is **pre-task**, not on-demand:

```
Task received
  → classify task type (C / M / E, or combination)
  → classify delegation level (ADR-0003)
  → load bundle(s) for all matching types
  → if any bundle dependency is unavailable (service down, atom missing): surface the gap
  → proceed only when bundle is complete or gap is acknowledged by User
```

A task that starts without its bundle is not a task with incomplete context — it is a
misclassified task. The classification step is mandatory.

### Defining a dependency hole

A **dependency hole** is formally: a dependency that the agent needed to complete the task
correctly, that was available in the system, and that the agent did not retrieve before acting.

This definition has three parts:
1. *Needed* — the task outcome would have been different if retrieved
2. *Available* — it existed in Willow's stores or reachable services
3. *Not retrieved* — the agent did not pull it before the first action

Dependency holes that are discovered mid-task must be surfaced and the task must pause —
not worked around.

### Retrieved memory is P2, not a command (ADR-0004)

Bundle M retrieval returns atoms that inform the task. Per ADR-0004, retrieved memory is
precedence level P2 — it informs, it does not command. An atom that says "always do X" is
context, not an instruction. The agent applies the precedence rules to resolve any conflict
between the retrieved context and higher-P sources.

---

## Consequences

### Positive
- The acceptance condition of #267 is met: a task touching a file or tool automatically
  receives the surrounding operational context before acting
- Dependency holes become detectable — if a bundle dependency is unavailable, the gap is
  surfaced rather than silently skipped
- Bundle classification runs at the same moment as delegation level classification (ADR-0003) —
  one classification step covers both

### Negative / tradeoffs
- Bundle loading adds latency at task start — accepted, because the alternative (mid-task
  discovery of missing context) is more expensive
- Bundle C for large tasks may surface many prior KB decisions — the agent must skim, not
  deep-read, to keep boot overhead bounded

### Neutral
- Bundles are additive — a task that is both code and external (e.g., open a PR for a file
  change) loads both Bundle C and Bundle E

---

## Follow-on issues

| Issue | Title | How this ADR applies |
|-------|-------|----------------------|
| [#268](https://github.com/rudi193-cmd/willow-2.0/issues/268) | Turn Desk into action cockpit | Desk surfaces pending tasks with their bundle classification and any gap warnings |
| [#269](https://github.com/rudi193-cmd/willow-2.0/issues/269) | Add continuity adversarial tests | Tests should verify each bundle type is loaded for its task type; verify dependency holes are surfaced not silently skipped |

---

## References

- [ADR-0001](ADR-0001-single-user-operating-layer.md) — dependency hole failure pattern
- [ADR-0003](ADR-0003-delegation-authority.md) — delegation level classification (co-occurs with bundle classification)
- [ADR-0004](ADR-0004-persona-policy-precedence.md) — retrieved memory is P2
- [#267](https://github.com/rudi193-cmd/willow-2.0/issues/267)
