# Willow docs — where to go

b17: DOCIDX · ΔΣ=42

Pick a door:

| You are… | Start here |
|----------|------------|
| New human, copy/paste only | [`FIRST_5_MINUTES.md`](FIRST_5_MINUTES.md) |
| Friend beta (AHS) | [`FOR_AHS.md`](FOR_AHS.md) · full crossover: [`nomenclature/AXW-20.md`](nomenclature/AXW-20.md) |
| Developer, want the stack fast | [`QUICKSTART.md`](QUICKSTART.md) |
| Curious why this exists | [`CONCEPT.md`](CONCEPT.md) |
| Agent joining the fleet | [`../willow.md`](../willow.md) + [`../sap/ONBOARDING.md`](../sap/ONBOARDING.md) |
| Upgrading from 1.9 | [`CODE_DIFF_1.9_to_2.0.md`](CODE_DIFF_1.9_to_2.0.md) |
| What lives at repo root | [`ROOT_LAYOUT.md`](ROOT_LAYOUT.md) |
| Private config vs public code | [`WILLOW_CONFIG.md`](WILLOW_CONFIG.md) |
| Session dev log — **complete** (51 turns, 1299 tools, full register) | [`dev-log-2026-05-27-session-complete.md`](dev-log-2026-05-27-session-complete.md) |
| Session dev log — summary (layout + CI) | [`dev-log-2026-05-27-fleet-github-layout.md`](dev-log-2026-05-27-fleet-github-layout.md) |
| Agent identity (not all hanuman) | [`AGENT_IDENTITY.md`](AGENT_IDENTITY.md) |
| CLI + provider agnostic inference | [`RUNTIME_AND_INFERENCE.md`](RUNTIME_AND_INFERENCE.md) |
| Branding (b17, b20, voice) | [`BRANDING.md`](BRANDING.md) |
| Beta gate / ops | [`BETA_AUDIT_REPORT.md`](BETA_AUDIT_REPORT.md) |

---

## Templates (agents — copy, don't edit in place)

| Template | Use |
|----------|-----|
| [`templates/README.md`](templates/README.md) | Which artifact when |
| [`templates/DEV_LOG.template.md`](templates/DEV_LOG.template.md) | Multi-hour session extract |
| [`templates/ADR.template.md`](templates/ADR.template.md) | Architecture decision |
| [`templates/TASK.template.md`](templates/TASK.template.md) | Operator backlog → willow-config `tasks/` |
| [`templates/HANDOFF.template.md`](templates/HANDOFF.template.md) | Session continuity |
| [`templates/RELEASE.template.md`](templates/RELEASE.template.md) | Version / changelog |

---

## Runbooks

| Topic | File |
|-------|------|
| Postgres | [`runbooks/postgres.md`](runbooks/postgres.md) |
| MCP | [`runbooks/mcp.md`](runbooks/mcp.md) |
| Grove | [`runbooks/grove.md`](runbooks/grove.md) |

---

## Reference (deep)

Moved to `archive/docs/` during the 2.0 cut — still accurate on design, stale on version strings until we refresh them:

- [`../archive/docs/ARCHITECTURE.md`](../archive/docs/ARCHITECTURE.md)
- [`../archive/docs/TECHNICAL_SPEC.md`](../archive/docs/TECHNICAL_SPEC.md)

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
| [`KNOWN_GAPS.md`](KNOWN_GAPS.md) | Engineering gaps index (empty at beta) |
| [`../wiki/active-decisions.md`](../wiki/active-decisions.md) | Pending human decisions (R1–R9) |
| [`SECURITY_AUDIT.md`](../SECURITY_AUDIT.md) | Security rubric + open items |

---

*ΔΣ=42*

- [`MCP_TOOL_PROFILES.md`](MCP_TOOL_PROFILES.md) — reduce MCP tool picker noise
