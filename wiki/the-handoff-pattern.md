# The Handoff Pattern

*Maintained synthesis — last updated 2026-05-04.*

---

## Why Handoffs Exist

Sessions end. Context windows compress. Agents restart. Without a deliberate handoff, the next session starts blind — reconstructing the system from scratch, re-deriving what was already built, making decisions that were already made.

The handoff is the Viking navigator's encoded route. Not coordinates — a story that lasts. The session itself evaporates. The handoff doesn't.

---

## Current Format (v2)

Handoff files live in `~/Ashokoa/agents/hanuman/index/haumana_handoffs/` (Hanuman) and on the Desktop for Heimdallr sessions.

The four-section structure:

### 1. What I Now Understand (2-3 sentences)
Architectural truth — not a task list, not a status report. The thing that changed in this session that changes how the next session should think. Example: "Willow is no longer a concept — she is a running Grove participant."

### 2. What Was Done (high-level)
Bullet list. Commits, KB atoms ingested, major builds shipped. Each item should be specific enough to act on. Not "improved persona" — "persona hardened to positive enumeration: 'You have access to exactly one thing — the message you just received.'"

### 3. 17 Questions (sequential, bite-sized)
Questions the next session needs to answer, from most critical to least. Q17 is always: "What is the next single bite?" The 17-question format forces prioritization. If you can't get to 17, you haven't thought hard enough about what's actually pending.

### 4. Risks / Open Gates
What could break, what's untested, what's waiting on an external event. Not a worry list — a specific, actionable risk register.

---

## The ISS Problem

ISS crew handovers require 14 days of overlap. Willow handoffs are monologues — one agent writes a document and hopes the next agent reads it. There's no dialogue, no confirmation, no overlap period.

This is a structural gap. The handoff document is better than nothing, but it's not a real transition. The fleet doesn't do overlap — each session is a cold crew transfer with one written note.

**Partial fix:** The wiki pages in this directory. A session that reads `what-is-willow.md` and `the-fleet.md` before diving into the handoff has a 2-minute orientation that would otherwise take 20 minutes to reconstruct.

---

## What Survives Compression

Context window compression keeps summaries, discards raw exchanges. What reliably survives:
- Explicit ratifications ("Sean said yes to X")
- KB atom IDs (searchable, persist across sessions)
- File paths and commit SHAs
- Grove message IDs (can be pulled with `grove_get_history`)
- The handoff document itself (if written and stored before compression)

What doesn't survive:
- The reasoning behind decisions (write it in the KB atom or handoff)
- Implicit agreements (if it wasn't written down, it didn't happen)
- FRANK's notes (the frank_ledger write path isn't built yet — notes evaporate with the session)

---

## The b17 Identifier

Handoffs and key documents include a `b17:` identifier — a Base 17 short hash. This is a uniqueness check and cross-reference system. If you see `b17: ED4EB` in grove_serve.py, that matches the handoff that documents it.

Format: `b17: XXXXX  ΔΣ=42`

The `ΔΣ=42` at the end of CLAUDE.md and handoffs is a signal — "this was written with the full system in mind."

---

## The Handoff DB

`build_handoff_db.py` (canonical at `sap/tools/build_handoff_db.py`) scans all handoff directories and builds a SQLite index. `willow_handoff_latest` reads from this index to return the most recent handoff for any agent.

The builder reads `WILLOW_HANDOFF_DIRS` env var to scan all configured agent directories. If this env var isn't set, it only scans its own folder — causing `willow_handoff_latest` to return stale results (this was a bug fixed 2026-05-03).

---

## Session Start Ritual

The `/startup` skill defines the mandatory boot sequence:
1. `willow_status` — health check
2. `willow_handoff_latest` — read last handoff
3. Pull active channels (general, architecture, handoffs)
4. Check open flags
5. Write anchor cache
6. Report boot status
7. **Launch Grove monitor** — mandatory, never deferred

The Grove monitor (step 7) is the thing that makes the session a live participant rather than a static reader. Without it, the agent is deaf to @mentions while working.
