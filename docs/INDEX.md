# Willow docs — where to go

b17: DOCIDX · ΔΣ=42

Pick a door. If you are unsure, start with `FIRST_5_MINUTES.md` as a human or
root `../willow.md` as an agent.

| You are… | Start here |
|----------|------------|
| Want the fun front page | [`index.html`](index.html) — Oden VO · Muninn/Huginn street clips · [`LANDING_DESIGN.md`](LANDING_DESIGN.md) |
| New human, copy/paste only | [`FIRST_5_MINUTES.md`](FIRST_5_MINUTES.md) |
| Friend beta (AHS) | [`FOR_AHS.md`](FOR_AHS.md) · full crossover: [`nomenclature/AXW-20.md`](nomenclature/AXW-20.md) |
| Developer, want the stack fast | [`QUICKSTART.md`](QUICKSTART.md) |
| Curious why this exists | [`CONCEPT.md`](CONCEPT.md) |
| Agent joining the fleet | root contract: [`../willow.md`](../willow.md) · public snapshot: [`CONTRACT.md`](CONTRACT.md) · [`../sap/ONBOARDING.md`](../sap/ONBOARDING.md) |
| Upgrading from 1.9 | [`CODE_DIFF_1.9_to_2.0.md`](CODE_DIFF_1.9_to_2.0.md) |
| What lives at repo root | [`ROOT_LAYOUT.md`](ROOT_LAYOUT.md) |
| Private config vs public code | [`WILLOW_CONFIG.md`](WILLOW_CONFIG.md) · [`PUBLIC_REMOTE_BOOT.md`](PUBLIC_REMOTE_BOOT.md) |
| Fleet contract (public snapshot) | [`CONTRACT.md`](CONTRACT.md) — sync via `scripts/sync_contract_snapshot.py` |
| Audits (fleet/system reports) | [`audits/`](audits/) — latest: [`audits/SYSTEM_AUDIT_2026-06-10.md`](audits/SYSTEM_AUDIT_2026-06-10.md) |
| Open work (curated backlog) | [`OPEN_WORK.md`](OPEN_WORK.md) |
| Upstream contribution strategy | [`UPSTREAM_CONTRIBUTION_STRATEGY.md`](UPSTREAM_CONTRIBUTION_STRATEGY.md) |
| Agent identity (not all hanuman) | [`AGENT_IDENTITY.md`](AGENT_IDENTITY.md) |
| CLI + provider agnostic inference | [`RUNTIME_AND_INFERENCE.md`](RUNTIME_AND_INFERENCE.md) |
| Branding (b17, b20, voice) | [`BRANDING.md`](BRANDING.md) |
| Beta gate / ops | [`BETA_AUDIT_REPORT.md`](BETA_AUDIT_REPORT.md) |
| Scheduled jobs / fleet timers | [`SCHEDULED_JOBS.md`](SCHEDULED_JOBS.md) — metabolic (nightly), W8 census (weekly), repo sweep |
| MCP tool profiles (reduce picker noise) | [`MCP_TOOL_PROFILES.md`](MCP_TOOL_PROFILES.md) |

---

## Common Workflows

_Dev log archive: [`dev-log-2026-05-27-fleet-github-layout.md`](dev-log-2026-05-27-fleet-github-layout.md)_

| Goal | Path |
|------|------|
| Public clone, no private config | `bash setup.sh --public` → [`PUBLIC_REMOTE_BOOT.md`](PUBLIC_REMOTE_BOOT.md) |
| Fleet operator setup | `bash setup.sh` → [`WILLOW_CONFIG.md`](WILLOW_CONFIG.md) |
| IDE agent setup | `./willow.sh agents install <id> --ide <surface>` → [`IDE_INTEGRATION.md`](IDE_INTEGRATION.md) |
| Agent boot order | [`../willow.md`](../willow.md) → [`../willow/fylgja/skills/boot.md`](../willow/fylgja/skills/boot.md) |
| Fix stale or confusing docs | update the source doc, then regenerate root [`../INDEX.md`](../INDEX.md) with `python3 scripts/gen_index.py` when annotations change |

---

## Templates (agents — copy, don't edit in place)

Start at [`templates/README.md`](templates/README.md) — canonical router for all agent artifacts and runtime config pointers.

| Template | Use |
|----------|-----|
| [`templates/README.md`](templates/README.md) | Which artifact when + runtime template registry |
| [`templates/HANDOFF.template.md`](templates/HANDOFF.template.md) | Session continuity |
| [`templates/DEV_LOG.template.md`](templates/DEV_LOG.template.md) | Multi-hour session extract |
| [`templates/ADR.template.md`](templates/ADR.template.md) | Architecture decision |
| [`templates/AUDIT.template.md`](templates/AUDIT.template.md) | Fleet/subsystem audit report |
| [`templates/INVESTIGATION.template.md`](templates/INVESTIGATION.template.md) | Debug / root-cause investigation |
| [`templates/GROVE_DECISION.template.md`](templates/GROVE_DECISION.template.md) | Grove quorum / decision post |
| [`templates/ATOM.template.md`](templates/ATOM.template.md) | KB / SOIL atom candidate |
| [`templates/PR_WORKTREE.template.md`](templates/PR_WORKTREE.template.md) | Branch / worktree / PR summary |
| [`templates/TASK.template.md`](templates/TASK.template.md) | Operator backlog → willow-config `tasks/` |
| [`templates/RELEASE.template.md`](templates/RELEASE.template.md) | Version / changelog |

---

## Runbooks

| Topic | File |
|-------|------|
| Postgres | [`runbooks/postgres.md`](runbooks/postgres.md) |
| MCP | [`runbooks/mcp.md`](runbooks/mcp.md) |
| Grove | [`runbooks/grove.md`](runbooks/grove.md) |

---

## Benchmarks

| Artifact | What |
|----------|------|
| [`../benchmarks/README.md`](../benchmarks/README.md) | Benchmark and research atlas — families, sidecars, local pointers |
| [`../benchmarks/catalog.json`](../benchmarks/catalog.json) | Machine-readable benchmark registry |
| [`../benchmarks/sidecars/cartographer_code_memory/`](../benchmarks/sidecars/cartographer_code_memory/) | CBM cartographer prompt sidecar: SQLite DB, JSON, Markdown, refresh script |
| [`model-benchmark-field-report-2026-06.md`](model-benchmark-field-report-2026-06.md) | Observational Claude model field report (June 2026) |
| [`../willow/bench/locomo/`](../willow/bench/locomo/) | LoCoMo / LongMemEval Path A external memory benchmarks |
| [`../willow/bench/retrieval_gold.json`](../willow/bench/retrieval_gold.json) | Fleet KB retrieval gold-query regression gate |
| [`corpus/larousse-path-a-ephemeris-pattern.md`](corpus/larousse-path-a-ephemeris-pattern.md) | Research pattern: Larousse ephemeris ↔ Path A memory |

---

## Reference (deep)

Moved to `archive/docs/` during the 2.0 cut — still accurate on design, stale on version strings until we refresh them:

- [`../archive/docs/ARCHITECTURE.md`](../archive/docs/ARCHITECTURE.md)
- [`../archive/docs/TECHNICAL_SPEC.md`](../archive/docs/TECHNICAL_SPEC.md)
- [`../archive/docs/superpowers/README.md`](../archive/docs/superpowers/README.md) — historical plans/specs (1.9 era; do not execute blindly)

Schema: [`db/WILLOW_SCHEMA.md`](db/WILLOW_SCHEMA.md) · ADRs: [`adrs/README.md`](adrs/README.md)

---

## Wiki (synthesis)

Living pages the fleet maintains — not install guides:

[`../wiki/README.md`](../wiki/README.md)

---

## Grove sibling repo

Messaging MCP and channels live in **`safe-app-willow-grove`**. Clone it beside this repo if you use Grove from the IDE.

---

## Open work (not install blockers)

| Doc | What |
|-----|------|
| [`KNOWN_GAPS.md`](KNOWN_GAPS.md) | Broken-in-master engineering gaps |
| [`OPEN_WORK.md`](OPEN_WORK.md) | Curated backlog (not install blockers) |
| [`../wiki/active-decisions.md`](../wiki/active-decisions.md) | Pending human decisions (R1–R9) |
| [`SECURITY_AUDIT.md`](../SECURITY_AUDIT.md) | Security rubric + open items |

---

*ΔΣ=42*
