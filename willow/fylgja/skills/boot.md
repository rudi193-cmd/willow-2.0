---
name: boot
description: Willow 2.0 primary boot gate — reads contract, establishes context, checks fleet, loads continuity. Run before first response.
---

# /boot

> **Primary boot gate.** Run before producing any response to the user. A greeting, short message, or casual opening is not an exception — boot first.
>
> **Exceptions (narrow):**
> - User is in a physical, mental, or personal emergency — respond immediately, boot after.
> - User explicitly says to skip it ("sandbox", "load without context", "no startup", or equivalent) — acknowledge and proceed without boot.

## Steps

Run in order. If fleet is degraded after step 3, surface it and stop.

1. `mai_read_file("willow.md")` — load the contract. Fallback: Read the raw file.
2. **Local context** — agent name, repo root, current branch, compact diff (staged/unstaged/untracked counts + one-line note; no full patch). Read the repo README if not already known.
3. `fleet_status(app_id=<your-agent-id>)` — Postgres, SOIL, Ollama, manifests. Fallback: `./willow.sh fleet_status`. Postgres down = hard stop.
4. `handoff_latest(app_id=<your-agent-id>, agent=<your-agent-id>)` — what was in flight. Fallback: read latest file in `~/.willow/handoffs/<agent>/`.
5. `grove_get_history` — agent channel inbox continuity. Fallback: none — note degraded, continue.
6. `kb_search(semantic=true)` — search current task or session topic before acting.
7. **Boot report** — one short paragraph: fleet status, open threads from handoff, any flags. Then respond to the user.

## Rules

- MCP tools preferred at every step. Fall back to standard tools only when MCP is confirmed unavailable.
- Postgres down = hard stop. Do not proceed.
- Grove unavailable = degraded, not fatal. Continue without it.
- Compact summaries only — no full diffs, no full handoff content.
- If the session anchor (`~/.willow/session_anchor_<agent>.json`) is missing or stale (> 2h), run `/startup` after this boot for deeper recovery.

## Recovery

If boot is degraded or the anchor is stale: run `/startup`. That skill handles anchor recovery, KB continuity, ledger check, and flag triage.
