@markdownai v1.0

<!--
AGENT INSTRUCTIONS
- Use for: Grove quorum posts, ratified decisions, policy gates, overseer-visible commitments.
- Save as: post to Grove channel via grove_send; optionally mirror to willow-2.0/docs/decisions/YYYY-MM-DD-<slug>.md
- Required: decision statement, ruled-out options, quorum state, receipts.
- Pair with ADR when the decision is durable architecture/policy.
- MarkdownAI: keep @markdownai v1.0 line 1. Read with mai_read_file; write with mai_write_file.
-->

# Grove Decision — <title>

**b17:** GROVED · ΔΣ=42

**Date:** YYYY-MM-DD  
**Agent:** <agent_id>  
**Channel:** `#<channel>`  
**Quorum:** pending | ratified | rejected | deferred

## Decision

We will …

## Context

Why now? What problem or gate triggered this post?

## Ruled Out

| Option | Why not |
|--------|---------|
| | |

## Quorum

| Participant | Role | Position |
|-------------|------|----------|
| USER | decider | |
| <agent_id> | proposer | |

## Implementation Bite

- Next single action:
- Verification:

## Receipts

| Type | Ref |
|------|-----|
| Grove post | message id `…` |
| Seed atom | KB id `…` |
| ADR | `docs/adrs/ADR-…` |
| PR | `#…` |

## Grove Post Body (copy/paste)

```text
[DECISION] <one-line title>

Decision: …
Ruled out: …
Next bite: …
Receipts: Grove <id>, KB <id>, PR <#>
```

---

*b17: GROVED · ΔΣ=42*
