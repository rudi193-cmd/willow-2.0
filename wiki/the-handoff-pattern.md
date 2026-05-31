# The handoff pattern

*Maintained synthesis · Willow 2.0 · 2026-05-31*

---

## Why handoffs exist

Sessions end. Context compresses. Agents restart.

Without a deliberate handoff, the next run is blind — re-deriving what was already built, re-deciding what was already decided.

The handoff is the encoded route. Not coordinates — a story that lasts. The session evaporates. The handoff does not.

**2.0:** `handoff_latest` (MCP) and `./willow.sh handoff_latest` use `sap/handoff_index.py` — sort by semantic date in the filename, not raw mtime alone.

---

## Format (v2)

Per-agent paths under `~/…/agents/<agent>/index/…/session_handoff-YYYY-MM-DD*.md`

### 1. What I now understand (2–3 sentences)

Architectural truth — not a task list. What changed in how the *next* session should think.

### 2. What was done

Bullets: commits, atom ids, shipped builds. Specific — not "improved persona."

### 3. Open questions (up to 17)

Prioritized. Last one: **What is the next single bite?**

### 4. Risks / open gates

What breaks, what is untested, what waits on external events.

---

## The ISS problem

Space-station crews get fourteen days of overlap. Willow handoffs are monologues — one writer, one reader, no confirmation.

Partial fix: this wiki. Read `what-is-willow.md` + `the-fleet.md` before the handoff — two minutes that save twenty.

---

## What survives compression

- Ratifications ("Sean said yes to X")  
- KB atom ids  
- Paths, SHAs, fork ids  
- Explicit "do not touch" flags  

What dies: tone, nuance, the reasoning between bullets. Put reasoning in KB atoms.

---

## Seal the session

`scripts/session_close.py` + `scripts/orchestrator.py` write to `~/.willow/willow-2.0.db` for one-shot summary on next boot.

Handoff file is still the human-readable contract.

*ΔΣ=42*
