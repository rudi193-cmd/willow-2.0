@markdownai v1.0

# ADR-0003: Task-Level Delegation Authority

**Status:** Accepted
**Date:** 2026-06-18
**Issue:** [#265](https://github.com/rudi193-cmd/willow-2.0/issues/265)
**Depends on:** [ADR-0001](ADR-0001-single-user-operating-layer.md) · [ADR-0002](ADR-0002-intent-kernel.md)
**Supersedes:** none

---

## Context

SAFE manifests define broad tool permissions at the agent level. Fylgja pre-tool hooks block
specific dangerous patterns (Bash redirect, psql, etc.). Neither mechanism addresses the
question that matters before a tool is called: *what autonomy level does this task require,
and is that level currently permitted?*

An agent that cannot answer this question treats answering a question, editing a file, pushing
to production, and messaging a human as equivalent actions — all permitted or all blocked,
with no gradation.

---

## Decision

Define a **six-level delegation ladder** for task classification. Every task has a level; every
session has a ceiling. If a task's level exceeds the session ceiling, Willow surfaces it before
starting — not after.

### The ladder

| Level | Name | Typical actions | Default posture |
|-------|------|----------------|-----------------|
| **L0** | Read / Answer | Read files, search KB/Grove, answer questions, explain code | ✅ Always allowed |
| **L1** | Local write | Edit files, ingest KB/SOIL atoms, create git branches, write handoffs | ✅ Allowed |
| **L2** | Execute | Run Kart tasks, run tests, dispatch worker agents within scope | ⚠️ Warn if unexpected scope |
| **L3a** | Fleet communicate | Grove fleet messages, internal agent dispatch (willow → agent) | ⚠️ Warn |
| **L3b** | External communicate | GitHub PRs/comments, email drafts, messages to humans outside the fleet | ⚠️ Surface before acting |
| **L4** | Escalate | Touch credentials/secrets, spend money, push to production, external APIs with irreversible side effects | 🛑 Must ask — no exceptions |

**L3a vs L3b distinction:** Fleet-internal Grove messages are reversible and self-contained;
external communications (GitHub, email) are visible to parties outside the system and cannot
be unsent. They warrant different treatment even though both are "communicate."

### Classification rules

**Pre-task classification:** Before accepting a task, Willow determines the highest L-level
any step requires. If that level exceeds the session ceiling, surface the level and ask before
starting. A task that starts at L1 and escalates to L4 mid-execution is a classification
failure — not a runtime surprise.

**Mid-task escalation:** If a task requires a higher level than initially classified (e.g., a
file edit reveals a credential must be rotated), stop, surface the new level, and ask. Do not
proceed silently.

**Default session ceiling:** L3a. Tasks requiring L3b or L4 always require surfacing or
explicit User permission.

### Integration with the intent kernel

`willow/intent/current` may carry a `hard_constraints` entry that lowers the ceiling for a
session or arc:

```json
"hard_constraints": [
  "read-only audit session — ceiling L0",
  "no external communications until CLA confirmed"
]
```

When a ceiling constraint is present, the pre-task classification checks it first. A task
above the constrained ceiling is rejected at intake, not mid-execution.

### Integration with Fylgja hooks

Existing `pre_tool` hooks block specific patterns (Bash redirect, psql, PYTHONPATH=). This
ADR sits above those hooks:

```
Task received
  → pre-task: classify highest L-level required
  → check against session ceiling + hard_constraints
  → if exceeds ceiling: surface, ask, stop
  → if within ceiling: proceed
    → per-tool: Fylgja pre_tool hooks apply as normal
```

The two mechanisms are complementary. Fylgja hooks are pattern-level guards; delegation
levels are task-level intent guards.

### Classification guidance

| If the task involves... | Assign at least... |
|------------------------|-------------------|
| Reading, explaining, searching | L0 |
| Writing files, ingesting atoms, creating branches | L1 |
| Running scripts, tests, Kart tasks, sub-agents | L2 |
| Sending Grove fleet messages | L3a |
| Opening PRs, posting GitHub comments, drafting email | L3b |
| Rotating credentials, pushing releases, calling paid APIs | L4 |
| Any combination | Highest level in the set |

---

## Consequences

### Positive
- Agents have an explicit model for what they are and are not allowed to do at task intake —
  not discovered mid-execution
- `hard_constraints` in the intent kernel can lower the ceiling for an arc without changing
  any manifests
- L3a/L3b split captures the real distinction: fleet-internal side effects vs. external-visible
  communications

### Negative / tradeoffs
- Classification requires judgment — a task description may not fully reveal its L-level until
  decomposed. Agents must err toward the higher classification when uncertain.
- Session ceiling is L3a by default; tasks requiring L3b require surfacing even in an
  otherwise trusted session. This adds friction for routine PR work — accepted as necessary.

### Neutral
- This ADR does not prescribe how classification is implemented (rule-based, LLM inference,
  or lookup table) — that is an implementation decision

---

## Follow-on issues

| Issue | Title | How this ADR applies |
|-------|-------|----------------------|
| [#266](https://github.com/rudi193-cmd/willow-2.0/issues/266) | Define persona and policy precedence | Personas may carry ceiling overrides (e.g., Skirnir = L3b permitted by default) |
| [#267](https://github.com/rudi193-cmd/willow-2.0/issues/267) | Add dependency-aware global context retrieval | Retrieval is L0; retrieval that triggers external calls is L3b |
| [#268](https://github.com/rudi193-cmd/willow-2.0/issues/268) | Turn Desk into action cockpit | Desk surfaces pending L3b/L4 tasks for User review |
| [#269](https://github.com/rudi193-cmd/willow-2.0/issues/269) | Add continuity adversarial tests | Tests should verify L4 tasks are never executed without explicit User permission |

---

## References

- [ADR-0001: Willow as a Global Single-User Agentic Operating Layer](ADR-0001-single-user-operating-layer.md)
- [ADR-0002: The Intent Kernel](ADR-0002-intent-kernel.md)
- [#265](https://github.com/rudi193-cmd/willow-2.0/issues/265)
