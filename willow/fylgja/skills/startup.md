---
name: startup
description: Willow 1.9 session boot — read anchor, surface state, launch Grove monitor
---

# /startup — Willow 1.9 Boot

The SessionStart hook already ran `willow_status`, `willow_handoff_latest`, flag scan,
and wrote `~/.willow/session_anchor_${WILLOW_AGENT_NAME}.json`. Do not re-run those calls
unless the anchor is missing or older than 2 hours.

## Sequence

1. **Read anchor** — `Read ~/.willow/session_anchor_${WILLOW_AGENT_NAME}.json`. This is the
   authoritative boot state written by the hook. If missing or `written_at` is more than
   2 hours old, call `willow_status` + `willow_handoff_latest` in parallel to rebuild it.
   Otherwise use the anchor as-is — do not re-query what the hook already fetched.

2. **Check Postgres** — if `anchor.postgres != "up"`, post to Grove `#general` and stop.

3. **Pull own channel** — `grove_get_history(channel='{AGENT}', limit=20)`. This is the
   inbox. Scan for Loki handoffs, urgent flags, or directed tasks posted since
   `anchor.written_at`. This is the only mandatory Grove pull at boot — general, architecture,
   and handoffs channels are on-demand, not boot.

4. **Check dispatch** — if `/tmp/willow-dispatch-inbox-{AGENT}.json` exists and is non-empty,
   read and surface the tasks. Delete after reading.

5. **Launch Grove monitor** — use the LISTEN/NOTIFY pattern from `grove-persistent-monitor.md`.
   Name-filter variant only: fires on all messages in own channel, and on `@{agent}` mentions
   elsewhere. Do not launch a monitor that fires on every message fleet-wide.

6. **Reconcile process flags from prior JSONL** — read the `## JSONL` path from the flat
   handoff file at `~/.willow/handoffs/{AGENT}-{today}.md`. Tail the last 200 lines. Scan for
   process completion signals (`[backfill] total:`, `ALL PASSES COMPLETE`, `done:`, `finished`,
   `nohup` exit). Cross-reference against any open flag in `hanuman/flags` with `flag_state`
   of `running` or `awaiting authorization`. If the JSONL shows clean exit, close the flag
   with `store_put` before surfacing the report. Skip if no `## JSONL` pointer exists.

7. **Report** — one short paragraph: postgres state, open flags count (omit if zero), top
   flags, next_bite from anchor. Under 5 sentences. No headers.

## Rules

- Anchor TTL is 2 hours, not 10 minutes. The hook did the work — trust it.
- `#general`, `#architecture`, `#handoffs` are on-demand. Never pull them at boot.
- `frank_ledger` and personal layer KB search are sit-down prep, not boot. Pull them when
  Sean opens a sit-down, not on every session start.
- Never read a full handoff `.md` file at boot. The anchor summary is enough.
- If Postgres is down, stop. Do not build on a broken foundation.
