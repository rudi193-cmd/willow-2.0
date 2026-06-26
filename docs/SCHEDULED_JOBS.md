# Scheduled jobs — fleet systemd timers

b17: SCHED · ΔΣ=42

Willow's recurring fleet work runs as **systemd `--user` timers**. `setup.sh`
links `systemd/*.{service,socket,timer}` into `~/.config/systemd/user/` and
enables the fleet units with `systemctl --user`. All timers set
`Persistent=true`, so a run missed while the machine was off fires on next boot.

## Timers

| Unit | Schedule | Runs | Purpose |
|------|----------|------|---------|
| `willow-metabolic.timer` | nightly `03:00` | `willow.sh metabolic` | Norn pass — KB metabolism (demote/retire stale atoms) |
| `willow-w8-census.timer` | weekly `Mon 04:00` | `willow.sh w8-census` | W8 canonical-reconstruction census — the trust instrument's heartbeat |
| `willow-wce.timer` | weekly `Mon 05:00` | `willow.sh wce` | WCE continuity eval — thread recall, next-bite, surfacing, staleness vector |
| `willow-bridge-cross-runtime.timer` | daily `06:00` | `willow.sh bridge-cross-runtime` | Rebuild `cross-runtime.json` from latest handoff + session JSONL |
| `repo-fleet-sweep.timer` | weekly `Mon 04:00` | `repo-fleet-sweep.service` | Repo hygiene sweep (diverged/unpushed repos, branch litter) |

**Enablement:** `setup.sh` enables `willow-metabolic.socket` (on-demand Norn pass),
`willow-metabolic.timer` (nightly `03:00`), `willow-w8-census.timer`, and
`willow-wce.timer`. WCE timer only (existing install): `scripts/install_wce_timer.sh`.
Bridge timer only (existing install): `scripts/install_bridge_timer.sh`.
One-shot consecration on an existing install: `scripts/consecrate_metabolic.sh` (copies units,
enables socket+timer, runs first Norn pass). Other units, including
`repo-fleet-sweep.timer`, are linked and can be enabled on demand with
`systemctl --user enable --now <unit>`. Inspect live schedules with
`systemctl --user list-timers`.

## W8 census witness (added in v2026.06.7)

`scripts/w8_census_witness.py` is the scheduled heartbeat for the W8 trust
instrument. Each run:

1. runs `canonical_reconstruction_census()` (of canonical KB atoms, how many are
   traceable to origin via FRANK ledger ∪ `content.source_id` ∪ a
   provenance-typed edge);
2. refreshes the saved report the W8 evaluator reads
   (`sandbox/stone_soup/reports/recon-canonical.json`);
3. computes `cost = unsupported / canonical_total`;
4. posts a **Grove `#alerts`** message (channel 15) when `cost > 0.05`.

`W8_MAX_COST` overrides the threshold; `--dry-run` computes and reports without
posting. Run on demand: `./willow.sh w8-census`.

## WCE weekly witness (added 2026-06)

`scripts/wce_witness.py` is the scheduled heartbeat for the Willow Continuity Eval
(ADR-20260624). Each run:

1. executes `run_wce.py --tasks all` (cold recall + handoff-pair vector);
2. writes `willow/bench/continuity/runs/wce_<timestamp>.json`;
3. updates SOIL `{agent}/wce/state` with the metric vector;
4. ingests a frontier KB atom (`WCE_INGEST_KB=true` by default);
5. optionally posts a one-line summary to Grove when `WCE_REPORT_CHANNEL_ID` is set.

The norn pass also queues WCE via Kart when `wce_check` says due (7-day interval).
Run on demand: `./willow.sh wce` (respects interval) or `./willow.sh wce --force`.

Before this, WCE was manual-only — the continuity metric had no heartbeat.

*ΔΣ=42*
