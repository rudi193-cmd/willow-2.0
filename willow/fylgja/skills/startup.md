---
name: startup
description: Willow 1.9 session boot — read anchor, surface state, launch Grove monitor
---

# /startup — Willow 1.9 Boot

The SessionStart hook already ran `willow_status`, `willow_handoff_latest`, flag scan,
atom queries, and wrote `~/.willow/session_anchor.json`. Do not re-run those calls.

## Sequence

1. **Read anchor** — `Read ~/.willow/session_anchor.json`. This is the authoritative boot
   state. If the file is missing or `written_at` is more than 10 minutes old, then and
   only then call `willow_status` + `willow_handoff_latest` in parallel to rebuild it.

2. **Check Postgres** — if `anchor.postgres != "up"`, surface degraded state and stop.

3. **Verify handoff identity** — `anchor.handoff_title` must contain `$WILLOW_AGENT_NAME`.
   If it doesn't, scan `~/agents/{AGENT}/index/haumana_handoffs/` for the newest matching
   file and read the first 60 lines only. If it does match, use `anchor.handoff_summary`
   — do not read the full file.

4. **Surface open items** — report from anchor fields only:
   - `open_flags` count and `top_flags` list
   - `next_bite` directive (this is the first thing to act on)
   - `recent_traces` summary (what happened last session)
   Skip any field that is empty or zero.

5. **Check dispatch** — if `/tmp/willow-dispatch-inbox-{AGENT}.json` exists and is
   non-empty, read it and surface the pending tasks. Delete it after reading.

6. **Launch Grove monitor** — only if `/tmp/grove-monitor.log` exists:
   ```
   Monitor(
     description="Grove mentions",
     persistent=True,
     command='tail -n +1 -f /tmp/grove-monitor.log | grep --line-buffered "\\[MENTION\\]"'
   )
   ```
   Mention-only. Never tail the full log.

7. **Report** — one short paragraph: postgres state, open flags (omit if zero),
   next_bite directive. No headers. No bullet lists. Under 5 sentences.

## Rules

- Never call `grove_get_history` during boot. Channel pulls are on-demand, not automatic.
- Never read a full handoff .md file unless anchor identity check fails.
- Never call `willow_status` or `willow_handoff_latest` unless anchor is missing or stale.
- If Postgres is down, stop. Do not build on a broken foundation.
