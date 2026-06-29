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
bash setup.sh --public   # or bash setup.sh when ~/github/.willow (willow-config) exists
source .venv-dev/bin/activate   # optional — ./willow.sh already uses .venv-dev
pre-commit install
pre-commit install --hook-type pre-push
```

`setup.sh` creates **`.venv-dev`** (canonical), installs `requirements.txt`, runs `pip install -e . --no-deps`, then `requirements-dev.txt`, and symlinks `$WILLOW_HOME/venv` → `.venv-dev`. Do not use a separate `.venv` — it is not wired into MCP or `./willow.sh`.

**Refresh deps manually** (avoid `pip install -e ".[dev]"` — it re-resolves runtime pins and fails on Python 3.14):

```bash
.venv-dev/bin/pip install -r requirements.txt
.venv-dev/bin/pip install -e . --no-deps
.venv-dev/bin/pip install -r requirements-dev.txt
```

If `pip check` warns `willow requires aiohttp>=3.14.1` on Python 3.14, run `bash scripts/refresh_editable_willow.sh` (refreshes editable metadata in site-packages).

**Python:** 3.11–3.13 recommended (`litellm>=1.87` needs `<3.14`; 3.14 uses litellm 1.83.x). Check: `./willow.sh venv check`.

**IDE wiring:**

```bash
./willow.sh agents active <agent-id>
./willow.sh agents install <agent-id> --ide <cursor|claude|codex>
./willow.sh agents check --ide <surface>   # --ide all only when every IDE is installed
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
| `lint` | `ruff check core sap willow tests scripts` (ruff pinned to match pre-commit) |
| `test` | pytest matrix on 3.11 + 3.12 (Postgres service); **blocked unless `lint` is green** |
| `path-guard` | legacy path scan |

Report-only in CI (artifacts, not merge blockers yet): mypy, coverage, bandit.

First-party scope excludes vendored trees (`worktrees/`, `mcp-memory-service/`, etc.) — see `pyproject.toml`.

## Pull requests

1. Branch from `master`; keep PRs focused.
2. Use the [PR template](.github/PULL_REQUEST_TEMPLATE.md).
3. Ensure required checks **`test`** and **`path-guard`** pass (exact names — branch protection depends on them). The `test` gate waits on `lint`; do not add chore lint commits to feature PRs — fix ruff on your branch before push (`bash scripts/lint_first_party.sh`).
4. Do not commit secrets, `.cursor/settings.local.json`, or machine-specific symlinks; root `willow.md` must remain a public tracked file.
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
