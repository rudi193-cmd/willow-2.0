# Changelog

All notable changes to Willow 2.0 are documented here. Version strings follow [`VERSION`](VERSION).

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- CI quality phases 0–2: first-party ruff scope, lint/security jobs, pre-commit, Python 3.11/3.12 matrix, bandit report.
- `CONTRIBUTING.md`, branch hygiene script, local API docs builder, GitHub Release workflow.
- IDE install: canonical per-agent `settings.local.json` under `WILLOW_HOME` (symlinked from repo).

### Changed

- `install_project` symlinks Cursor/Claude local settings to fleet home instead of writing into the repo.

## [2026.05.1]

Baseline 2.0 beta — see git history and [`docs/CODE_DIFF_1.9_to_2.0.md`](docs/CODE_DIFF_1.9_to_2.0.md).
