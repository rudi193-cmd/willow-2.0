@markdownai v1.0

# ADR-20260703-handoff-v3-claims-record

**Status:** proposed
**Date:** 2026-07-03
**Deciders:** operator (+ agents: willow)

## Context

On 2026-07-02 a session booted with the injected line `NEXT: Push feat/civics-check`
— 16 hours after that branch had already been merged (safe-app-store PRs #22–#25).
Root cause: `cross-runtime.json` is rebuilt by a daily 06:00 timer but consumed
per-session; session anchors, the `[HANDOFF]` block, and the `NEXT` line copy it
forward and launder its age. The flat handoff's `[UNVERIFIED]` marker conflates
"no anchor recorded" with "failed verification."

The audit that followed (KB atom `42F2F794`, FRANK ledger decision `b1f7b7a4`)
found six overlapping continuity spines, of which only the v2 handoff files were
fresh and correct. The design sketch (KB atom `31F4E6F0`) scoped a v3 handoff
format whose claims are verifiable at read time, so staleness is detected
instead of inherited.

The core inversion: **v2 is a narrative that contains claims; v3 is a claims
record that carries narrative.**

A blocking culture question was put to the operator: the fate of the v2
"17 Questions" section. Decision (2026-07-03, this session): **keep the section,
drop the fixed count.** Open questions remain a first-class section — however
many are genuinely open, no padding to 17. The old Q17 ("next single bite")
becomes the typed, verifiable `next_bite` claim.

## Decision

We will define handoff format v3 as a single markdown file with three layers,
validated by `docs/adrs/handoff-v3.schema.json`.

### Layer 1 — Machine skeleton (code-written, always present)

Written by the Stop hook (or recovery sweep) with no model involvement:
session id, agent, project, runtime, branches touched, commit SHAs, PR numbers
and states (from `gh`), flags delta, Kart task ids, files changed. A crashed
session still yields a valid, bootable handoff.

### Layer 2 — Typed claims (structured, verified at read time)

Open threads and `next_bite` are claims, not prose bullets:

```
{id, text, kind, verify: {type, subject, expect}, opened, carried_from}
```

Claim kinds in v1: `branch_pushed`, `pr_state`, `file_exists`, `flag_open`,
`sha_current`, `prose` (= explicitly unverifiable — an honesty marker, not a
failure). The boot digest runs the verifier per claim kind **at read time** and
stamps `verified | failed | unverifiable` + `checked_at`. Verdicts are digest
output — they are never written back into the handoff file. Claims carry
forward with `carried_from`, so age is visible and content is never re-copied.

### Layer 3 — Narrative (model-written, tier-scaled)

Frontier models write rich prose; an 8B fills template fields; an absent model
leaves them empty and the file is still bootable. Sections:

- `## What I Now Understand` — prose summary
- `## What We Agreed On` — decisions carried forward
- `## Open Questions` — replaces "17 Questions": as many as are genuinely
  open, no fixed count, no padding; the next action is NOT here (it is the
  `next_bite` claim)
- `## Agent Notes for Human`
- `## Human Notes to Agent` — stays live-read at next boot

### Format rules

- **Storage:** one fenced JSON machine block per file, schema-validated.
  JSON is for scripts.
- **Injection:** the boot digest renders flat, terse English `key: value`
  lines into model context — never raw JSON.
- **No invented shorthand:** universal symbols only (`✓`, `→`, `#`, ISO dates).
- **Models never author JSON:** fields arrive via tool call; code serializes.
  Grammar-constrained decoding (Ollama) is the floor-tier backstop.
- **No b17:** claim ids are plain; provenance is `session_id` + `written_at` +
  FRANK ledger; attestation, if ever needed, is the existing PGP gate path.

### Migration

`handoff_latest` reads v2 and v3 side by side, keyed on `format:` frontmatter.
Retired once the boot digest lands: flat handoff, session-anchor copies,
`cross-runtime.json` (the digest merges runtimes at read time instead).

## Consequences

### Positive

- Stale claims are detected at read time, not inherited — the civics-check
  incident class is structurally closed.
- A crashed or model-less session still produces a valid handoff (skeleton).
- One continuity spine instead of six; claim age is visible via `carried_from`.
- Floor-tier (7–8B) sessions produce bootable handoffs without prose quality
  being load-bearing.

### Negative / tradeoffs

- Read-time verification costs boot latency (gh/git calls per claim); needs a
  budget and a cache window.
- Two formats coexist during migration; `handoff_rebuild` must handle both.
- Claim typing adds authoring friction for frontier sessions that previously
  free-wrote bullets.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Keep 17 Questions as frontier-tier ritual | Preserves the padding ceremony that produces filler questions; the count was the only dishonest part |
| Retire open questions entirely into the machine block | Loses genuine unresolved-question signal that doesn't reduce to a verifiable claim |
| Verify at write time (Stop hook stamps verdicts) | Verdicts go stale exactly like the NEXT line did; verification must happen when the claim is consumed |
| Patch cross-runtime.json refresh cadence | Treats the symptom; anchor copies would still launder age |

## Receipts

| Type | Ref |
|------|-----|
| KB | atom `42F2F794` (audit) · atom `31F4E6F0` (v3 sketch) |
| Ledger | FRANK `b1f7b7a4-3979-49c3-9151-786baafe6344` (decision) |
| Git | `willow-2.0` — PR introducing this ADR |

## Implementation notes

- Schema: [`handoff-v3.schema.json`](handoff-v3.schema.json) (this PR — the
  contract only, no code).
- Not in this PR (blocked on operator "build it"): Stop-hook skeleton writer,
  claim verifier in the boot digest, `handoff_latest` v3 reader, retirement of
  the cross-runtime timer.
- Verification command (once built): boot digest output shows per-claim
  `verified/failed/unverifiable` stamps with `checked_at`.
- WCE boot scenarios (the stale-NEXT case is test case #1) track whether tiers
  consume the digest correctly.

## Supersedes

- None (v2 remains valid during migration; authoring guidance in
  `willow/fylgja/skills/boot.md` to be updated when the digest ships).
