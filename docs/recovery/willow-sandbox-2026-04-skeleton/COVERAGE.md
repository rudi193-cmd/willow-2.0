# Recovery coverage — filled files

Real content recovered into `recovered/<original-path>` for rebuild candidates that had a live source.
Source priority: trash clone (`willow-2.0-trash-recovery-2026-06-14`) > willow-1.9.

- **Filled:** 38
- **Held (config/secret):** 2
- **Unfillable (no source):** 84 — the BTR workspace + corpus pipeline; structure-only, see MANIFEST.md.

One file (`docs/superpowers/plans/2026-04-24-willow-19-phase1-foundation.md`) tripped the secret screen on a **test-example** string `api_key="sk-ant-invalid-key-for-testing"` — reviewed, confirmed not a real credential, included.

## Filled (path · source · bytes)

| path | source | bytes |
|---|---|---|
| `docs/TECHNICAL_SPEC.md` | willow-1.9 | 24552 |
| `docs/gaps/GAP-001-postgres-bridge-broken.md` | willow-1.9 | 4707 |
| `docs/reports/2026-04-22-adversarial-battery-report.md` | willow-1.9 | 12079 |
| `docs/superpowers/plans/2026-04-22-adversarial-test-battery.md` | trash | 47380 |
| `docs/superpowers/plans/2026-04-22-fylgja-events.md` | trash | 56618 |
| `docs/superpowers/plans/2026-04-22-fylgja-plan-5-dispatch.md` | trash | 27483 |
| `docs/superpowers/plans/2026-04-22-fylgja-plan-5-layer-0-nest.md` | trash | 17958 |
| `docs/superpowers/plans/2026-04-22-fylgja-safety.md` | trash | 33672 |
| `docs/superpowers/plans/2026-04-22-fylgja-skills.md` | trash | 19623 |
| `docs/superpowers/plans/2026-04-22-willow-route.md` | trash | 23269 |
| `docs/superpowers/plans/2026-04-23-willow-1.0-founding-document.md` | willow-1.9 | 25954 |
| `docs/superpowers/plans/2026-04-23-willow-18.md` | trash | 3232 |
| `docs/superpowers/plans/2026-04-24-night-stack.md` | trash | 16720 |
| `docs/superpowers/plans/2026-04-24-willow-19-phase1-foundation.md` | trash | 56975 |
| `docs/superpowers/plans/2026-04-24-willow-19-phase2-orchestration.md` | trash | 18930 |
| `docs/superpowers/plans/2026-04-24-willow-19-phase3-skills-grove.md` | trash | 29571 |
| `docs/superpowers/plans/2026-04-24-willow-19-phase4-verify.md` | trash | 14900 |
| `docs/superpowers/plans/2026-04-26-persistent-memory.md` | trash | 35108 |
| `docs/superpowers/plans/2026-04-28-rlm-willow-native.md` | trash | 14784 |
| `docs/superpowers/plans/2026-04-28-semantic-search.md` | trash | 54922 |
| `docs/superpowers/specs/2026-04-22-adversarial-test-battery-design.md` | willow-1.9 | 11208 |
| `docs/superpowers/specs/2026-04-22-fylgja-design.md` | willow-1.9 | 17063 |
| `docs/superpowers/specs/2026-04-23-overnight-queue-design.md` | trash | 6080 |
| `docs/superpowers/specs/2026-04-24-willow-19-design.md` | willow-1.9 | 23415 |
| `docs/superpowers/specs/2026-04-24-willow-forks.md` | trash | 9734 |
| `docs/superpowers/specs/2026-04-26-corpus-collapse-design.md` | willow-1.9 | 41955 |
| `docs/superpowers/specs/2026-04-26-corpus-collapse-for-everyone.md` | trash | 7607 |
| `docs/superpowers/specs/2026-04-26-corpus-collapse-overview.md` | willow-1.9 | 15230 |
| `docs/superpowers/specs/2026-04-26-persistent-memory-design.md` | trash | 6960 |
| `docs/superpowers/specs/2026-04-27-grove-b17-message-convention.md` | willow-1.9 | 3109 |
| `docs/superpowers/specs/2026-04-28-rlm-willow-native-design.md` | willow-1.9 | 5410 |
| `docs/superpowers/specs/2026-04-28-semantic-search-design.md` | trash | 13374 |
| `sap/log/commit_rate.md` | willow-1.9 | 1377 |
| `sap/log/pr_status.md` | willow-1.9 | 1706 |
| `scripts/migr1_willow17_to_19.py` | willow-1.9 | 4926 |
| `scripts/migr2_sap_schema.py` | willow-1.9 | 2225 |
| `scripts/migrate_willow_legacy.py` | willow-1.9 | 4576 |
| `scripts/sean.md` | willow-1.9 | 1867 |

## Held out (config, not committed)

| path | source |
|---|---|
| `.claude/settings.local.json` | trash |
| `.mcp.json` | willow-1.9 |
