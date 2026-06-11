---
name: boot
description: Willow 2.0 primary boot gate — reads contract, establishes context, checks fleet, loads continuity, persona, corrections, and stack before first response.
---
@markdownai

# /boot

> **Primary boot gate.** Run before producing any response to the user. A greeting, short message, or casual opening is not an exception — boot first.
>
> **Exceptions (narrow — only these two; the agent does not classify a turn as exempt on its own judgment):**
> - User is in a physical, mental, or personal emergency — respond immediately, boot after.
> - User explicitly says to skip it ("sandbox", "load without context", "no startup", or equivalent) — acknowledge and proceed without boot.

---

## Pre-session (fires automatically — no action needed)

These run before your first turn via hooks:

| Hook | What it does |
|---|---|
| **SessionStart** | Hardware scan · willow_status · jeles registration · dispatch subscribe · heartbeat · corpus corrections seeded from memory feedback files · stack snapshot read from SOIL · anchor written to `$WILLOW_HOME/session_anchor_{agent}.json` |
| **prompt_submit (turn 1)** | Persona picker injected · boot guard injected · dispatch inbox injected |

---

## Config mode

`link_fleet_home` (or `bash setup.sh`) prints the active tier:

| Mode | When | Boot behavior |
|------|------|---------------|
| `private-config` | `~/github/.willow/willow.md` present | Full fleet: KB, handoffs, Grove |
| `public-fallback` | No private willow-config | Contract + skills + MCP template only |
| `degraded` | MCP or Postgres unreachable after boot starts | Continue with local contract |

In **public-fallback**: KB search, handoffs, and Grove are optional — not hard prerequisites.
In **private-config**: Postgres down remains a hard stop (step 3).

---

## Steps

**1. Contract**
`mai_read_file("willow.md")` — load the fleet contract.
Fallback: Read the raw file.

**2. Local context** *(compact)*
Agent name · repo root · current branch · staged/unstaged/untracked counts · one-line diff note.
No full patch. No full diffs.

**3. Fleet health** *(parallel with 4–6)*
`willow_status(app_id=<agent>)` — Postgres, SOIL, Ollama, manifests (`level=quick` by default).
`postgres` is a dict → up. Non-dict or timeout → probe directly.
**Postgres down = hard stop in private-config mode.** In public-fallback, note degraded and continue.

**4. Continuity** *(parallel with 3, 5–6)*
`handoff_latest(app_id=<agent>)` — what was in flight, open threads, agreements.
If stale (> 2h): note it, continue — run /startup after.

**5. Grove inbox** *(parallel with 3–4, 6)*
`grove_get_history` on agent channel since anchor written_at. Scan for directed, urgent messages.
If `/tmp/willow-dispatch-inbox-{agent}.json` exists → read, surface, delete.
Grove unavailable = degraded, not fatal. Continue.

**6. KB topic** *(parallel with 3–5)*
Extract the key topic or entity from the user's first message — strip filler phrases ("is an interesting subject", "I've been thinking about", "tell me about", etc.) and search on the core noun or concept. Examples: "NASA is an interesting subject" → `NASA`; "I've been thinking about cathedrals" → `cathedrals`; "fix the kart symlink" → use as-is.

`willow_find(scope=kb, query=<extracted topic>)` — routes to hybrid KB search; do not use the raw sentence as the query; embedding models match phrase structure, not topic.

**6b. Dream gate** *(parallel with 3–6; optional line in boot report)*
`dream_check(app_id=<agent>)` — if `should_dream` is true, surface one line: `Dream: due ({hours_since_dream}h, {sessions_since_dream} sessions) — queue via dream_schedule or /dream`. Do not run `dream_run` inline during boot unless the user asked.

After the search, classify the tone of the first message and pick one output mode for surfacing results in the boot report:

| Mode | When | Output shape |
|---|---|---|
| **Direct** | Clear task or question | KB hits as context, standard boot report continues |
| **Bridge** | Casual or ambient topic | 1–2 sentences connecting the topic to the actual open work |
| **Sideways** | Off-topic or random | Surface the most unexpected KB atom that resonates with the topic |
| **Story seed** | Creative, poetic, or philosophical | 2–3 sentences weaving the topic into current open threads |
| **One-liner** | Any tone | Single dry observation connecting the two |

If no KB hits land above 0.5 distance: skip the mode entirely, continue normally.

**Mode examples:**

*Direct* — "Fix the kart symlink" → "PR #170 is already open for this. CI is the gate."
*Direct* — "What's the LoCoMo baseline?" → "KB atom 0C7BA8F0: token_f1=0.1062, 1540 questions. Full-10 pending smoke pass."

*Bridge* — "NASA is an interesting subject" → "NASA's answer to temporal uncertainty: name the gap, build an instrument, then wait. The temporal gap in LoCoMo (cat-3 = 0.1001) is named. The instrument is `_is_counterfactual_query()`. Waiting on the smoke."
*Bridge* — "I've been thinking about cathedrals" → "Built on the assumption the builders won't see the spire. PR #151 is that kind of work — nobody celebrates the scaffold."

*Sideways* — "NASA is an interesting subject" → pulls autocatalytic closure atom: "Above a critical density, self-maintenance becomes inevitable. The retrieval pool is at 38 candidates. Might be past the threshold."
*Sideways* — "Byzantine art is fascinating" → pulls iconography atom: "Fixed representation, variable interpretation. That's what session summary atoms are doing."

*Story seed* — "NASA is an interesting subject" → "In 1977 Voyager left with a golden record — the whole mountain, not the herb. This session has a smoke test running in external_runs/. The record plays when we check."
*Story seed* — "I've been thinking about time" → "The ship that knows its position can calculate where it's been. The ship that only knows where it's been has to guess. LoCoMo cat-3 is the second ship."

*One-liner* — "NASA is an interesting subject" → "They also had a temporal gap problem. Took 8 minutes to know if it worked."
*One-liner* — "I like Mondays" → "Six open threads disagree."
*One-liner* — "What's the meaning of life?" → "42. It's been there the whole time. *ΔΣ=42*"

**7. Persona** *(voice overlay — not fleet identity)*
Read `$WILLOW_HOME/willow-2.0-active-persona` (`~/github/.willow`; `~/.willow` alias OK). Persona changes **voice only** — it does **not** switch MCP `app_id`, Grove sender, SOIL namespace, or `.willow/active-agent`. Fleet identity is `WILLOW_AGENT_NAME` / `active-agent`. To switch agent: `./willow.sh agents active <id> --install`.

If the active persona file exists and contains a non-empty name, normalize it by trimming whitespace and using the value as `{persona}`. Then attempt to load `willow/fylgja/skills/{persona}-boot.md`.

Persona boot overlay convention: add `willow/fylgja/skills/{persona}-boot.md` for any persona that needs boot-time voice, posture, or continuity instructions. Do not hardcode persona names in this file. If the overlay file exists, read it at this step and apply it as a voice/posture layer only. If it does not exist, skip silently and continue boot normally.

The hook injects picker + `[PERSONA-IDENTITY]` lines into system context only — **the user cannot see them**. Render the picker and identity banner as visible text in your boot response.
If active: load context per the persona registry (source defined in `willow.md` — the fleet contract, not any runtime-specific path). The optional `{persona}-boot.md` overlay supplements that registry context; it never changes fleet identity.

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
`ledger_read(project=<agent>, limit=3)` — use the fleet agent id (`WILLOW_AGENT_NAME` / `active-agent`), not the OS username. Newest entry `content.atoms_written` → priority IDs to skim.

**12. KB continuity + registry orientation** *(parallel)*
Read `willow/fylgja/config/startup_continuity.json` — run each `kb_searches[]` entry in parallel. Skim titles/summaries — full atom only if tied to open flag or handoff gap. All empty → skip.

Also orient against these registries if not already loaded this session:

| File | What it contains |
|---|---|
| `docs/INDEX.md` | Doc router — workflows, runbooks, and template index |
| `docs/templates/README.md` | Canonical agent artifact templates (handoff, audit, ADR, PR, atom, …) |
| `sap/mcp_registry.json` | All MCP tools grouped by domain prefix — the authoritative tool reference |
| `willow/fylgja/powers/registry.json` | 10 named powers (execute, plan, worktree, etc.) with cold-pull .md paths |
| `willow/fylgja/skills/plugin.json` | Fylgja skills manifest — LLM-agnostic behavioral skills |
| `scripts/index_annotations.json` | Repo directory map — what lives where |

Paths are relative to repo root. All six are dark by default — they do not self-announce. For session artifacts, copy from `docs/templates/` — do not improvise structure.

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
- Postgres down = hard stop in **private-config** only. Public-fallback may continue degraded.
- Grove unavailable = degraded, not fatal. Continue.
- Never report "postgres unknown" without probing first (step 3).
- Compact summaries only — no full diffs, no full handoff content.
- Persona picker and `[PERSONA-IDENTITY]` banner must be visible in the boot response — hook injection is system-only. Never imply persona switch changed fleet agent id.
- No hardcoded names or paths — use `[user]`, `[agent]`, env vars, or parameters.
- If anchor missing or stale (> 2h): run /startup after for deeper recovery.

## Handoff authoring — v2 schema

Write session handoffs to `$WILLOW_HOME/handoffs/{agent}/` — **not** `docs/handoffs/` (that directory contains old-format files and will produce the wrong schema).

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

Re-wire after pull: `./willow.sh agents install <agent> --ide claude` then `/reload-plugins` in Claude Code if skills still show unknown.
