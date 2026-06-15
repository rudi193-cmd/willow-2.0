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
| `repo-fleet-sweep.timer` | weekly `Mon 04:00` | `repo-fleet-sweep.service` | Repo hygiene sweep (diverged/unpushed repos, branch litter) |

**Enablement:** `setup.sh` enables `willow-metabolic.socket` (socket-activated
metabolic MCP) and `willow-w8-census.timer`. Other units, including
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

Before this, W8 was the fleet's stated trust instrument with no scheduler — the
census only ran when invoked by hand, so the saved report could silently go
stale. This is the heartbeat.

*ΔΣ=42*
