---
name: boot
description: Willow 2.0 primary boot gate — reads contract, establishes context, checks fleet, loads continuity, persona, corrections, and stack before first response.
---

# /boot

> **Primary boot gate.** Run before producing any response to the user. A greeting, short message, or casual opening is not an exception — boot first.
>
> **Exceptions (narrow):**
> - User is in a physical, mental, or personal emergency — respond immediately, boot after.
> - User explicitly says to skip it ("sandbox", "load without context", "no startup", or equivalent) — acknowledge and proceed without boot.

---

## Pre-session (fires automatically — no action needed)

These run before your first turn via hooks:

| Hook | What it does |
|---|---|
| **SessionStart** | Hardware scan · fleet_status · jeles registration · dispatch subscribe · heartbeat · corpus corrections seeded from memory feedback files · stack snapshot read from SOIL · anchor written to `~/.willow/session_anchor_{agent}.json` |
| **prompt_submit (turn 1)** | Persona picker injected · boot guard injected · dispatch inbox injected |

---

## Steps

Run in order. Parallelize where marked. If fleet is degraded after step 3, surface it and stop.

**1. Contract**
`mai_read_file("willow.md")` — load the fleet contract.
Fallback: Read the raw file.

**2. Local context** *(compact)*
Agent name · repo root · current branch · staged/unstaged/untracked counts · one-line diff note.
No full patch. No full diffs.

**3. Fleet health** *(parallel with 4–6)*
`fleet_status(app_id=<agent>)` — Postgres, SOIL, Ollama, manifests.
`postgres` is a dict → up. Non-dict or timeout → probe directly.
**Postgres down = hard stop.** Post to #general, stop.

**4. Continuity** *(parallel with 3, 5–6)*
`handoff_latest(app_id=<agent>)` — what was in flight, open threads, agreements.
If stale (> 2h): note it, continue — run /startup after.

**5. Grove inbox** *(parallel with 3–4, 6)*
`grove_get_history` on agent channel since anchor written_at. Scan for directed, urgent messages.
If `/tmp/willow-dispatch-inbox-{agent}.json` exists → read, surface, delete.
Grove unavailable = degraded, not fatal. Continue.

**6. KB topic** *(parallel with 3–5)*
`kb_search(semantic=true, query=<current task or session topic>)` — check before acting.

**7. Persona**
Read `~/.willow/willow-2.0-active-persona`. The hook injects picker context into system context only — **the user cannot see it**. You must render the picker as visible text in your boot response so the user can confirm or switch.
If active: load context per the persona registry (source defined in `willow.md` — the fleet contract, not any runtime-specific path).

**8. Corrections + Preferences**
Read `corpus/corrections` and `corpus/preferences` — already seeded from memory feedback files by SessionStart hook.
Surface count and top items. These are behavioral rails for this session.

**9. Stack snapshot**
Read SOIL `{agent}/stack/current` — open tasks, open threads, open decisions written by last stop hook.
Prefer this over handoff title when richer. This is the authoritative "what was open."

**10. Open initiatives**
`soil_list({agent}/overseer)` → filter `status != "closed"`. One line per hit: `[branch] goal`.
Empty → skip. Surface count in boot report.

**11. Ledger** *(mandatory)*
`ledger_read(project=[user], limit=3)` — newest entry `content.atoms_written` → priority IDs to skim.

**12. KB continuity + registry orientation** *(parallel)*
Read `willow/fylgja/config/startup_continuity.json` — run each `kb_searches[]` entry in parallel. Skim titles/summaries — full atom only if tied to open flag or handoff gap. All empty → skip.

Also orient against these registries if not already loaded this session:

| File | What it contains |
|---|---|
| `sap/mcp_registry.json` | All MCP tools grouped by domain prefix — the authoritative tool reference |
| `willow/fylgja/powers/registry.json` | 10 named powers (execute, plan, worktree, etc.) with cold-pull .md paths |
| `willow/fylgja/skills/plugin.json` | Fylgja skills manifest — LLM-agnostic behavioral skills |
| `scripts/index_annotations.json` | Repo directory map — what lives where |

Paths are relative to repo root. All four are dark by default — they do not self-announce.

**13. Flag triage**
`soil_list({agent}/flags)` — close duplicates, surface open ones (max 5, one-line fix_path ≤150 chars).
Empty → skip.

**14. Boot report + sentinel**

**If `[PERSONA-GATE]` is present in system context this turn:**
Show ONLY the fenced picker block (copy it verbatim). End with the one footer line from the gate directive. Do NOT write a boot report. Do NOT start any work. Stop — wait for the user's next message.

**Otherwise (persona confirmed or no gate):**
First render the persona picker as a visible fenced block:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  PERSONA — confirm or switch
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. Oakenscroll    ...
  ...
  N. [active]  ← ACTIVE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Then a compact status list (no prose paragraph — one line each, no sub-bullets):

- **Fleet:** Postgres [up/down] · Ollama [running/down] · [N]/[total] manifests
- **Branch:** [branch] · [N] modified[, N staged] [· diff note if relevant]
- **Threads:** [N] open — [top item ≤80 chars, or "none"]
- **Corrections:** [N] loaded
- **Next:** [next_bite ≤120 chars]

Then write the boot sentinel: `Write(file_path="/tmp/willow-boot-done-{agent}.flag", content="booted")` — this clears the boot gate for this session. The sentinel is deleted by the Stop hook at session end.

Then respond to the user.

---

## Rules

- MCP tools at every step. Standard tools only when MCP confirmed unavailable.
- Postgres down = hard stop. Do not proceed.
- Grove unavailable = degraded, not fatal. Continue.
- Never report "postgres unknown" without probing first (step 3).
- Compact summaries only — no full diffs, no full handoff content.
- Persona picker must be rendered as visible text in the boot response — hook injection is system context only, the user cannot see it without explicit render.
- No hardcoded names or paths — use `[user]`, `[agent]`, env vars, or parameters.
- If anchor missing or stale (> 2h): run /startup after for deeper recovery.

## Handoff authoring — v2 schema

Write session handoffs to `~/.willow/handoffs/{agent}/` — **not** `docs/handoffs/` (that directory contains old-format files and will produce the wrong schema).

Filename pattern: `session_handoff-{date}{letter}_{agent}.md` (e.g. `session_handoff-2026-05-26d_hanuman.md`).

```markdown
---
agent: {agent}
date: {YYYY-MM-DD}
session: {YYYY-MM-DD}{letter}
runtime: claude-code
format: v2
---

# HANDOFF: {one-line title}

## What I Now Understand

{One paragraph summary — what changed this session, what was resolved, what was discovered.}

## Open Threads

- **[label]** — description. Fix_path or next action ≤150 chars.

## What We Agreed On

- Bullet list of decisions, commitments, constraints that carry forward.

## 17 Questions

Q1: {open question — something unresolved that the next session should know about}
Q2: {open question}
...
Q16: {open question}
Q17: {next single bite — one sentence, no preamble}
```

**Required:** `format: v2` and `session:` in frontmatter. Without them `handoff_latest` will not surface this file.
**Required:** Section headers must match exactly — `## What I Now Understand`, `## Open Threads`, `## What We Agreed On`, `## 17 Questions`.
**Required:** Q17 line must be `Q17: <text>` — no question mark in the key, colon-delimited, no preamble. Q17 is always "What is the next single bite?" answered.
**Convention:** Q1-Q16 are open questions for the next session — things unresolved, decisions pending, gates not yet crossed. Write as many as are genuinely open (pad to 17 only if needed). Q17 is always the next action.

After writing, run `handoff_rebuild(app_id={agent})` then verify with `handoff_latest(app_id={agent})`.

---

## Recovery

If continuity is the bottleneck (pick up where we left off, no fleet gate): run `/cold-recovery` — see `willow/fylgja/skills/cold-recovery.md`.

If boot is degraded or the anchor is stale: run `/startup`. That skill handles anchor recovery, KB continuity, ledger check, and flag triage at depth.

## Claude Code registration

`Skill(skill='boot')` resolves via the Fylgja plugin layout:

- `willow/fylgja/skills/.claude-plugin/plugin.json`
- `willow/fylgja/skills/commands/boot.md` → symlink to `boot.md`

Re-wire after pull: `./willow agents install <agent> --ide claude` then `/reload-plugins` in Claude Code if skills still show unknown.
