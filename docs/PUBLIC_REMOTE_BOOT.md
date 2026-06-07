# Public / remote boot (GitHub-only clone)

b17: PUBBOT · ΔΣ=42

Use this flow when you clone **willow-2.0** without access to private
**willow-config** (`~/github/.willow`) — e.g. remote Claude Code, a fresh laptop,
or a contributor machine.

## Quick start

```bash
git clone https://github.com/rudi193-cmd/willow-2.0.git
cd willow-2.0
bash setup.sh --public
./willow.sh agents install willow --ide claude --no-claude-global
```

`setup.sh --public`:

1. Skips private willow-config clone (non-fatal if clone would fail)
2. Materializes the tracked public pack → `.willow/generated/`
3. Symlinks `willow.md`, `fleet.env`, `settings.global.json` into the repo
4. Defaults active agent to `willow` if none set
5. Runs `install_project` for IDE wiring

Manual link only:

```bash
python3 -m willow.fylgja.link_fleet_home --public
```

Expect: `config-mode: public-fallback (home=…/willow-2.0/.willow/generated)`.

## Three-tier config

| Tier | Location | Contents |
|------|----------|----------|
| **Public pack** | `willow/fylgja/config/public/` | Contract, env template, safe settings |
| **Generated home** | `{repo}/.willow/generated/` | Materialized per clone (gitignored) |
| **Private config** | `~/github/.willow` | Full operator home when available |

Private config **upgrades** the experience automatically on next `setup.sh` when
`~/github/.willow/willow.md` exists.

## What works in public-fallback

- Fleet contract (`willow.md` / `/boot`)
- Fylgja skills and powers (repo)
- MCP template + `install_project` IDE wiring
- Code graph, MarkdownAI, local Read/Edit
- Kart task queue **if** Postgres is reachable locally

## What does not travel

- KB atoms, Jeles corpus, handoffs
- Grove credentials, Discord tokens, API keys
- Operator personas, session anchors
- Machine-specific absolute paths

## Boot modes

| Mode | Meaning |
|------|---------|
| `private-config` | Full willow-config home linked |
| `public-fallback` | Repo public pack only |
| `degraded` | MCP or Postgres down — contract still loads |

See [`willow/fylgja/skills/boot.md`](../willow/fylgja/skills/boot.md) — public-fallback
does not hard-stop on missing KB/Postgres.

## Verify

```bash
python3 -m pytest tests/test_fylgja/test_public_fallback.py -q
python3 scripts/verify_public_fallback.py
```

## Upgrade to private config

```bash
git clone git@github.com:rudi193-cmd/willow-config.git ~/github/.willow
bash setup.sh   # without --public
```

Re-run `./willow.sh agents install <id> --ide <surface>` to refresh IDE paths.

See also: [`WILLOW_CONFIG.md`](WILLOW_CONFIG.md) · [`CONTRACT.md`](CONTRACT.md)

*ΔΣ=42*
