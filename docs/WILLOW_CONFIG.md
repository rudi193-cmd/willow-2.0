# willow-config (private) + willow-2.0 (public)

Two repos, one machine:

| Repo | Remote | Checkout |
|------|--------|----------|
| **willow-config** | `rudi193-cmd/willow-config` (private) | `~/github/.willow` (`~/.willow` → symlink) |
| **willow-2.0** | `rudi193-cmd/willow-2.0` (public) | `~/github/willow-2.0` (`~/willow-2.0` → symlink) |

## Canonical (USER root: `~/github/.willow`)

- `willow.md` — fleet contract (canonical)
- Public snapshot — `willow-2.0/docs/CONTRACT.md` via `python3 scripts/sync_contract_snapshot.py`
- `env` — `WILLOW_ROOT`, `WILLOW_PG_DB`, paths
- `settings.global.json` — consent, fleet paths, default agent
- `handoffs/` — session continuity

Edit and commit these in **willow-config**, not in public willow-2.0.

## Symlinks in (public repo)

`bash setup.sh` or `python3 -m willow.fylgja.link_fleet_home`:

- `willow-2.0/willow.md` → `~/github/.willow/willow.md`
- `willow-2.0/willow/fylgja/config/fleet.env` → `~/github/.willow/env`
- `willow-2.0/willow/fylgja/config/settings.global.json` → `~/github/.willow/settings.global.json`

Deployed manifests and apps: `~/github/SAFE/Agents`, `~/github/SAFE/Applications` (`~/SAFE` → symlink).

Personal/archive data: `~/github/sean-data-vault` (`~/sean-data-vault` → symlink). Legacy 1.9 agent index stubs: `~/github/archive/legacy-agents-home` (`~/agents` → symlink).

## Host layout script

`bash scripts/consolidate_github_layout.sh` — wire home symlinks, move untracked drops out of willow-2.0, run `link_fleet_home`. See `~/github/README-fleet-layout.md`.

Templates for new machines: `fleet.env.example`, `settings.global.template.json` (in willow-2.0 only).
