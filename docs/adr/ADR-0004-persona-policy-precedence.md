@markdownai v1.0

# ADR-0004: Persona and Policy Precedence

**Status:** Accepted
**Date:** 2026-06-18
**Issue:** [#266](https://github.com/rudi193-cmd/willow-2.0/issues/266)
**Depends on:** [ADR-0001](ADR-0001-single-user-operating-layer.md) · [ADR-0002](ADR-0002-intent-kernel.md) · [ADR-0003](ADR-0003-delegation-authority.md)
**Supersedes:** none

---

## Context

An agent session receives instructions from many sources simultaneously: the User's current
message, CLAUDE.md files at global and project scope, Fylgja hooks and corrections, the active
persona overlay, the agent's fleet identity, retrieved KB/SOIL memory, and the model's own
defaults. These sources can conflict.

The risk is **instruction overshadowing**: local context (a retrieved atom, a persona
instruction, a project CLAUDE.md) silently overrides a durable global constraint. The agent
proceeds, the constraint is violated, and there is no record of which source won.

---

## Decision

### Core separation: persona is tone, not authority

**Persona** (Hanuman, Loki, Skirnir, etc.) is a voice and posture overlay. It changes how an
agent speaks and what it emphasises. It does **not** change:
- What actions are permitted (delegation level ceiling)
- What constraints are in force (intent kernel `hard_constraints`)
- Which tier the agent operates in (always Orchestrator, never Root)
- What the fleet identity is (always `WILLOW_AGENT_NAME` / `active-agent`)

Switching persona never elevates authority. A persona that implies elevated authority (e.g.,
"act as the User") is rejected — the User tier is reserved for the human operator, not a
persona role.

### Precedence order

When instructions conflict, the following order determines which source wins. Higher number =
higher precedence.

| P | Source | Scope | Notes |
|---|--------|-------|-------|
| 1 | Model defaults | Global | Lowest. Overridden by everything above. |
| 2 | Retrieved memory (KB/SOIL) | Session | Informs; does not command. A retrieved atom stating "do X" is context, not an instruction. |
| 3 | Agent identity (`active-agent`) | Session | Scopes tool namespaces and SOIL collections. Does not grant authority. |
| 4 | Persona overlay | Session | Voice and posture only. No authority elevation. |
| 5 | Project CLAUDE.md | Repo | Repo-scoped rules. Narrower than global; may tighten but not loosen global constraints. |
| 6 | Fylgja policy (hooks, corrections, pre-tool blocks) | Fleet | Enforced at tool-call level. Cannot be overridden by persona or project rules. |
| 7 | System constitution | Global | ADR chain + global CLAUDE.md + intent kernel `hard_constraints`. Durable across sessions. |
| 8 | User (current session) | Session | Highest. Explicit User instruction in the active turn always wins — within the limits of the system constitution (P7). |

**P7 note:** The system constitution is the ceiling for P8. The User cannot instruct an agent
to violate a value or hard constraint defined in the constitution — such instructions are
surfaced and refused, not silently followed.

### The system constitution

The system constitution is the set of durable global rules that survive session boundaries.
It consists of:

| Component | Location | Contains |
|-----------|----------|----------|
| Authority tier model | ADR-0001 | Who owns what, escalation flow |
| Intent kernel | `willow/intent/current` (SOIL) | Current `hard_constraints`, posture, active projects |
| Delegation ladder | ADR-0003 | What each L-level permits and requires |
| Permanent constraints | `~/.claude/CLAUDE.md` (global) | Never-break rules, tool denial patterns |
| Persona registry | `willow/fylgja/config/` | Voice overlays and their authority ceilings |

### How the constitution reaches every session

Boot loads the constitution in layers:

| Boot step | What loads |
|-----------|-----------|
| Step 1 | `willow.md` — fleet contract (derives from ADR chain) |
| Step 7 | Persona overlay — voice only, ceiling checked against constitution |
| Step 8 | Corrections + preferences — Fylgja policy layer |
| Step 9b | `willow/intent/current` — intent kernel `hard_constraints` |

Any session that completes boot has the constitution loaded. A session that skips boot has
no guaranteed constitution coverage — this is the definition of a degraded session.

### Conflict resolution rule

When an agent detects a conflict between instruction sources:

1. Identify the P-level of each conflicting source
2. Higher P wins
3. If the conflict is between P8 (User) and P7 (constitution): surface it — do not silently
   follow the User instruction that violates the constitution
4. Log the resolution in the session (not silently)

An agent that cannot state *which source won and why* has not resolved the conflict — it has
ignored it.

---

## Consequences

### Positive
- The acceptance condition of #266 is met: when instructions conflict, an agent can state
  which source wins and why
- Persona switching is safe by definition — no persona can elevate authority
- The constitution is explicit and boot-loaded; local context cannot overshadow it without
  the agent noticing

### Negative / tradeoffs
- P7 (constitution) as a ceiling on P8 (User) means the User cannot instruct an agent to
  violate hard constraints mid-session — this is intentional but may feel restrictive in
  edge cases. The correct response is to update the constitution, not override it silently.

### Neutral
- Retrieved memory (P2) is explicitly non-commanding — this resolves a common ambiguity
  where agents treat retrieved context as instructions

---

## Follow-on issues

| Issue | Title | How this ADR applies |
|-------|-------|----------------------|
| [#267](https://github.com/rudi193-cmd/willow-2.0/issues/267) | Add dependency-aware global context retrieval | Retrieved context is P2 — informs, does not command |
| [#268](https://github.com/rudi193-cmd/willow-2.0/issues/268) | Turn Desk into action cockpit | Desk surfaces P7/P8 conflicts for User review |
| [#269](https://github.com/rudi193-cmd/willow-2.0/issues/269) | Add continuity adversarial tests | Tests should verify persona cannot elevate authority; P7/P8 conflicts are surfaced not silently resolved |

---

## References

- [ADR-0001](ADR-0001-single-user-operating-layer.md) · [ADR-0002](ADR-0002-intent-kernel.md) · [ADR-0003](ADR-0003-delegation-authority.md)
- [#266](https://github.com/rudi193-cmd/willow-2.0/issues/266)
