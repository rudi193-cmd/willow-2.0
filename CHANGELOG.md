# Changelog

All notable changes to Willow 2.0 are documented here. Version strings follow [`VERSION`](VERSION).

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `core/bkt.py` — Bayesian Knowledge Tracing for skill-mastery estimation. Sibling of `core/actr.py`: dependency-free (no numpy/pandas) forward filter + EM fit + RMSE/accuracy/AUC evaluation, estimating an agent's latent mastery of a skill from its outcome history. Reimplements the pyBKT (CAHLR, MIT) algorithm for Termux/Windows parity.
- `core/skill_mastery.py` — live per-skill mastery tracking built on `core/bkt.py`. Maps `core/outcomes.py` terminal results to correct/incorrect, advances mastery online, periodically refits parameters from each skill's own history, and persists one record per skill in the SOIL `bkt` collection. Read surface: `mastery()`, `all_mastery()`, `weakest()`.

## [2026.05.2] - 2026-05-31

Patch release: tag aligns with post-`2026.05.1` fleet layout, documentation, and operator tooling (#162–#167).

### Added

- `/release` skill and fylgja command symlink — full gate sequence for tagged GitHub Releases.
- Fleet layout scripts: `consolidate_github_layout.sh`, `consolidate_home_clones.py`, `audit_safe_paths.py`, `repair_safe_layout.sh`, `sync_safe_agent_manifests.py`.
- Fleet hardening scan and upstream worktree maintenance (`fleet_hardening_scan.py`, `cleanup_worktrees.sh`, `restore_upstream_worktrees.sh`).
- Doc architecture (phases A–D): `docs/CONTRACT.md`, `sap/MCP_INSTRUCTIONS.md`, handoffs archive and `docs/handoffs/` README.

### Changed

- Canonical fleet data under `~/github/`; legacy paths (`~/SAFE`, `~/willow-2.0`, `~/.willow`, `~/agents`) symlink back.
- awesome-claude-skills resolved from `~/github/awesome-claude-skills` sibling.

### Fixed

- Upstream contribution tracker: CONTRIBUTORS table conflict markers (#163).

## [2026.05.1] - 2026-05-31

First tagged release of Willow 2.0. Baseline code from the 1.9→2.0 rewrite plus the full quality audit (phases 0–3) and infrastructure hardening completed this sprint. See [`docs/CODE_DIFF_1.9_to_2.0.md`](docs/CODE_DIFF_1.9_to_2.0.md) for the full 1.9→2.0 delta.

### Added

- CI quality phases 0–3: first-party ruff scope, lint/security/pytest jobs, pre-commit config, Python 3.11/3.12 matrix, bandit enforced (HIGH gate on `core sap willow`), coverage floor (`--fail-under=10`), GitHub Release workflow.
- `CONTRIBUTING.md`, branch hygiene script (`scripts/list_stale_branches.sh`), local API docs builder (`scripts/build_api_docs.sh`).
- IDE install: canonical per-agent `settings.local.json` under `WILLOW_HOME` (symlinked from repo, never committed).
- Kart sandbox: `ANTHROPIC_` and `GROQ_` API key prefixes now injected from fleet env file.

### Changed

- `install_project` symlinks Cursor/Claude local settings to fleet home instead of writing into the repo.
- `openclaw-sap-gate` pinned to commit `710860045` (eliminates floating-HEAD supply chain risk).
- Routing intent map updated; `navigate` intent routes to `willow` (coordinator) instead of `jeles`.
- Branch protection on master requires a status check named `test` (gate job wrapping pytest-matrix).
