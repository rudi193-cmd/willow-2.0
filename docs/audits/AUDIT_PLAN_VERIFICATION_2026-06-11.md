# Audit-Plan Verification — did "done" mean closed?

- **Date:** 2026-06-11
- **Auditor:** willow (Claude Code session, persona Hanuman) — audit-only, no code changed
- **Trigger:** S18 (the Kart sandbox audit, `KART_SANDBOX_AUDIT_2026-06-11.md`) was discovered *by accident* while tearing down a worktree — a defect that existed the whole time PR 5 was marked "Kart done." If one completed item hid that much, the others deserve the same scrutiny. This pass re-verifies every completed item of the 06-10 audit plan against current master, and re-scopes the pending ones.
- **Method:** map each plan-PR to its merged GitHub PR, then check the *claimed* outcome against the *enacted* state on master (commit `8f110e9`) — grep/ls evidence, not the PR description.

---

## Verdict in one paragraph

**"Done" in the 06-10 plan meant "a PR merged," not "the finding closed and verified."** Of six completed PRs, **three left enacted residue**: PR 4 shipped with two skills still carrying placeholder descriptions and one command file still broken in exactly the way the PR was written to fix; PR 8 shipped the sweep script but never wired the schedule that was its entire purpose; PR 5 left the whole read/visibility + security + worktree class open (S1–S18, separately documented). PR 1, PR 2, and PR 6 are genuinely closed. The plan had no verification step — the autonomy-licensing condition #1 ("verifiable: the system checks its own outcome") was never applied to the audit's own execution. S18 was not a fluke; it is representative.

---

## Completed-PR verification

| Plan PR | GitHub | Claim | Enacted state on master | Verdict |
|---|---|---|---|---|
| PR 1 | #308 | regen CONTRACT, fix doc links, move 6 handoffs to archive, add INDEX audits row | CONTRACT carries public-safety + PII ✓; 6 handoffs untracked in git (only on-disk residue lingers) ✓; INDEX Audits row present ✓ | **Closed** (trivial on-disk residue only) |
| PR 2 | #309 | untrack `settings.local.json`, parameterize operator paths | only the *public template* is tracked; private one untracked + gitignored ✓; no hardcoded `/home/...` in xfer.sh / willow-claude.sh ✓ | **Closed** |
| PR 4 | #310 | fix sync frontmatter detection; **regenerate all** `.claude` skill + command copies | **2 skills still carry placeholder descriptions** (`persistent-memory-stack`, `grove-quorum` — `"Willow Fylgja skill: …"`); **`.claude/commands/startup.md` still opens with `@markdownai v1.0` on line 1, before its YAML** — the exact frontmatter-detection bug PR 4 targeted | **PARTIAL — V1, V2** |
| PR 5 | #311 | facade defects + bwrap guards + retention sweep → "Kart hygiene" | facade + write-side guards landed, but the entire read/visibility, security, and worktree-management class stayed open | **PARTIAL — S1–S18** |
| PR 6 | #313 | intake tier enforcement, session-close completeness gate, memory-stack tightening | `core/intake.py` has tier/ratified logic ✓; `scripts/session_close.py` has the completeness gate ✓ | **Closed** (spot-verified; deep behavior unverified) |
| PR 8 | #312 | productize repo-fleet sweep **and schedule it** via Kart/cron | `scripts/repo_fleet_sweep.py` exists ✓; **no systemd unit, no routine, no cron reference anywhere in the repo** — never scheduled | **PARTIAL — V3** |

---

## New findings (verification class)

### V1 — PR 4 left two skills with placeholder descriptions *(Low)*
`.claude/skills/persistent-memory-stack/SKILL.md` and `.claude/skills/grove-quorum/SKILL.md` still read `description: Willow Fylgja skill: …` instead of the real one. This is why this session's own boot skill list shows those two with junk descriptions. PR 4 claimed "regenerate all `.claude/skills` copies"; these two were missed. **Fix:** re-run the (now-fixed) sync for these two surfaces; add a check that fails when any `.claude` description matches `Willow Fylgja skill:`.

### V2 — PR 4's target bug still live in `startup.md` *(Low/Med)*
`.claude/commands/startup.md` line 1 is `@markdownai v1.0`, *above* the YAML frontmatter — the precise "frontmatter detection fails when `@markdownai` precedes YAML" defect PR 4 was written to eliminate. (boot.md and shutdown.md are correct: `@markdownai` sits in the body, after frontmatter.) So the fix landed for most surfaces but not the one command that still carries the original shape. **Fix:** move `@markdownai` below the frontmatter (or regenerate startup.md from source); add a check that fails when line 1 of a `.claude/commands/*.md` is `@markdownai`.

### V3 — PR 8 sweep is built but unscheduled *(Medium)*
`scripts/repo_fleet_sweep.py` exists; nothing runs it. No `systemd/*` unit, no Fylgja routine, no cron entry references it. PR 8's stated deliverable was "productize the sweep **and schedule via Kart/cron, route threshold breaches to flags**." The capability shipped; the wire that makes it autonomous did not. This is the exact integration-debt pattern the parent audit named — a built capability one schedule away from working, marked done at "built." **Fix:** register a routine or systemd timer (follow the `upstream_steward` weekly pattern); route breaches to flags.

*(V-series numbering is local to this verification pass; S-series belongs to the Kart sandbox audit.)*

---

## Pending items — re-scope

| Item | State on master | Note |
|---|---|---|
| **PR 3 — service inventory** | `setup.sh` still installs **0** `*.timer` units; `willow-metabolic.timer` still never installed (06-10 F10). Single-source not done | Pending — unchanged |
| **PR 7 — close automation** | decision-gated: (a) stop-hook / (b) proclamation-/shutdown / (c) manual | Pending — needs operator decision |
| **Bitemporal repair (173)** | not verifiable from shell (psql on Willow stores is banned) — needs an MCP-side count | Pending — verify via `ledger_verify` / a KB query, then a dry-run repair |
| **SOIL dual-layout (HIGH)** | `core/soil.py` references a per-collection `store.db`; sap-layer path not confirmed in this pass | Pending — open; needs a dedicated diagnosis |
| **Corrections loop (06-10 F6)** | still open-circuit — no telemetry split, no repetition-trigger, no lifecycle (the boot context still shows repeated "Blocked Bash" corrections) | Pending — design+build, prerequisite for Tier-2 autonomy |

---

## Root cause

The plan optimized for **merge velocity**, not **closure**. Eleven PRs in a day is real output, but "merged" was treated as the terminal state. None of the completed items carried a machine-checkable definition-of-done, so partial closures (PR 4, PR 5, PR 8) looked identical to full ones in the handoff ledger. This is the same disease the parent audits keep naming — *stated-state diverging from enacted-state with no surfaced signal* (finding #16, S3, S18) — turned inward on the audit's own bookkeeping.

**The fix is a definition-of-done.** Every audit finding gets a one-line verifiable check (the grep/ls that proves it closed) written *before* the PR, and the check runs at merge and in a periodic sweep. A finding whose check still fails is not closed, regardless of how many PRs reference it.

---

## Remediation (small, ordered)

- **VP1 — PR 4 residue:** regenerate the 2 placeholder skills + fix `startup.md` frontmatter; add the two guard checks. Tiny, verifiable. *(V1, V2)*
- **VP2 — schedule the sweep:** wire `repo_fleet_sweep.py` to a routine/timer; route breaches to flags. *(V3)*
- **VP3 — definition-of-done harness:** a `scripts/audit_verify.py` that runs the per-finding checks and reports open vs. closed; seed it with S-series + V-series checks. This is the governor the plan was missing.
- **Kart sandbox (S1–S18):** per `KART_SANDBOX_AUDIT_2026-06-11.md` — KP1/KP2 first.
- **Pending decisions:** PR 7 close-design; bitemporal repair scope; SOIL dual-layout diagnosis.

All VP items are verifiable + reversible + PR-gated — clean Tier-1 dogfood candidates, and good first tests of the definition-of-done harness once VP3 exists.

*ΔΣ=42 — audit only; nothing in the codebase has been changed.*
