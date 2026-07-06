@markdownai v1.0
<!--
AGENT INSTRUCTIONS — see docs/templates/ADR.template.md
Read with mai_read_file; write with mai_write_file; do not use IDE Read/Write on filled file.
-->

# ADR-20260705-corpus-seed-drift

**b17:** ADRCS1 · ΔΣ=42

**Status:** proposed
**Date:** 2026-07-05
**Deciders:** Sean (+ agents: willow, persona Hanuman)

## Context

While auditing "is everything in the local flat memory files reflected in
the correct SOIL tables" (2026-07-05 night session), the assumption behind
one boot-digest claim — *"corpus corrections seeded from memory feedback
files"* — turned out to be false for the live system.

What the audit found, directly queried, not inferred:

- **57 files** live in the Claude Code auto-memory directory
  (`~/.claude/projects/<slug>/memory/*.md`): 25 `type: feedback`,
  31 `type: project`, 1 `type: reference`, 0 `type: user`.
- **`corpus/corrections`** (SOIL, 193 records): 178 tagged
  `source: prompt_submit_hook` (raw, unfiltered, real-time captures of
  anything the hook flags as correction-like — e.g. *"you should have just
  rerun the lint test."*), plus **15 records tagged
  `source: feedback_<name>.md`** (e.g. `feedback_use_kart_for_bash.md`,
  `feedback_no_direct_db.md`, `feedback_boot_sequence_every_turn.md`).
- **None of those 15 filenames exist anywhere in the repo.** `grep -rl` across
  the whole tree (excluding worktrees) found them only as literal strings in
  `willow/fylgja/events/session_start.py` and as a fixture in
  `tests/test_corrections_dedupe.py` — never as real files. They are a
  hardcoded bootstrap seed, not a live read of any memory directory.
- **`corpus/preferences`** (SOIL, 58 records): every single record —
  checked exhaustively, not sampled — is `source: prompt_submit_hook`.
  Zero come from any memory file.
- **`scripts/promote_corrections.py`** (the one real promotion path off
  `corpus/corrections`) groups recurring raw hook captures and calls
  `kb_ingest` straight into the **KB** (`knowledge` table, tier `observed`).
  It never reads, writes, or references the Claude Code memory directory in
  either direction.

Net: the memory directory (this agent's own curated distillations — the
"auto memory" system described in the assistant's own system prompt) and
SOIL's `corpus/corrections` + `corpus/preferences` (raw fleet-wide hook
telemetry) are **two parallel, non-communicating systems**. The digest
sentence that says otherwise is describing a mechanism that no longer
exists — or never existed as literally as it reads.

## Decision

Not yet decided — this ADR is filed at `proposed` to put the finding on
record and force a real choice among the options below, rather than let
the misleading digest line stand unexamined.

Two directions, not mutually exclusive:

1. **Wire it for real.** Change `session_start.py`'s seed step to glob the
   live memory directory (`willow.fylgja.claude_projects`-style path
   resolution already exists for session JSONLs — same pattern, new
   target) for `type: feedback` / `type: preference` frontmatter, and seed
   `corpus/corrections` / `corpus/preferences` from what's actually on disk
   instead of the hardcoded 15-name list.
2. **Stop claiming it.** If curated memory files are meant to stay a
   separate, agent-owned layer (they are richer than raw corrections —
   they carry Why/How-to-apply structure the hook captures don't), drop
   the "seeded from memory feedback files" line from the digest/boot
   report and document the memory directory as its own, sixth persistence
   layer alongside the five in `persistent-memory-stack.md`.

## Consequences

### Positive

- Whichever direction is chosen, the boot report stops asserting a sync
  that doesn't happen — corrections/preferences claims become trustworthy
  again.
- If wired for real: 25 curated, high-signal feedback files start feeding
  the same promotion pipeline as raw hook noise, at higher quality than
  the 178 unfiltered captures currently competing for norn-pass attention.
- If documented as separate: `persistent-memory-stack.md` becomes accurate
  again — right now it lists five layers and is silent about a sixth that
  demonstrably exists and is actively maintained every session.

### Negative / tradeoffs

- Wiring it for real risks duplicate/noisy promotion if a feedback file's
  content already exists as a raw hook capture — would need de-dup by
  normalized content (the same `_normalize()` used in
  `promote_corrections.py`) before ingest.
- The 15 hardcoded `feedback_*.md` seed entries in `session_start.py` may
  be intentional bootstrap/demo fixtures rather than a broken feature —
  worth confirming with whoever added them before deleting, in case a test
  or onboarding path depends on their presence.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Leave as-is, no ADR | The false digest claim keeps costing trust on every boot report; better to record the gap once than re-discover it per session. |
| Delete the 15 hardcoded seed entries with no replacement | Removes stale data but doesn't answer whether curated memory *should* feed SOIL — punts the real decision. |

## Receipts

| Type | Ref |
|------|-----|
| Grove | `#architecture` message id `254` |
| Session | willow 2026-07-05 night session (persona Hanuman) — direct `soil_list`/`soil_search` queries against `corpus/corrections` and `corpus/preferences`, full (not sampled) enumeration of both collections |
| Code | `willow/fylgja/events/session_start.py` (hardcoded 15-name seed list), `tests/test_corrections_dedupe.py` (fixture referencing same names), `scripts/promote_corrections.py` (confirms promotion target is KB, not memory dir) |

## Implementation notes

- Files to touch if Decision 1 is chosen: `willow/fylgja/events/session_start.py`
  (seed step), possibly a new `willow/fylgja/claude_memory.py` resolver
  mirroring `claude_projects.py`'s multi-slug-variant scan.
- Files to touch if Decision 2 is chosen: `willow/fylgja/skills/persistent-memory-stack.md`
  (add the layer), the boot digest section that renders the false claim
  (`willow/fylgja/config/digest_sections.json` or wherever `[DIGEST]`
  corrections/preferences lines are generated).
- Verification command once implemented: re-run the same audit —
  `soil_list(corpus/corrections)` / `soil_list(corpus/preferences)`,
  confirm sources now include real memory filenames (Decision 1) or that
  the digest no longer claims memory-file seeding (Decision 2).

## Supersedes

- None

---

*b17: ADR · ΔΣ=42*
