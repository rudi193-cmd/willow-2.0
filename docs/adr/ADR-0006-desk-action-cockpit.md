@markdownai v1.0

# ADR-0006: Desk as Action Cockpit with Interruption Rules

**Status:** Accepted
**Date:** 2026-06-18
**Issue:** [#268](https://github.com/rudi193-cmd/willow-2.0/issues/268)
**Depends on:** [ADR-0001](ADR-0001-single-user-operating-layer.md) · [ADR-0002](ADR-0002-intent-kernel.md) · [ADR-0003](ADR-0003-delegation-authority.md) · [ADR-0005](ADR-0005-dependency-aware-retrieval.md)
**Supersedes:** none

---

## Context

Desk is becoming a cockpit but remains mostly read-oriented. A global single-user agentic
operating system needs a surface that reduces cognitive load — not one that adds another inbox
to monitor. The risk is that Desk becomes a dashboard the User must poll rather than a system
that actively manages attention.

---

## Decision

### Desk answers four questions

At any moment, Desk must be able to answer:

1. **What needs the User now?** — L3b/L4 tasks pending approval, decisions past deadline,
   commitments about to age out
2. **What can wait?** — open threads with no urgency signal, proposals in `proposed_diffs`
   not yet ratified
3. **What should be hidden?** — resolved items, deferred work, ignore-today items
4. **What may Willow do without interrupting?** — L0–L2 tasks within the current session
   ceiling, L3a fleet messages

### Action surface

Desk exposes seven actions on any surfaced item:

| Action | Effect | Min delegation level |
|--------|--------|---------------------|
| **Acknowledge** | Mark seen; removes from "needs now" | L0 (User) |
| **Defer** | Move to "can wait" with optional date | L0 (User) |
| **Promote** | Elevate to "needs now" | L0 (User) |
| **Archive** | Remove from active surface; KB atom written | L1 |
| **Dispatch** | Hand to Willow for execution | L2 |
| **Verify** | Request Willow confirms current state | L0 |
| **Resume** | Reactivate a deferred or paused thread | L0 (User) |

Dispatch and Archive are the only Desk actions that change system state. Both require at
least L1 (local write) and are subject to the session ceiling (ADR-0003).

### Operational health panel

Desk surfaces a personal-operational health view alongside task triage:

| Signal | Source | Threshold |
|--------|--------|-----------|
| **Commitments aging** | `near_term` in intent kernel | Warn at 48h before deadline |
| **Decisions waiting** | `proposed_diffs` in intent kernel | Surface if > 3 unratified |
| **Overload signal** | Open threads > 12 + no archive in 48h | Surface "triage needed" |
| **Ignore-today** | User-marked items | Hidden from main view; accessible on demand |

The health panel is read-only. It surfaces signals; it does not take action.

### Interruption levels

Willow may interrupt the User at four levels. The level is determined by the task's delegation
classification and the urgency of the item:

| Level | When Willow uses it | Delivery |
|-------|--------------------|----|
| **Silent** | L0–L1 tasks completing normally | No notification; visible in Desk on next open |
| **Batch** | L2 task results, L3a fleet messages | Queued; surfaced at next Desk open or session start |
| **Notify** | L3b actions ready for approval, decisions aging | Grove message to User channel; appears in boot report |
| **Interrupt** | L4 tasks requiring approval, P7/P8 conflicts | Blocks current task; requires User response before proceeding |

**Interrupt is the only level that blocks task execution.** Silent, Batch, and Notify are
asynchronous — Willow continues working within its permitted ceiling while waiting.

### External communication boundaries

Willow may initiate external communications (L3b) only through defined channels and only
when explicitly permitted:

| Channel | Permitted by default | Requires |
|---------|---------------------|---------|
| Grove (fleet-internal) | Yes — L3a | Session ceiling ≥ L3a |
| GitHub PR / comment | No — L3b | Notify-level approval this session |
| Discord | No — L3b | Notify-level approval this session |
| Email (draft) | No — L3b | Notify-level approval this session |
| Calendar | No — L4 | Interrupt-level explicit approval |

Channels not listed above are L4 by default.

### Desk and the intent kernel (ADR-0002)

Desk reads `willow/intent/current` as its cockpit headline:
- `posture` → one-line status at top of Desk
- `active_projects` → primary task lanes
- `proposed_diffs` → pending ratification items
- `hard_constraints` → shown as active guardrails

Desk does not write the intent kernel directly. Desk actions (Defer, Archive) may produce
`proposed_diffs` entries that the User ratifies at the next session.

---

## Consequences

### Positive
- Desk answers the four questions explicitly — not a passive dashboard
- Interruption levels give Willow a disciplined way to escalate without always blocking
- External communication boundaries are enumerated — no implicit "if it seems OK, send it"

### Negative / tradeoffs
- Interrupt-level blocking is strict — L4 tasks that arrive mid-session will pause execution.
  This is intentional but requires Willow to classify L4 tasks at intake, not mid-execution.
- Notify-level is asynchronous — a L3b action may sit pending for a session if the User is
  away. This is correct: Willow waits rather than proceeds.

### Neutral
- Desk implementation (TUI widget, Grove Desk channel, web surface) is not prescribed here —
  this ADR defines what Desk must answer and what it must surface, not how it renders

---

## Follow-on issues

| Issue | Title | How this ADR applies |
|-------|-------|----------------------|
| [#269](https://github.com/rudi193-cmd/willow-2.0/issues/269) | Add continuity adversarial tests | Tests should verify interrupt-level fires for L4; verify Desk "can wait" does not include items needing approval |

---

## References

- [ADR-0001](ADR-0001-single-user-operating-layer.md) · [ADR-0002](ADR-0002-intent-kernel.md) · [ADR-0003](ADR-0003-delegation-authority.md) · [ADR-0005](ADR-0005-dependency-aware-retrieval.md)
- [#268](https://github.com/rudi193-cmd/willow-2.0/issues/268)
