@markdownai v1.0

# Willow 2.0 — Full System Audit

- **Date:** 2026-06-10
- **Auditor:** willow (Claude Code session, audit-only — no code changes made)
- **Scope:** docs layer, skills layer, config/setup layer, scripts/hooks layer, live system state (SOIL, ledger, queues, systemd, Kart)
- **Method:** four parallel read-only sweeps + MCP diagnostics (`willow_status`, `soil_stats`, `hook_list`, `ledger_verify`, `human_required_queue_list`, `intake_list`, Kart-sandboxed listings)
- **Revision 8 (same day):** finding #16 added — **sandbox environment divergence under bwrap**. Two confirmed instances of state-mutating operations behaving differently inside the Kart sandbox than on the host: (1) GPG manifest signing fails silently from bwrap (root-caused 2026-05-31, KB atom 83D34B41; `sign_manifest()` still has no bwrap guard); (2) the pre-commit INDEX.md regeneration hook, running inside a bwrap-sandboxed commit (PR #307), deleted index rows for gitignored/host-only files it could not see (`.mcp.json`, `gaps.db`, `${HOME}`, `.kart-scripts`). Fix folded into PR 5. Also re-verified PR 1 claims at execution time: three were already fixed on master (FOR_AHS links carry the `nomenclature/` prefix, CODE_DIFF links already retarget `archive/docs/`, the six deprecated handoffs already live in `archive/docs/handoffs/`) — PR 1 narrows to CONTRACT regen, the WILLOW_CONFIG template reference, handoff path notation, the INDEX audits row, and landing this document.
- **Revision 7 (same day):** two operator corrections folded in: (1) stash finding amended — stashes are atom-documented by convention (verified, atom AAED75E5); the real check is stash↔atom parity, severity reduced; (2) the ecosystem sweep reframed around the capability inventory — the solutions to most audit gaps are already built (Nest, willow-bot, deep-review, steward pattern, dream, openclaw stop channel); the deficit is integration debt, not capability debt.
- **Revision 6 (same day):** ecosystem sweep of all 28 local repos — the audit's patterns confirmed fleet-wide (diverged repos, untracked deliverables, runtime state in git, branch/stash litter, unscheduled hygiene tools). Meta-finding: no repo-fleet hygiene loop; proposed as PR 8 and the strongest Tier-1 autonomy candidate.
- **Revision 5 (same day):** pulled `sean-data-vault` (3 commits today, incl. the 245-file professional layer) and reconciled the operator's prepared session prompt (`willow-2.0-memory-autonomy-prompt.md`) against the audit — agreements, four amendments (stop-hook design conflict, Nest watcher partially exists, KB scale claim, stale first-reads), and two new plan items (PR 6/7).
- **Revision 4 (same day):** added the closing "Autonomy map" section — the audit's second purpose, per operator: mark which loops can close without a human. Tier assignments, existing governors, missing governors (BUILD-STOP, outcome wiring, corrections-loop prerequisite), and the five-PR dogfood trial.
- **Revision 3 (same day):** finding #6 reframed from "dedup the corrections table" to "the correction loop is open-circuit" after operator discussion — the 699 records are evidence of a feedback-loop failure, not clutter. Distribution measured (77% hook events); design recorded as a KB atom.
- **Revision 2 (same day):** every "does not exist" claim re-checked against git rename lineage (`git log --follow --find-renames`). One claim corrected (`remote-control` → renamed `willow-remote`, not missing), one fix refined (`settings.global.template.json` → superseded by public pack). `corpus-watcher` and `willow-dashboard` have no rename history — those findings stand as written.

@constraint
This document proposes actions only. Every change below goes through worktree + PR per the `worktree-pr` Critical rule. Nothing in this audit has been applied.
@end

---

## Verdict in one paragraph

The core is healthy: ledger chain valid (86 entries), MCP registry exactly matches live tools (183/183), powers registry clean, zero broken skill symlinks, persona overlays complete, Postgres/Ollama/manifests all green. The rot is at the edges: a stale public contract snapshot, a service inventory that disagrees with reality in both directions, a sync tool that garbles skill frontmatter, ~200 dead one-off scripts in `.kart-scripts/`, an open-circuit correction loop (699 records, 77% of them the hook re-teaching the same lessons), machine-private settings tracked in the public repo, and a ledger "gaps" list that still flags work resolved two days ago.

---

## Severity index

| # | Finding | Layer | Severity |
|---|---------|-------|----------|
| 1 | `docs/CONTRACT.md` stale — missing mcp-first Critical, public-safety rule, PII clause | docs | **High** |
| 2 | `willow/fylgja/config/settings.local.json` tracked with `/home/sean-campbell` paths | config | **High** |
| 3 | Service inventory drift: willow.sh ↔ systemd/ ↔ setup.sh ↔ installed units | config | **High** |
| 4 | Skill sync tool produces double/garbled frontmatter (`@markdownai` before YAML) | skills | Medium |
| 5 | `.kart-scripts/` landfill — 389 files, ~200 dead one-offs | scripts | Medium |
| 6 | Correction loop is open-circuit — hook blocks logged as "corrections," no lifecycle, repeats never trigger investigation | live | **High** |
| 7 | Deprecated `docs/handoffs/` still holds 6 tracked handoff files | docs | Medium |
| 8 | Ledger/cross-runtime "gaps" stale (webhook 401 resolved 06-09, still flagged) | live | Medium |
| 9 | Kart facade defects: script_body=python-only undocumented, run_now returns wrong task, stdout truncates | scripts | Medium |
| 10 | `willow-metabolic.timer` never installed (setup.sh copies only .service/.socket) | config | Medium |
| 11 | Broken doc links (WILLOW_CONFIG, FOR_AHS, CODE_DIFF) | docs | Low |
| 12 | ~80 empty SOIL collections + ~40 stale `forks/*/env` leftovers | live | Low |
| 13 | Duplicate/unchecked config copies (.claude settings pair, .cursor permissions dup) | config | Low |
| 14 | Hardcoded operator paths in tools/xfer.sh, willow-claude.sh, kart SKILL.md examples | config | Low |
| 15 | Doc redundancy/orphans (ATOM_EXTRACTION ×3, willow-handoff.md, INDEX gaps) | docs | Low |
| 16 | Sandbox environment divergence — state-mutating ops (GPG signing, pre-commit regeneration) behave differently under bwrap; no guard | scripts | Medium |

---

## 1. Docs layer

### Broken (fix)
- **`docs/WILLOW_CONFIG.md`** references `settings.global.template.json` — superseded by the public fallback pack (commit `36a0ca4`): the live files are `willow/fylgja/config/settings.global.json` and `willow/fylgja/config/public/settings.global.json`. → Update the doc to name `config/public/settings.global.json` as the template.
- **`docs/FOR_AHS.md`** links `AXW-20.md` / `AXW-20-NECRONS.md` without the `nomenclature/` prefix. → Fix links.
- **`docs/CODE_DIFF_1.9_to_2.0.md`** links `docs/ARCHITECTURE.md` and `docs/TECHNICAL_SPEC.md`, both moved to `archive/docs/`. → Fix the two links; leave historical 1.9 file mentions as-is.

### Inconsistent (fix)
- **`docs/CONTRACT.md` vs `willow.md`** — snapshot generated 2026-06-08, before PR #302 hardening. Missing: `mcp-first` upgraded to Critical + Fallback Protocol section, `public-safety` rule, PII bullet. → Run `python3 scripts/sync_contract_snapshot.py`, commit via PR. Consider a CI check that fails when the snapshot drifts.
- **`docs/handoffs/`** — README declares the dir DEPRECATED, `.gitignore` blocks new files, yet six tracked `session_handoff-2026-05-31*.md` remain. → `git mv` to `archive/docs/handoffs/`.
- **Handoff path notation split** — templates say `~/github/.willow/handoffs/`, continuity docs say `~/.willow/handoffs/`. Same place via symlink, confusing to fresh agents. → Standardize on `~/.willow/...` with a one-line symlink note.

### Redundant / orphaned (tidy)
- `ATOM_EXTRACTION_DESIGN/COMPLETE/QUICKSTART.md` — three docs (~27 KB) for one finished feature, none in INDEX. → Merge COMPLETE into DESIGN or archive it; keep QUICKSTART; add one INDEX row.
- `docs/willow-handoff.md` — live MarkdownAI Postgres dashboard, referenced by nothing, overlaps `handoff_latest`. → Add INDEX row if still used, else delete.
- `docs/OPEN_WORK.md` — last updated 06-04, statuses likely stale. → Refresh or fold into wiki.
- `docs/INDEX.md` — no Audits section despite six files in `docs/audits/`; dev-log pinned in the "start here" table. → Add Audits row, demote the dev-log.
- `docs/gaps/README.md` (214-byte pointer), `docs/superpowers/README.md` (tombstone), `docs/lore/gerald.md` (orphan lore), `docs/.nojekyll` — all harmless. → Leave.

## 2. Skills layer

Clean: all 6 command symlinks resolve, zero broken file references across ~40 skills, all six persona boot overlays present and byte-identical between copies, boot/startup/cold-recovery explicitly delineated (not conflicting).

### Broken (fix)
- **Sync tool frontmatter bug** — fylgja sources open with `@markdownai v1.0` before their YAML, so the fylgja→`.claude` sync fails to detect existing frontmatter and prepends a generic block. Result: `.claude/skills/{handoff,startup,power}/SKILL.md` have double frontmatter; `.claude/commands/{handoff,startup}.md` descriptions render literally as "@markdownai v1.0". → Fix the sync tool's frontmatter detection (or move `@markdownai` below YAML in sources), then re-sync.
- **`.claude/commands/power.md`** drifted: hardcodes `~/github/willow-2.0/...` where source uses `${WILLOW_ROOT:-...}`. → Regenerate from source.

### Redundant / useless (tidy)
- ~10+ `.claude/skills/*` copies carry placeholder descriptions ("Willow Fylgja skill: X.") instead of the real ones — this is why the session skill list shows duplicates with junk descriptions. → Regenerate from fylgja sources after the sync fix.
- `willow/fylgja/commands/` (overseer.md, power.md) — second commands dir referenced by no manifest. → Fold into `willow/fylgja/skills/commands/` or delete.
- **`remote-control` was renamed `willow-remote`** (operator-anonymization era, commits `dce7a17`/`16b2573`; rename recorded in `docs/audits/CANONICAL_HOME_RUNTIME_AUDIT_2026-06-07.md:185`). The skill is alive: `willow/fylgja/skills/willow-remote.md`, `.claude/skills/willow-remote/SKILL.md`, `.claude/commands/willow-remote.md`. The old ledger question ("dead or needs authoring?") is answered: authored, renamed. → Close the thread. One stale reference survives: `.kart-scripts/docs-refresh-fylgja-paths.py` still points at `willow/fylgja/skills/commands/remote-control.md` — dies with the `.kart-scripts` sweep (finding #5). *(Correction: the first pass of this audit wrongly called this skill "never authored" — it checked for the filename but not rename lineage.)*

## 3. Config / setup layer

### Broken (fix)
- **`setup.sh:139`** copies only `*.service` and `*.socket` — `willow-metabolic.timer` is never installed despite willow.sh calling the service "timer/socket capable". → Add `*.timer` to the glob and the enable list.
- **`willow.sh` inventory vs reality:**
  - `corpus-watcher` — no unit, no script anywhere in-tree. → Restore it or drop from inventory into a documented "external/helper" list.
  - `willow-dashboard` — actually a sibling repo (`~/github/willow-dashboard`) that setup.sh never clones; not a local unit. → Remove from systemd inventory; document the external dependency.
  - `journal-responder` — helper spawned per-entry by journal-watcher, yet listed in both start-all and stop-all arrays, guaranteeing a phantom "missing unit" row forever. → Remove from both arrays.
  - `journal-watcher.service` and `willow-mcp.service` exist in `systemd/` but are **not installed** in `~/.config/systemd/user/` (setup.sh hasn't run since PR #302 merged). → Run setup or copy+`daemon-reload`, then decide enable state (open handoff question).
  - Five installed units are **unmanaged** — not in the repo or inventory: `downloads-watcher`, `drop-ngrok`, `grove-ngrok`, `openclaw-gateway`, `willow-bot`. → Either adopt into the repo/inventory or document them as machine-local.
- **`setup.sh:151-154`** enables only 6 of 15 inventoried units; `grove-serve`, `kart-worker`, `orin-worker`, `willow-mcp`, `upstream-watcher`, `willow-discord-responder` ship but never enable. The `willow.sh:77` comment promises a "single inventory" but setup.sh doesn't read it. → Generate both lists from one source (e.g. setup.sh sources the array from willow.sh) so they cannot drift.

### Privacy / portability (fix)
- **`willow/fylgja/config/settings.local.json` is tracked** and contains `/home/sean-campbell/...` permission paths — machine-private IDE settings in the public repo, directly against the contract's `public-safety` rule. → Untrack, add to `.gitignore`; keep `config/public/settings.local.json` as the template.
- `kart-sandbox.json` binds `{{HOME}}/Ashokoa` and `{{HOME}}/Desktop` read-write in a tracked policy file. → Move to a private overlay or `bind_try`.
- Hardcoded operator values: `tools/xfer.sh:15` (`REMOTE_USER`), `scripts/willow-claude.sh:5-6` (venv/splash paths), kart `SKILL.md:20` examples (absolute path; also vendored into `.cursor`/`.codex`/`.agents`). → Parameterize with env / `{WILLOW_ROOT}`.

### Drift guards (improve)
- `.claude/settings.json` ≡ `willow/fylgja/config/claude-settings.json` is byte-identical today, but `agents_cli.py` drift-checks only the cursor pair. → Add the claude pair to `_surface_matches_canonical`.
- `.cursor/permissions.json` ≡ `.cursor/cli.json` — exact duplicate permission blocks. → Keep one, generate or delete the other.

### Clean
`sap/mcp_registry.json` (183/183 vs live), `willow/fylgja/powers/registry.json` (11/11), systemd units use `%h`, public config pack properly templated, `fleet.env`/`settings.global.json` correctly untracked.

## 4. Scripts / Kart layer

- **`.kart-scripts/` landfill** — 389 files; ~200 are named one-off probes and payloads: `rh_dirty_probe2`–`9`, `rh_dry_run`1–4, `openclaw_90165_*` ×17, `smoke-kb-context`1–4, `locomo_*` ×12, ~12 `handoff-write-*`, plus auto-generated `kart_*.py` bodies. → Adopt a retention policy: auto-generated `kart_*.py` older than N days deleted by a cron/dream task; named one-offs archived or deleted after their PR merges. Keep genuinely reusable ones (`skirnir_splash_*` pending the font decision) in `scripts/` instead.
- **Kart facade defects** (all reproduced live this session):
  1. `willow_run(script_body=...)` is Python-only; shell input fails with SyntaxError and nothing says so. → Document in the tool description, or detect shebang/shell and route accordingly.
  2. `run_now=true` can execute and return a *different* pending backlog task's result than the one just submitted. → Return the submitted task's result or clearly label which task ran.
  3. Task stdout truncates from the **front**, silently. → Truncate from the tail with a marker, or raise the cap.
- **Sandbox environment divergence (finding #16, added rev 8)** — operations that mutate state behave differently under bwrap than on the host, and nothing detects the mismatch:
  1. GPG manifest signing fails silently from Kart (KB atom 83D34B41); 26/26 manifests had to be re-signed from a host terminal; `sign_manifest()` still has no bwrap guard.
  2. The pre-commit INDEX.md regeneration hook ran inside a bwrap-sandboxed `git commit` (PR #307) and removed rows for files the sandbox cannot see — the index recorded the sandbox's view of the tree, not the real one.
  → Add a shared `is_bwrap()` guard helper; apply it to `sign_manifest()` (hard error, not silent skip); for regeneration hooks, either skip regen under sandbox or bind the paths the hook needs. Joins PR 5.
- **Kart lifetime failure rate** — 604 failed vs 1870 completed (24%). Much of this is the syntax/replay defects above plus dead one-offs. → After fixing the facade, baseline the failure rate; consider purging failed-task history older than 30 days.
- `scripts/` overlaps: `kb_repair.py`, `human_required.py`, `human_attestation.py`, `consolidate_home_clones.py` exist in both `scripts/` and `core/` (or `.kart-scripts/`); `restore_upstream_worktrees` exists as both `.py` and `.sh`. → Spot-check each pair, keep one canonical.

## 5. Live system state

- **The correction loop is open-circuit** *(reframed in rev 3 — the original finding proposed dedup/expiry, which treats the evidence as the problem)*. Measured distribution: 536 of 699 records (77%) are automated "Blocked Bash" hook events — 158× "use Glob", 118× "use Read", 75× older Glob wording, 56× "use Kart", 44× SQLite, etc. Rate fell from 50–90/day (mid-May) to 1–5/day (early June), then resurged to 18/day on 06-09 and 06-10: every fresh session re-pays the same tax. Three failures, none of them "the table is dirty":
  1. **Category error at the write** — hook *enforcement events* (rule already enforced, blessed path already taken) are recorded as *corrections* (operator feedback an agent must learn). The ~163 genuine corrections drown under 536 copies of the hook talking to itself.
  2. **Write-only loop** — records carry a `promoted` field and `scripts/promote_corrections.py` exists, but nothing measures recurrence, converts a 158×-repeated correction into structural change, or retires anything. The system writes "don't do X" 158 times and never asks why every agent keeps doing X.
  3. **Repeats are affordance gaps, not disobedience** — reproduced live during this audit: the hook blocked `ls` and recommended Glob in a session where Glob is not exposed; Kart facade defects (finding #9) make the blessed path genuinely worse than Bash for simple listings. Agents are being "corrected" for making rational choices against a broken or missing blessed path.

  → Redesign (design record: KB atom, see rev-3 note): **(a)** split the streams — hook blocks become a telemetry counter (one record per rule: hit count, last_seen, per-runtime breakdown); `corpus/corrections` carries human feedback only; **(b)** make repetition the trigger — same rule blocking ≥N times in a window auto-opens a flag: "blessed path for X may be broken or missing"; **(c)** give corrections a lifecycle — raised → promoted into structure (hook / contract line / tool description / actual fix) → recurrence watched → archived when it stops firing. Invariants: a correction that can't be promoted into structure is a preference; one that recurs after promotion is a bug in the blessed path, not in the agent.
- **Stale gap tracking** — newest ledger check-in (06-08) still flags "webhook 401 deferred" and "daemon-reload pending," but intake record `68115A10` (06-09, confidence 1.0) records both resolved. Cross-runtime open list shows the same lag. → Write a closing check-in entry; have /shutdown reconcile gaps against intake before writing.
- **Intake backlog** — 4 unpromoted records, including a real bug: `NOVITA_API_KEY` not wired into the MCP server env (`infer_imagine` broken). → Promote the NOVITA gap to a flag/KB atom; promote or discard the rest.
- **SOIL litter** — ~80 zero-record collections (mostly `<topic>/atoms` skeletons: `physics/atoms`, `epstein_network/atoms`, …) and ~40 single-record `forks/*/env` from merged branches (`hanuman/forks/FORK-*`, named feature forks). → Add a sweep (dream task or script) that archives empty collections and fork-env records whose branches no longer exist.
- **`willow/stack/current` is empty** (written 06-07, no open tasks/threads) while the handoff carries 3 open threads — the stop hook isn't capturing stack state, so step 9 of boot reads nothing. → Verify the stop hook writes the stack snapshot; this session can confirm at shutdown.
- **`hanuman/flags`: 12 records** vs `willow/flags`: 0 — flags live under the old agent namespace; boot's flag triage for `willow` reads the empty one. → Migrate or dual-read during the hanuman→willow identity transition.
- **Clean:** ledger chain valid (86), hooks registry sane (6 active), human-required queue legitimately waiting on operator (3 items), dream system live, manifests 4/4.

---

## Proposed action plan (ordered)

**PR 1 — contract & docs truth (small, do first)**
1. Regenerate `docs/CONTRACT.md` via `sync_contract_snapshot.py`.
2. Fix the three broken doc links (WILLOW_CONFIG, FOR_AHS, CODE_DIFF).
3. `git mv` the six `docs/handoffs/session_handoff-*` files to `archive/docs/handoffs/`.
4. Standardize handoff path notation; add Audits row + this document to `docs/INDEX.md`.

**PR 2 — privacy & portability**
5. Untrack `willow/fylgja/config/settings.local.json`; gitignore it.
6. Parameterize `tools/xfer.sh`, `scripts/willow-claude.sh`, kart SKILL.md examples; move Ashokoa/Desktop binds out of tracked `kart-sandbox.json`.

**PR 3 — service inventory reconciliation**
7. Single-source the service list (setup.sh reads willow.sh's array).
8. Add `*.timer` to setup.sh install glob; decide the enable tier for the 6 never-enabled units.
9. Drop `corpus-watcher`/`willow-dashboard`/`journal-responder` from the systemd arrays into a documented external/helper list.
10. Adopt or document the five unmanaged installed units (`willow-bot`, `openclaw-gateway`, ngrok pair, `downloads-watcher`).

**PR 4 — skill sync fix**
11. Fix frontmatter detection in the sync tool; regenerate all `.claude/skills` + `.claude/commands` copies; resolve the orphan `willow/fylgja/commands/` dir.

**PR 5 — Kart hygiene**
12. Fix/document the three facade defects (script_body language, run_now result mismatch, truncation direction).
13. Retention policy + sweep for `.kart-scripts/`.
13b. Sandbox divergence guard (finding #16): `is_bwrap()` helper, applied to `sign_manifest()`; regen-hooks skip or bind under sandbox.

**Operational (no PR needed)**
14. Redesign the correction loop per finding #6 (split streams / repetition-triggers-flag / lifecycle) — this is a design+build item, likely its own PR; the 699 records are kept as the baseline dataset, not deleted.
15. Reconcile ledger gaps with intake; write closing check-in; promote the NOVITA_API_KEY gap.
16. SOIL sweep for empty collections and dead fork envs; migrate `hanuman/flags` → `willow/flags`.
17. Local: install `journal-watcher.service` (+ decide `willow-mcp.service`), `systemctl --user daemon-reload`.
18. Decide fate of the two untracked RH7 verification `.txt` files at repo root (commit, move, or delete — they predate this audit).

---

## Autonomy map (closing section — added rev 4)

The operator's framing: this audit exists not just to find breakage but to mark **which loops can
close without a human in them**. The recurring day-to-day toil — babysitting PRs, dogfooding
agents along, telling them to stop, re-teaching the same patterns — is the target.

### The licensing principle

A task is safe to make autonomous when all three hold:

1. **Verifiable** — the system itself can check the outcome (CI green, file exists, count is zero).
2. **Reversible** — the action is undoable, or gated behind something undoable (a PR, an archive-not-delete).
3. **Closed-loop** — failure is detected and routed (flag, queue item, halt), not piled.

Nearly every finding in this audit is a violation of condition 3. The system has the *capability*
for autonomy; what it lacks is **governors**.

### Governors that already exist (most of the hard part is built)

| Governor | What it provides |
|---|---|
| `worktree-pr` + CI | Reversibility gate — anything PR-gated is cheap to undo (PRs #301/#302 proved the recovery path) |
| `human_required` queue | Consent gate — the correct destination for never-autonomous decisions |
| FRANK ledger | Tamper-evident audit trail — autonomous actions reviewable after the fact |
| Kart sandbox + task history | Contained execution with a record |
| `babysit`, `outcome_*`, routines/cron, `upstream_steward`, Grove monitor | Supervision scaffolding, mostly unwired |

### Tier assignments

**Tier 1 — fully autonomous now** (verifiable + PR-gated/trivially reversible):
- PR babysitting: CI watch, rebase on master, re-run flaky checks, report. (`babysit` exists; needs a schedule, not an operator.)
- Audit hygiene loops: contract-snapshot drift check, skill-copy drift check, doc-link check, `.kart-scripts` retention sweep, SOIL empty-collection sweep, intake triage at shutdown. All are detect → PR/flag → report.

**Tier 2 — autonomous with a tripwire:**
- Merging green PRs touching only an allowlist (docs, config templates — never contract, hooks, permissions). Any file outside the allowlist → `human_required`.
- Gap routing: `willow_remember` input tagged `gap` auto-becomes a flag (intake record E8C7EF52 — a live broken tool sat silently in a memory queue — is the case for this).

**Tier 3 — never autonomous, by design:**
- External-facing actions (publishing, posts to humans, comments on others' repos).
- Secrets, deletes (archive instead, per contract), PII boundaries.
- Changes to contract/hooks/permissions — these ARE the governors; a system that edits its own
  governors is not self-correcting, it is unsupervised.

### The missing governors (gap list)

1. **BUILD-STOP** — hooks inject `[BUILD-CONTINUE]` (keep going, don't ask) but there is no
   symmetric stop rail: no budget, no scope fence, no "N tasks without convergence → halt and
   flag." The operator is currently the stop condition — both for runaway agents and (PR #305,
   this session) for scope overrun. Fix shape: every autonomous task carries a **scoped goal,
   explicit stop condition, and outcome check, written before it starts**; exceeding them halts
   and opens a `human_required` item instead of pressing on.
2. **Outcome wiring** — `outcome_run`/`outcome_agent_register` exist but are barely invoked;
   they are the natural home for "verify the result, then report" on every Tier-1 loop.
3. **The corrections loop (finding #6) is the prerequisite, not a peer finding.** Self-correction
   is the license for autonomy: an agent that repeats the same blocked action 158 times without
   the system noticing is not ready to merge PRs unsupervised. The redesign (telemetry →
   repetition flags → lifecycle) must land before Tier 2 is trusted.

### Proving it: the dogfood trial

This audit's five proposed PRs are the test cases — each verifiable, reversible, scoped. Run them
as autonomy trials: the agent takes one end-to-end (branch → build → verify → PR → CI green →
report) with a written stop condition; the operator's only touch is the merge button. Five clean
runs proves Tier 1 on real work, and the trial telemetry is the argument for Tier 2.

---

## Operator work order — reconciliation (added rev 5)

`sean-data-vault` commit `1527f1f` ships `professional/.../willow-2.0-memory-autonomy-prompt.md` —
a prepared session prompt targeting the same two goals as this audit's autonomy map: tighten the
5-layer memory stack, autonomize the close/intake loops. Reconciliation against today's findings:

### Where the prompt and the audit agree (the work order stands)

| Prompt target | Audit connection |
|---|---|
| Norn-pass scheduling — `promote_intake.py` on a Kart interval (end of session or daily) | This is "the pump" the intake discussion called for. Prompt settles the design choice: **both** shutdown-time and scheduled. |
| Intake tier enforcement (`observed/fetched/verified/ratified`; `ratified` requires human attestation) | Pairs with the gap-routing tripwire (Tier 2) and `human_attestation_*` tools already present. |
| Handoff completeness gate in `session_close.py` (no open threads / no capability table → reject) | Closes the gap a prior session already found ("what now exists" got lost from handoffs). Belongs in the new shutdown step 2 (PR #306) as well as `session_close.py`. |
| SOIL graduation trigger (stabilized SOIL records → KB) | Same shape as the corrections lifecycle (finding #6): raised → promoted → watched. One design should serve both. |
| Bi-temporal audit of promotion (`valid_at`/`invalid_at`, supersede-not-delete) | Matches contract rule "archive stale atoms, do not delete." Verifiable — good Tier-1 dogfood candidate. |

### Where this audit amends the prompt

1. **Session close automation** — the prompt says: wire `session_close.py` to the Claude Code stop
   hook, restore the hook lost in the April 2026 wipe. But 2.0 made an explicit design decision the
   other way: *"Stop hook is cleanup-only. Pipeline only runs on explicit /shutdown"* (shutdown.md
   rules). There are now three competing close designs on the table:
   (a) automatic close on stop hook (this prompt), (b) proclamation-triggered /shutdown (operator
   proposal, prototyped and parked as closed PR #305 / commit `5e3a0f5`), (c) manual /shutdown
   (status quo). **Decision needed before implementation** — (a) and (b) can coexist ((b) catches
   intentional sign-offs, (a) catches abandoned sessions), but (a) reverses a ratified rule and
   must be re-ratified explicitly.
2. **Nest watcher** — the prompt says "implement a Nest watcher." `systemd/nest-watcher.service`
   and the `nest_scan`/`nest_queue`/`nest_file` MCP tools already exist. The work is **verify and
   wire the missing link** (auto-`intake_write` at `tier=verified, confidence=1.0` + Grove log),
   not build from scratch. The service-inventory drift (finding #3) is why this looked missing.
3. **KB scale claim** — the prompt says 229,000 atoms; live `willow_status` today reports 10,765
   knowledge rows + 515 jeles atoms + 69 opus atoms. Either the prompt counts a different corpus
   (full vault drops?) or it is stale — correct it before a fresh session inherits a wrong mental
   model of scale.
4. **First-reads list** — the prompt sends a fresh agent to `docs/KNOWN_GAPS.md` + `docs/OPEN_WORK.md`;
   this audit found OPEN_WORK.md stale since 06-04. Regenerating it (action #2/PR 1 territory)
   should precede running the prompt, or the fresh session starts on stale backlog state.

### Net effect on the action plan

The prompt's items join the plan as **PR 6 — memory-stack tightening** (norn-pass audit, tier
enforcement, completeness gate, SOIL graduation, bi-temporal verification) and **PR 7 — close
automation** (gated on the (a)/(b)/(c) decision above; Nest wiring). Both are strong dogfood-trial
candidates: verifiable outcomes, PR-gated, scoped.

---

## Ecosystem sweep — all local repositories (added rev 6)

Operator hypothesis: the audit's gap patterns are not willow-2.0-specific. Swept all 28 git repos
under `~/github` (read-only; fetch + status only). **Confirmed** — the same five patterns, one
repo fleet wide:

### Findings by pattern

**1. Diverged repos — pull-before-push violations waiting to happen** *(High)*
- `safe-app-store`: **ahead 8 / behind 1** — eight unpushed commits on a diverged master, 12 local branches.
- `willow-bot`: ahead 1 / behind 1 — diverged; the unpushed commit is on master directly (worktree-pr rule does not extend here).
- This is the exact failure mode the worktree-pull memory records for willow-2.0, live in two more repos.

**2. Deliverables living outside git — the "RH7 verification files" pattern at scale** *(High)*
- `safe-app-store` untracked: `store_mcp.py`, `tui.py`, `dev_tui.sh`, `VISION.md`, `data/` — source files and a vision doc, not scratch.
- `willow-2.0` untracked: the two RH7 txt files + this audit document.
- Untracked work is invisible to every agent that boots from git state.

**3. Runtime state tracked in a repo — category error, corrections-style** *(Medium)*
- `.willow` (private config): 18 dirty — tracked-and-modified `willow_responder.pid`,
  `willow_responder_state.json`, `discord_claims.json`, `version`, live handoffs, settings.
  PID and state files in git guarantee permanent dirt; the repo can never be clean, so real
  changes hide in the noise. Same shape as enforcement events polluting corpus/corrections.

**4. Branch litter and stash↔atom parity** *(Low — amended in rev 7)*
- *Correction (operator + KB verification):* stashes are **not** anonymous litter — fleet
  convention is that agents write a KB atom when they stash (confirmed: atom `AAED75E5` "Stash
  upstream PR #9 — Ollama local-first docs"). The stash count itself is not a finding.
- The remaining gap is **parity, unverified in either direction**: nothing checks that every
  stash has an atom and every stash atom still has a live stash. A stash whose atom was never
  written is invisible; an atom whose stash was popped is a phantom open thread. → The repo-fleet
  sweep (PR 8) should check parity, not count stashes.
- Branch litter stands at reduced severity: 34 local branches in willow-2.0, 12 in
  safe-app-store, mostly merged-PR leftovers. `list_stale_branches.sh` and
  `cleanup_worktrees.sh` exist — unscheduled.

**5. Upstream-contribution clones parked on feature branches** *(Low / informational)*
- 9 repos (awesome-claude-skills, basic-memory, claude-deep-review, engram, hermes-agent,
  mcp-memory-service, ngrok-python, sigmap, smallcode, …) sit on PR feature branches — correct
  for in-flight upstream PRs, but `litellm` and `python-sdk` branches have **no upstream
  tracking** (ahead/behind unknowable), and nothing inventories which of these PRs are merged,
  stale, or awaiting re-review beyond the hand-maintained cross-runtime list (which finding #8
  already showed goes stale).

Clean: 18 of 28 repos fully clean and synced. `sean-data-vault`, `quiet-corner`, `willow-1.9`,
and all the small upstream clones are in good order.

### The capability inventory — the solutions are already built (added rev 7)

The operator's actual point in commissioning this sweep: the ecosystem doesn't just reproduce
the audit's gaps — **it already contains the solutions to most of them.** The deficit is
integration debt (the last wire + a schedule), not capability debt:

| Already built | Where | Audit gap it solves |
|---|---|---|
| Nest (`nest-watcher.service`, `nest_scan`/`nest_queue`/`nest_file`, `core/intake.py`) | willow-2.0 | Autonomous intake from drops (work-order item 4) — needs only the auto-`intake_write` wire |
| willow-bot (GitHub App + webhook, HMAC preflight) | willow-bot | The GitHub/PR toil — the receiving end for PR automation already exists |
| claude-deep-review (operator fork, finding-dedup module) | claude-deep-review | Automated PR review — the review half of PR babysitting |
| upstream_steward + skill-steward (scheduled scans → SOIL triage → Grove) | willow-2.0 | The *template* for every scheduled sweep this audit proposes — the pump exists as a pattern, proven weekly |
| Dream system (`dream_check/run/schedule`) + hermes-agent dreaming plugin | willow-2.0, hermes-agent | The background-consolidation scheduler that can drive norn-pass, corrections telemetry, SOIL graduation |
| mcp-memory-service `rfc1008-s3-auto-capture` branch | mcp-memory-service | Auto-capture design — prior art for hook-block telemetry (finding #6a) |
| engram / basic-memory / sigmap (hot-cold index) | upstream forks | Memory consolidation + tiering patterns for the 5-layer stack work (PR 6) |
| openclaw-gateway + Discord bridge (`openclaw-discord` skill) | installed unit + willow-2.0 | The remote **stop** channel — "telling them to stop" from a phone is built, pairs with the missing BUILD-STOP rail |
| `orchestrator.py`, `outcome_*`, `grove_gate` | willow-2.0 | The governors the autonomy map calls for — present, barely wired |

The repo-fleet hygiene loop (PR 8) remains the one genuinely missing piece — and even it is
"schedule the ~20-line sweep that produced this section," following the steward pattern above.

**Revised meta-finding:** the audit's gap list is, almost line for line, a *wiring* list. The
system is past the build phase on most of these problems; what the fleet needs is a session (or
an autonomous agent, per the tier map) whose only job is connecting built capabilities to their
schedules and triggers.

### Proposed actions (joins the plan)

- **Operational:** push or reconcile `safe-app-store` (8 unpushed) and `willow-bot` (1 unpushed)
  — operator decision per repo, divergence means a merge/rebase choice.
- **Operational:** adopt or discard the untracked source files in `safe-app-store`.
- **PR (in .willow repo):** gitignore + untrack PID/state/claims files; handoffs and settings
  reviewed case-by-case.
- **PR 8 — repo-fleet sweep:** productize the sweep script (`scripts/repo_fleet_sweep.sh`),
  schedule via Kart/cron, route threshold breaches to flags. Branch/stash cleanup offered as a
  report, never auto-deleted (Tier 3: no autonomous deletes).

---

*ΔΣ=42 — audit only; nothing above has been changed.*
