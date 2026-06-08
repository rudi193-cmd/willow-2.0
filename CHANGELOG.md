# Changelog

All notable changes to Willow 2.0 are documented here. Version strings follow [`VERSION`](VERSION).

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [2026.06.3] - 2026-06-08

Patch release: fleet memory audit remediation (#247) and hybrid retrieval gold-query ranking (#248).

### Added

- **Fleet memory audit (C1–C10)** — hybrid-first `kb_search`, fleet-wide intake promote, binder→`public.edges` sync, canonical quality gate, dream queue, audit close-out doc (#247).

### Fixed

- **Hybrid retrieval** — metadata-aware row text, token-filtered BM25 candidates, lexical coverage bias; audit gold queries Hit@1 (#248).
- **`app_status` MCP wiring** — inspect full command line so `bash -lc …unified_mcp.sh` apps (e.g. ask-jeles) no longer report `stale: -lc` (#248).
- **CI** — close `PgBridge` in bitemporal test fixture to prevent pytest 3.11 coverage hang (#248).

## [2026.06.1] - 2026-06-07

Patch release: canonical fleet-home remediation (#235), CI path-guard (#238), and fleet features landed since `v2026.06.0`.

### Added

- **Canonical fleet home** — `willow/fylgja/willow_home.py` resolver; `$WILLOW_HOME` (default `~/github/.willow`) replaces hardcoded `Path.home() / ".willow"` across hooks, core, SAP, scripts, and launchers (#235).
- `scripts/audit_canonical_home.sh` — operator audit for layout, symlinks, and identity matrix coherence.
- `tests/test_fylgja/test_canonical_home.py` — resolver and layout regression coverage.
- **CI path-guard** — `scripts/path_guard.sh` blocks new Python/shell hardcodes of `~/.willow` fleet-home paths (#238).
- **Portable Willow pack** — public-fallback layout for GitHub-only clones; respects explicit `WILLOW_HOME` (#232).
- **Skill mastery (BKT)** — `core/bkt.py`, `core/skill_mastery.py`, `skill_mastery` MCP tool; mastery-aware `skill_load` and drill surfacing (#231).
- **Discord remote control** — REST bridge, Ollama-backed responder, claim coordination, tier routing, KB search, restart subcommand (#220–#228).
- Stop hook auto-refreshes `current-projects` KB atom on session end (#230).
- `CODEX.md` — Codex operator contract snapshot.

### Changed

- Fleet-wide path migration: `willow_home()` / `resolve_store_root()` in Python; `${WILLOW_HOME}` in shell (`willow.sh`, `sap/willow_mcp.sh`, hooks, Kart sandbox env).
- Sleipnir install targets `private_home()` / `WILLOW_HOME`, not legacy `~/.willow` public fallback.

### Fixed

- Seed/platform: guard Linux-only `apt-get` and service calls (#229).
- Kart bwrap: `DBUS_` / `XDG_` env prefixes and `XDG_RUNTIME_DIR` bind for `systemctl --user` (#224–#225).
- Identity bind checks read disk MCP config, not stale shell `GROVE_SENDER` (#234).
- Lint/import cleanup after `willow_home` migration (#235).

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
