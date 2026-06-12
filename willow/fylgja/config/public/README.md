# Public Willow config pack

Tracked, safe defaults for **GitHub-only clones** without private `willow-config`
(`~/github/.willow`).

`link_fleet_home` materializes these files into `{repo}/.willow/generated/` when
private config is absent, then symlinks runtime config paths to that home. The
root `willow.md` remains a tracked public file in the repo.

## Included

| File | Purpose |
|------|---------|
| `willow.md` | Public fleet contract copy for generated fallback homes |
| `env.example` | Local-safe env template → generated `env` |
| `settings.global.json` | Consent + fleet flags (no operator paths) |
| `settings.local.json` | IDE MCP permissions template (no secrets) |

## Intentionally missing

- Postgres KB atoms, Jeles corpus, handoffs
- Grove auth tokens, Discord tokens, API keys
- Operator personas and session anchors
- Machine-specific absolute paths

## Upgrade path

Clone `rudi193-cmd/willow-config` to `~/github/.willow`, re-run `bash setup.sh`,
and `link_fleet_home` switches to **private-config** mode automatically.

See [`docs/PUBLIC_REMOTE_BOOT.md`](../../../../docs/PUBLIC_REMOTE_BOOT.md).
