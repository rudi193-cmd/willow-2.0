# Contributing to Willow 2.0

Thank you for helping tend the tree. This doc covers setup, quality gates, PR expectations, and release hygiene.

## Before you start

1. Read [`docs/FIRST_5_MINUTES.md`](docs/FIRST_5_MINUTES.md) — install, health checks, optional pre-commit.
2. Read [`docs/AGENT_IDENTITY.md`](docs/AGENT_IDENTITY.md) if you wire an IDE — one agent per session, canonical settings under `WILLOW_HOME`.
3. Search [`docs/INDEX.md`](docs/INDEX.md), [`docs/OPEN_WORK.md`](docs/OPEN_WORK.md), and the KB before building something that may already exist.

## Development setup

```bash
git clone https://github.com/rudi193-cmd/willow-2.0
cd willow-2.0
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
pre-commit install --hook-type pre-push
```

**Python:** 3.11 or 3.12 (`openclaw-sap-gate` in `requirements.txt` requires ≥3.11).

**IDE wiring:**

```bash
./willow agents active <agent-id>
./willow agents install <agent-id> --ide all
```

Per-agent IDE permissions live at `$WILLOW_HOME/agents/<agent>/settings.local.json` (symlinked into `.cursor/` and `.claude/` — not committed).

## Quality gates

Run before opening a PR:

```bash
bash scripts/lint_first_party.sh          # ruff enforced; mypy report-only
python3 -m pytest --ignore=tests/adversarial/e2e -q
bash scripts/path_guard.sh                # no hardcoded home paths
```

CI enforces:

| Check | Meaning |
|-------|---------|
| `lint` | `ruff check core sap willow tests scripts` |
| `test` | pytest matrix on 3.11 + 3.12 (Postgres service) |
| `path-guard` | legacy path scan |

Report-only in CI (artifacts, not merge blockers yet): mypy, coverage, bandit.

First-party scope excludes vendored trees (`worktrees/`, `mcp-memory-service/`, etc.) — see `pyproject.toml`.

## Pull requests

1. Branch from `master`; keep PRs focused.
2. Use the [PR template](.github/PULL_REQUEST_TEMPLATE.md).
3. Ensure required checks **`test`** and **`path-guard`** pass (exact names — branch protection depends on them).
4. Do not commit secrets, `.cursor/settings.local.json`, or machine-specific symlinks like `willow.md`.
5. Prefer extending existing patterns over new abstractions.

## Branch hygiene

We carry many long-lived remote branches. Periodically audit stale ones:

```bash
bash scripts/list_stale_branches.sh          # default: 90 days idle
bash scripts/list_stale_branches.sh 30       # stricter window
```

Delete only branches you own or that fleet has ratified — script lists; it does not delete.

## API documentation (local)

Generate module reference for `core/`, `sap/`, and `willow/`:

```bash
bash scripts/build_api_docs.sh
# output: docs/api/  (gitignored)
```

Uses [pdoc](https://pdoc.dev/) — optional dev dependency.

## Releases

Version source of truth: [`VERSION`](VERSION) → `core/version.py`.

Maintainers cut a release by tagging:

```bash
git tag v$(cat VERSION)
git push origin "v$(cat VERSION)"
```

The [Release workflow](.github/workflows/release.yml) creates a GitHub Release with generated notes. Append human-facing changes to [`CHANGELOG.md`](CHANGELOG.md) under `[Unreleased]` before tagging.

## Getting help

- Architecture: [`docs/ROOT_LAYOUT.md`](docs/ROOT_LAYOUT.md), [`wiki/what-is-willow.md`](wiki/what-is-willow.md)
- MCP tools: [`docs/MCP_TOOL_PROFILES.md`](docs/MCP_TOOL_PROFILES.md)
- Known gaps: [`docs/KNOWN_GAPS.md`](docs/KNOWN_GAPS.md)

*ΔΣ=42*
