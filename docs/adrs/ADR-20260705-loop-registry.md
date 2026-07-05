<!--
AGENT INSTRUCTIONS — see docs/templates/ADR.template.md
Read with mai_read_file; write with mai_write_file; do not use IDE Read/Write on filled file.
-->

# ADR-20260705-loop-registry

**b17:** ADRLR1 · ΔΣ=42

**Status:** proposed
**Date:** 2026-07-05
**Deciders:** Sean (+ agents: willow, persona Ada)
**Related:** [ADR-20260624-locomo-overfit-vs-continuity-eval](ADR-20260624-locomo-overfit-vs-continuity-eval.md) (WCE — an existing loop this ADR would register, not replace)

## Context

The fleet runs ~19 recurring surfaces with **no unified inventory**. The
2026-07-05 sweep (intake atoms 4B79925A, FE14A08B) found them spread across
three systems that don't know about each other:

- **7 systemd user timers** (sentinel-watchdog 15min; hook-wiring-audit,
  kb-snapshot-refresh, willow-metabolic daily; repo-fleet-sweep, w8-census,
  willow-wce weekly)
- **6 hook-registry handlers** (post_commit, post_merge, edge_linking,
  test_completion, shutdown, stop_slow)
- **~12 long-running daemons** (grove-*, kart-worker, watchers, bridges)
- The MCP-native `routine_list` registry: **empty**. The fleet's scheduling
  surface of record records nothing.

Consequences observed, not hypothesized:

1. **Watchmen heartbeat coverage is 2 of ~19.** Only upstream_watcher and
   sentinel_watchdog register heartbeats. The other 17 can die the quiet
   death — "completed, error: none, never ran again" — with no signal. This
   exact failure class produced the commit-atom-hooks-never-fired incident
   (172 atoms backfilled) and the hook-pipeline five-bug stack.
2. **Every loop is a bespoke script.** Adding automation means engineering a
   new Python file, its own error handling, its own (usually absent)
   heartbeat. The marginal cost of a new loop is a project, so loops don't
   get added, so chores stay manual or stay on frontier models.
3. **Verification discipline is per-author.** Some loops verify effects by
   recount (upstream groom #698: pending=0, archive+=188), some assert
   shapes, some nothing. Which discipline a loop has is discoverable only by
   reading its source.
4. Lane-4 (ollama) tenancy is live with one tenant, and the harness
   suite (PR #703) now defines *how* a local model fills a TASK slot — but
   there is no standard place to declare a loop that uses one.

The six-clause loop spec (TRIGGER / TASK / VERIFY / ATTENTION / EXIT /
ON FAILURE — from the "Building Loops" framing, 2026-07-05 discussion) plus
the fleet's verifier-tier taxonomy gives the schema this registry needs.

## Decision

Create **one declarative loop registry** and grow it by attrition, not
migration:

1. **Registry location:** SOIL collection `willow/loops` (one record per
   loop) mirrored to a repo-tracked `willow/fylgja/config/loops.json` for
   public clones. SOIL is live truth; the JSON is the seed/backup.
2. **Record schema — the six clauses plus fleet fields:**

   ```json
   {
     "id": "sentinel-watchdog",
     "trigger": {"kind": "timer", "spec": "OnUnitActiveSec=15min", "unit": "sentinel-watchdog.timer"},
     "task": {"kind": "script", "ref": "…/sentinel_watchdog.py", "model": null},
     "verify": {"class": "recount|exitcode|schema|coverage|containment", "predicate": "<one sentence, checkable>"},
     "attention": "<what it reads; bounded>",
     "exit": "<stop condition / pass limit>",
     "on_failure": "self_heal|queue_decision|open_flag",
     "heartbeat": {"watchmen_key": "sentinel_watchdog", "interval_sec": 900},
     "harness": null
   }
   ```

   `task.model` + `harness` point at a lane-4 harness directory (PR #703)
   when a local model fills the TASK slot.
3. **Watchmen-from-birth is a hard rule:** a loop record without a
   `heartbeat.watchmen_key` fails registry validation. Registering a loop
   IS registering its watchman. `fleet_status.watchmen` becomes the boiler
   light over the whole registry.
4. **Containment cannot self-complete:** `verify.class=containment` loops
   must declare `on_failure`+completion routing into a review queue
   (mem_ratify or human-required). Enforced by the same validator, mirroring
   the harness runner's CONTAINED verdict.
5. **Growth by attrition:** every NEW recurring surface must carry a
   registry record (checklist item in PR review). Existing loops get records
   opportunistically when touched. No big-bang migration — the sweep showed
   the bespoke scripts work; what's missing is the inventory and heartbeats.
6. **The registry is data, not an executor.** systemd/hooks/Kart keep
   running the loops exactly as today. A generic registry-driven runner is
   explicitly a POSSIBLE FUTURE (it is the consumer-product shape from the
   loops-for-laptops thread), deferred until the registry has proven itself
   as inventory + validation.

## Consequences

### Positive

- One query answers "what runs unattended, on what trigger, verified how?"
  — currently a 3-system archaeology task.
- Heartbeat coverage grows mechanically toward 19/19; the quiet-death class
  becomes structurally impossible for registered loops.
- `verify.class` makes verification discipline declarative and reviewable;
  containment loops are visibly fenced off from self-completion.
- The registry record is the future loop-template format for the
  SAFE-store/consumer thread — authored here, reused there.

### Negative / tradeoffs

- A registry that drifts from reality is worse than none. Mitigation: the
  hook-wiring-audit timer (already daily) gains a recount — registry records
  vs live systemd units/hook rows — and flags drift both directions.
- Attrition growth means months of partial coverage; the sweep table (atom
  FE14A08B) is the interim inventory.
- One more schema to learn. Kept to the six clauses everyone already knows
  plus three fleet fields.

## Alternatives considered

| Option | Why not |
|--------|---------|
| Populate the existing MCP `routine_*` registry | It's a scheduler (execution), not an inventory (description). Loops here live in systemd/hooks; forcing them into routines means migrating execution — big-bang risk for zero coverage gain. Revisit as the executor later. |
| systemd-only discipline (units as the registry) | Covers timers/daemons but not hook handlers or Kart tenants; unit files can't declare verify_class or containment routing; invisible to public clones. |
| Big-bang generic runner now | Highest-value long-term (consumer shape) but couples 19 working loops to new code at once — the exact opposite of the magma-layer lesson. Registry-as-data first, runner when earned. |
| Do nothing (bespoke scripts + sweep docs) | The sweep goes stale immediately; watchmen coverage stays 2/19; every silent-death incident repeats. |

## Receipts

| Type | Ref |
|------|-----|
| KB | intake atoms `4B79925A` (loops discussion + product thread) · `FE14A08B` (magma audit + sweep) |
| Git | PRs `#701` `#702` (audit fixes) · `#703` (lane-4 harnesses, verify-class enforcement precedent) · `#698` (recount-verified groom, the discipline exemplar) |
| Grove | #253 (lane-4 live + residual gaps table) |
| Session | willow 2026-07-05 night session (persona Ada) |

## Implementation notes

MVP is one PR: JSON schema + validator (`willow/fylgja/config/loops.schema.json`),
seed `loops.json` with the 7 timers + 2 registered watchmen as records,
registry↔reality recount added to hook-wiring-audit, and a `loop_list` MCP
tool reading the SOIL mirror. Wire `sentinel_watchdog` and `upstream_watcher`
first (they already heartbeat — records only). Verification command once
built: `python -m willow.fylgja.loops --validate && python -m willow.fylgja.loops --recount`.

## Supersedes

- None

---

*b17: ADR · ΔΣ=42*
