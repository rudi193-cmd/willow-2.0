@markdownai v1.0

# ADR-0001: Willow as a Global Single-User Agentic Operating Layer

**Status:** Accepted
**Date:** 2026-06-18
**Issue:** [#262](https://github.com/rudi193-cmd/willow-2.0/issues/262)
**Supersedes:** none
**Superseded by:** none

---

## Context

Willow has sufficient capability. The failure mode is not missing tools — it is losing the
User's intent across tools, contexts, sessions, and semi-autonomous agents.

The June 2026 KB/MCP audit confirmed that tool overload and ambiguous routing are the primary
risks, not capability gaps. The sociotechnical analysis identified three recurring failure
patterns:

- **Temporal collapse** — an agent loses track of when something happened or was decided
- **Implicit dependency holes** — an agent assumes context that was never passed to it
- **Instruction overshadowing** — later instructions override earlier intent without flagging
  the conflict

These three patterns all have the same root cause: no shared, durable model of who holds
what authority and how state persists across tier boundaries.

This ADR establishes that model as the constitutional layer for all follow-on design decisions
(#263–#269).

---

## Decision

Willow is defined as a **global single-user agentic operating layer**:

> One human root of authority. Many agents, tools, and apps. One continuity problem.

### Authority tiers

| Tier | Holder | Owns | Does not own |
|------|--------|------|--------------|
| **Root** | User | Intent kernel · constraint authoring · ratified decisions · persona selection · final escalation target | Day-to-day routing · task execution · session-level state |
| **Orchestrator** | Willow | Continuity across sessions · fleet coordination · KB/SOIL · memory lanes · routing · boot/shutdown lifecycle | Autonomous decision-making without a root signal · user-level intent |
| **Worker** | Agents, inference engines, Kart tasks | Task-scoped execution within a single session or worktree | Persistent authority · cross-session state · escalation without surfacing |

### Authority flow

```
User (Root)
  │  ratifies · constrains · owns intent
  ▼
Willow (Orchestrator)
  │  routes · persists · coordinates · escalates unresolved decisions upward
  ▼
Workers (Agents / Kart / Sub-agents)
     execute · surface blockers · return results · do not retain authority
```

**Authority flows downward. Escalation flows upward.**

A worker that encounters a decision above its authority tier must surface it to the
orchestrator, which surfaces it to the User — not resolve it autonomously.

### How this addresses the three failure patterns

| Pattern | Resolution |
|---------|-----------|
| Temporal collapse | Willow (orchestrator) owns session continuity. Workers inherit context via handoffs and the boot gate — they do not reconstruct it from scratch. |
| Dependency holes | The orchestrator tier explicitly holds cross-session state (KB, SOIL, handoffs). Workers must not assume context they were not given. |
| Instruction overshadowing | Root intent (CLAUDE.md, ratified decisions, corrections corpus) always wins over worker-level inference. The orchestrator surfaces conflicts rather than silently resolving them. |

### What belongs where

| Layer | Contains |
|-------|----------|
| **Constitution** (this ADR + #263–#269) | Authority tiers · escalation rules · what each tier owns · adversarial tests |
| **Contract** (`willow.md`) | Operational rules derived from the constitution — how the tiers operate in practice |
| **Implementation docs** | How Kart enforces worker scope · how KB stores root intent · how handoffs carry orchestrator state · how Fylgja hooks apply the rules |

The constitution defines *what*. The contract defines *how*. Implementation docs define *where in the code*.

---

## Consequences

### Positive
- All follow-on architecture decisions (#263–#269) have a shared reference for authority
  boundary questions — no re-litigation of first principles per issue
- Escalation paths are explicit: workers surface, orchestrator routes, root ratifies
- The three sociotechnical failure patterns have a single architectural answer

### Negative / tradeoffs
- Willow as orchestrator must maintain reliable state across session boundaries — the
  handoff/boot/shutdown pipeline is load-bearing, not optional
- Workers are intentionally scope-limited; this means the orchestrator bears more
  coordination cost than a flat architecture would

### Neutral
- This ADR does not prescribe implementation mechanisms — those belong in the follow-on issues
- Multi-user extension (#273–#281) will add a second root-level tier (shared workspace);
  this ADR scopes to single-user only and is not invalidated by that extension

---

## Follow-on issues

These issues are gated on this ADR. The authority tier model must be stable before each
can be decided.

| Issue | Title | Tier addressed |
|-------|-------|---------------|
| [#263](https://github.com/rudi193-cmd/willow-2.0/issues/263) | Design the current intent kernel | Root |
| [#265](https://github.com/rudi193-cmd/willow-2.0/issues/265) | Define task-level delegation authority | Worker boundary |
| [#266](https://github.com/rudi193-cmd/willow-2.0/issues/266) | Define persona and policy precedence | Root → Orchestrator |
| [#267](https://github.com/rudi193-cmd/willow-2.0/issues/267) | Add dependency-aware global context retrieval | Orchestrator |
| [#268](https://github.com/rudi193-cmd/willow-2.0/issues/268) | Turn Desk into action cockpit with interruption rules | Root/Orchestrator interface |
| [#269](https://github.com/rudi193-cmd/willow-2.0/issues/269) | Add continuity adversarial tests | All tiers |

---

## References

- `docs/audits/AI_DEVELOPMENT_SOCIOTECHNICAL_ANALYSIS_2026-06-08.md`
- `docs/audits/WILLOW_KB_MCP_AUDIT_2026-06-08.md`
- KB atom `session20260608_sociotechnical_analysis`
