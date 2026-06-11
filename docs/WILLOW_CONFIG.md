# willow-config (private) + willow-2.0 (public)

Two repos, one machine:

| Repo | Remote | Checkout |
|------|--------|----------|
| **willow-config** | `rudi193-cmd/willow-config` (private) | `~/github/.willow` (`~/.willow` → symlink) |
| **willow-2.0** | `rudi193-cmd/willow-2.0` (public) | `~/github/willow-2.0` (`~/willow-2.0` → symlink) |

## Public contract + private overlay

The portable boot contract is the tracked root file in the public repo:

- `willow-2.0/willow.md` — public-safe fleet contract and `/boot` entrypoint
- `willow-2.0/willow/fylgja/config/public/willow.md` — copy materialized into public-fallback homes

The private config home may provide an overlay:

- `~/github/.willow/willow.md` — private live fleet context, handoffs, and operator policy
- `env` — `WILLOW_ROOT`, `WILLOW_PG_DB`, paths
- `settings.global.json` — consent, fleet paths, default agent
- `handoffs/` — session continuity

Edit public boot rules in **willow-2.0**. Edit private live context in
**willow-config**. Do not make the public root `willow.md` a symlink to private
config.

## Runtime links in the public repo

`bash setup.sh` or `python3 -m willow.fylgja.link_fleet_home`:

- `willow-2.0/willow/fylgja/config/fleet.env` → `~/github/.willow/env`
- `willow-2.0/willow/fylgja/config/settings.global.json` → `~/github/.willow/settings.global.json`

Root `willow-2.0/willow.md` remains a tracked public file so GitHub-only clones
have a valid entrypoint.

Deployed manifests and apps: `~/github/SAFE/Agents`, `~/github/SAFE/Applications` (`~/SAFE` → symlink).

**SAFE move + audit:** `bash scripts/repair_safe_layout.sh` then `python3 scripts/audit_safe_paths.py`. After re-sign: `python3 scripts/sync_safe_agent_manifests.py --force` and `./willow.sh verify`.

Personal/archive data: `~/github/sean-data-vault` (`~/sean-data-vault` → symlink). Legacy 1.9 agent index stubs: `~/github/archive/legacy-agents-home` (`~/agents` → symlink).

## Host layout script

`bash scripts/consolidate_github_layout.sh` — wire home symlinks, move untracked drops out of willow-2.0, run `link_fleet_home`. See `~/github/README-fleet-layout.md`.

Templates for new machines: `fleet.env.example`, `willow/fylgja/config/public/settings.global.json` (public fallback pack, in willow-2.0 only).

**Public-only clones:** see [`PUBLIC_REMOTE_BOOT.md`](PUBLIC_REMOTE_BOOT.md) — tracked pack at
`willow/fylgja/config/public/`, materialized to `.willow/generated/` when private config is absent.

## Path resolver

| Function | Module | Resolves |
|----------|--------|----------|
| `fleet_home()` / `willow_home()` | `willow/fylgja/willow_home.py` | `$WILLOW_HOME` → private config or public generated |
| `willow_home_alias()` | same | `~/.willow` (backward-compat reads) |
| `resolve_store_root()` | same | `$WILLOW_STORE_ROOT` or `$WILLOW_HOME/store` |
| `resolve_secrets_path()` | same | `$WILLOW_HOME/secrets.sh` |

Verify live layout: `bash scripts/audit_canonical_home.sh`  
Audit report: [`audits/CANONICAL_HOME_RUNTIME_AUDIT_2026-06-07.md`](audits/CANONICAL_HOME_RUNTIME_AUDIT_2026-06-07.md)
