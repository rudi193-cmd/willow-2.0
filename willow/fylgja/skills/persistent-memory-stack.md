---
name: persistent-memory-stack
description: Willow 2.0 persistent memory architecture - boot persistence, mid-session persistence, and end-of-session persistence
---

# Persistent Memory Stack

This is the compact architecture for how Willow 2.0 remembers across a session, across compaction, and across restarts.

## Model

The stack has three layers:

1. **Boot persistence** - orient from live truth before acting.
2. **Mid-session persistence** - accumulate compact traces while working.
3. **End-of-session persistence** - seal the session so the next one does not start blind.

The rule is simple: boot from live state, accumulate small durable traces, then close with a handoff plus ledger trail.

## 1. Boot persistence

Purpose: give the agent the minimum truthful context needed to act without rebuilding state from chat memory.

Default boot path:

1. `markdownai-read_file("willow.md")`
2. local operating context: agent, namespace, repo root, branch, compact repo diff summary
3. `fleet_status`
4. `handoff_latest`
5. `grove_get_history(channel={AGENT}, limit=20)`
6. `kb_search` on the current task/topic
7. stop on degraded base or proceed to act

Boot persistence surfaces:

- `willow.md` - canonical boot contract
- compact repo state - local operating reality
- `fleet_status` - system reality
- `handoff_latest` - session reality
- `grove_get_history` - fleet/social reality
- `kb_search` - task continuity

Boot-adjacent support surfaces:

- `~/.willow/session_anchor_${WILLOW_AGENT_NAME}.json` - cache/fallback only
- ledger resume context - compacted-session assist
- dispatch inbox injection - urgent operator continuity
- flat handoff verification - crash recovery support

Rules:

- Prefer live truth over cached truth.
- Keep repo state compact: branch, clean/dirty, staged/unstaged/untracked counts, ahead/behind if known, short diff note.
- Do not dump a full patch at boot unless Sean asks for it.
- `/startup` is the recovery path, not the default path.

## 2. Mid-session persistence

Purpose: keep a compact durable trail while the agent works, without flooding the context window.

Primary writers:

- `events/prompt_submit.py`
- `events/pre_tool.py`
- `events/post_tool.py`

Mid-session persistence surfaces:

- prompt log in `~/agents/{AGENT}/cache/turns.txt`
- ledger observations for human turns
- feedback capture in `{AGENT}/feedback`
- correction capture in `corpus/corrections`
- trace atoms in `{AGENT}/turns/store`
- run-ledger events for significant tool uses
- blocked-tool ledger entries
- flat handoff checkpoints every N prompts

Protective but not primary memory:

- read dedup
- security advisories
- routing decisions
- rate limiting
- source-ring advancement state

Rules:

- Persist summaries, not full transcripts.
- Prefer append-only or checkpoint-style writes.
- Capture what changed, what blocked, and what the next instance would need.
- Mid-session memory should support handoff, not replace it.

## 3. End-of-session persistence

Purpose: seal the session into a form the next session can trust.

Required close trilogy:

1. `/handoff`
2. `ledger_write`
3. `handoff_rebuild`

Deliberate close pipeline:

- `/shutdown`
- session composite write
- compost
- Grove ingest
- feedback pipeline
- close session
- optional synthesis / edge linking

End-of-session truth surfaces:

- handoff atom and handoff index
- FRANK ledger entry
- rebuilt handoff DB

Rules:

- Never end without a handoff.
- Never skip `ledger_write` if the session changed durable state.
- Never skip `handoff_rebuild` - the next session reads from that index.
- The next bite must be explicit and concrete.

## Promotion guide

Promote into the default startup contract:

- `willow.md`
- compact repo state
- `fleet_status`
- `handoff_latest`
- `grove_get_history`
- `kb_search`

Keep as support or recovery:

- `session_anchor_*.json`
- `/startup`
- flat handoff verification
- deep flag cleanup
- ledger resume injection

Keep as close pipeline internals:

- compost
- ingot
- feedback processing
- synthesis and edge linking

## One-line contract

Boot from live truth. Accumulate compact traces while working. Seal the session with handoff plus ledger before exit.
