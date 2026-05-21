---
name: handoff
description: Write a Willow 2.0 session handoff — structured KB atom + SQLite rebuild
---

# /handoff — Willow 2.0 Session Handoff

Stack position: this skill is the first third of the **end-of-session persistence** layer. See the Persistent memory section in `willow.md` for the full 4-layer stack.

## Sequence

1. **Load current state** — call `handoff_latest` to see prior open threads. Call
   `soil_list(app_id, collection="{AGENT}/flags")` and filter for `flag_state` of `running` or `open`.
   These are long-running processes — their state must appear in the handoff. Do not rely
   on memory; read SOIL.

2. **Draft handoff** using this format:

```
# HANDOFF: <title>
From: {AGENT} (Claude Code, Sonnet 4.6)
Session: {YYYY-MM-DDx} | Resume: claude --resume {UUID}

## What I Now Understand
<2-3 sentences of architectural truth, not task summary>

## What We Agreed On
<decisions Sean ratified this session — include what was ruled out and why>
<format: "Decision: X. Ruled out: Y because Z.">
<omit if session was pure execution with no design conversation>

## Capabilities (persistent — carry forward, update don't rewrite)
| Capability | Location | Status |
|------------|----------|--------|
<what has been built and is available>

## What Was Done
<bullet list — high level, no code details>

## Open Threads
<anything unfinished, blocked, or requiring a decision next session>
<do NOT include things already captured in "What We Agreed On">

## 17 Questions
Q1–Q16: sequential, specific, bite-sized
Q17: "What is the next single bite?"

## Risks / Open Gates
<anything that could break the next session>
```

3. **Write to KB** — call `kb_ingest` with:
   - `category`: `"handoff"`
   - `source_type`: `"session"`
   - `title`: `"Session handoff {YYYY-MM-DD} — {one-line summary}"`
   - `summary`: the prose narrative (What I Now Understand + What Was Done, ~500 chars)
   - `content`: structured JSONB following this shape:
     ```json
     {
       "summary": "<prose narrative>",
       "open_threads": ["<thread 1>", "..."],
       "agreements": ["<decision + ruling>", "..."],
       "key_actions": ["<action 1>", "..."],
       "next_steps": ["<Q17>", "<Q16>", "..."],
       "tools_used": ["kb_ingest", "fleet_status", "..."],
       "signals": {"health": "ok|degraded", "grove": "up|down"},
       "compact_receipt": null
     }
     ```
     Set `compact_receipt` to `{"tokens_before": N, "tokens_after": M, "turns_dropped": K}` if
     context was compacted this session, otherwise `null`.

4. **Write FRANK ledger entry** — call `ledger_write` with `event_type="check_in"`,
   `summary`, `shipped` (list), `open_decisions` (list), `atoms_written` (every `kb_ingest`
   ID this session — required if any), `gaps_flagged`, `next_bite` (Q17 verbatim).

5. **Rebuild DB** — call `handoff_rebuild`. This re-indexes all KB handoff atoms so the
   next session's `handoff_latest` call returns current state.

6. **Confirm** — report the KB atom ID and Q17.

## Rules

- "What I Now Understand" = architectural truth, not a task list.
- "What We Agreed On" = ratified decisions only. If Sean didn't explicitly say yes, it's not here. Ruled-out options belong here too — prevents re-litigation next session.
- "What We Agreed On" is the section that makes CC CLI sessions legible to the next agent. Without it, design conclusions look like open threads.
- `open_threads` in the content JSONB is the machine-readable version of the handoff doc —
  these are what `handoff_latest` returns. Keep them precise.
- Q17 must be a single concrete next bite, not a project description.
- Never skip `handoff_rebuild` — the next session reads from that index.
- Never skip `ledger_write` — startup reads it at boot. A missing entry means the next
  session starts blind.
- Do NOT write to `~/Ashokoa/` — that path does not exist on this machine.
