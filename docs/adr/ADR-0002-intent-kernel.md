@markdownai v1.0

# ADR-0002: The Intent Kernel — `willow/intent/current`

**Status:** Accepted
**Date:** 2026-06-18
**Issue:** [#263](https://github.com/rudi193-cmd/willow-2.0/issues/263)
**Depends on:** [ADR-0001](ADR-0001-single-user-operating-layer.md) (authority tier model)
**Supersedes:** none

---

## Context

Willow has handoffs, KB, Grove, SOIL, dreams, ledger, personas, and a session index. None of
these is a single canonical object that answers: *what is the User currently trying to build,
what matters now, what is paused, and what must not be violated?*

A new agent session can retrieve facts but still miss the operating posture. The boot sequence
reads stack snapshot + handoff + corrections — but these are session-scoped or backward-looking.
There is no forward-looking, User-ratified, cross-session intent record.

---

## Decision

Define a **single SOIL record** at `willow/intent/current` as the intent kernel. It is the
one compact object a new session reads to understand the current global operating posture
before acting.

### Schema

```json
{
  "posture": "one-line summary — e.g. 'shipping mex-mcp, auditing arch issues'",
  "active_projects": [
    {
      "name": "string",
      "goal": "string",
      "phase": "string",
      "fork_id": "string or null"
    }
  ],
  "paused_work": [
    {
      "name": "string",
      "reason": "string",
      "resume_condition": "string or null"
    }
  ],
  "near_term": [
    {
      "commitment": "string",
      "deadline": "ISO 8601 date or null",
      "dependency": "string or null"
    }
  ],
  "hard_constraints": [
    "string — arc-scoped rules that must not be violated this period"
  ],
  "validation_gates": [
    "string — what must pass before the current arc closes"
  ],
  "proposed_diffs": [
    {
      "field": "string",
      "proposed_value": "any",
      "proposed_by": "agent id",
      "proposed_at": "ISO 8601",
      "rationale": "string"
    }
  ],
  "updated_at": "ISO 8601 — advances only on User ratification",
  "ratified_by": "user"
}
```

### Storage

The intent kernel lives in **SOIL** at `willow/intent/current`.

- SOIL provides update/audit trail — every write is versioned
- The record is small enough to load in one call
- Agents cannot silently overwrite it — `soil_update` is an explicit, logged operation
- After each User ratification, a KB atom is ingested (`category: intent_kernel`) for
  permanent audit trail

### Authority (per ADR-0001)

| Action | Who can do it | Notes |
|--------|--------------|-------|
| Read | Any agent | Always permitted at boot |
| Write `proposed_diffs` | Orchestrator + Workers | Agents append proposals; they do not overwrite fields |
| Write any field directly | User (Root tier only) | Via `willow_remember` or direct SOIL write |
| Advance `updated_at` | User ratification only | Ratification = User confirms a proposed diff or writes directly |
| Clear `proposed_diffs` | Orchestrator at boot | After User reviews and ratifies/rejects each proposal |

**Hard constraint**: `hard_constraints` lives here (arc-scoped, dynamic), not in CLAUDE.md.
CLAUDE.md holds permanent never-break rules. SOIL holds arc-scoped constraints that may change
between projects or phases.

### Refresh rules

| Trigger | Action |
|---------|--------|
| Session start (boot step 9b) | Read `willow/intent/current` — load alongside stack snapshot; surface `posture` + `proposed_diffs` count in boot report |
| Session close (shutdown) | Orchestrator appends any new `proposed_diffs` surfaced this session |
| Dream synthesis | May propose additions to `paused_work` or `active_projects` via `proposed_diffs` |
| User explicit update | Writes any field directly; advances `updated_at`; clears relevant `proposed_diffs` |
| Arc close | User updates `active_projects` / `paused_work` / `validation_gates` to reflect the new posture |

### Boot integration

Boot step 9 (stack snapshot) expands to step 9b:

```
soil_get("willow/intent/current")
→ surface posture one-liner in boot report
→ if proposed_diffs > 0: surface count + first item for User awareness
```

This is one extra SOIL call. The record is small; it does not bloat boot.

---

## Consequences

### Positive
- Any agent session, on any tool (Claude Code, Cursor, Codex), can read one record and
  understand the current operating posture — the acceptance condition of #263 is met
- Proposed diffs give agents a write path without granting them root authority
- `updated_at` advancing only on ratification makes intent drift visible: a stale
  `updated_at` signals the kernel needs a User review

### Negative / tradeoffs
- Requires the User to keep the kernel up to date — a stale kernel misleads agents as much
  as no kernel does; the `updated_at` field is the staleness signal
- Agents must not treat `proposed_diffs` as ratified — they are proposals until `updated_at`
  advances

### Neutral
- CLAUDE.md permanent constraints are not duplicated here — the two records are complementary,
  not redundant

---

## Follow-on issues

| Issue | Title | How this ADR unblocks it |
|-------|-------|--------------------------|
| [#265](https://github.com/rudi193-cmd/willow-2.0/issues/265) | Define task-level delegation authority | Delegation scope is bounded by `hard_constraints` + `validation_gates` in the kernel |
| [#266](https://github.com/rudi193-cmd/willow-2.0/issues/266) | Define persona and policy precedence | Persona selection is root-tier; kernel can carry the active persona constraint |
| [#267](https://github.com/rudi193-cmd/willow-2.0/issues/267) | Add dependency-aware global context retrieval | `active_projects` + `near_term` are the dependency anchors for retrieval ranking |
| [#268](https://github.com/rudi193-cmd/willow-2.0/issues/268) | Turn Desk into action cockpit | Desk reads the kernel to surface the current posture as the cockpit headline |
| [#269](https://github.com/rudi193-cmd/willow-2.0/issues/269) | Add continuity adversarial tests | Tests should verify kernel is loaded at boot and that proposed_diffs are not treated as ratified |

---

## References

- [ADR-0001: Willow as a Global Single-User Agentic Operating Layer](ADR-0001-single-user-operating-layer.md)
- [#263](https://github.com/rudi193-cmd/willow-2.0/issues/263)
- KB atom `session20260608_sociotechnical_analysis`
