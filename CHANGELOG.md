# Changelog

All notable changes to Willow 2.0 are documented here. Version strings follow [`VERSION`](VERSION).

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [2026.06.6] - 2026-06-10

Audit-execution release: six of the eight SYSTEM_AUDIT_2026-06-10 action-plan PRs, the boot-order contract hardening, the upstream-tracker convergence fix, and two-way handoff notes since `v2026.06.5`.

### Added

- **System audit landed** — `docs/audits/SYSTEM_AUDIT_2026-06-10.md` at rev 8 (16 findings, autonomy map, capability inventory); finding #16: bwrap sandbox environment divergence (#308).
- **Repo-fleet hygiene sweep** — `scripts/repo_fleet_sweep.py`: diverged/unpushed repos, untracked deliverables, runtime dirt, branch litter, stash↔atom parity; `--emit-flags` into SOIL (#312).
- **Memory-stack tightening** — ratified tier requires human attestation (fail-closed); handoff completeness gate (`session_close.py --check-handoff`, wired into /shutdown); norn-pass pump at close + fleet weekly; `scripts/soil_graduate.py` (stable SOIL → intake); `scripts/audit_bitemporal.py` supersede⇔invalid_at verifier (#313).
- **Two-way handoff notes** — `## Agent Notes for Human` + `## Human Notes to Agent` in HANDOFF (and AUDIT/INVESTIGATION/TASK/DEV_LOG) templates; `handoff_latest` reads both live from the newest file so post-close operator notes surface at next boot; machine block now required (#319).
- **Kart retention sweep** — `scripts/kart_scripts_sweep.py`: auto-generated bodies >14d deleted (dry-run default), named files report-only (#311).

### Changed

- **boot-order rule hardened** — boot before any response; the agent does not classify a turn as exempt; only explicit user waiver or user emergency (#307).
- **/handoff retired** — /shutdown absorbs the handoff write as step 2; surface checks and tests track the retirement (#306).
- **Contract & docs truth** — `docs/CONTRACT.md` regenerated (mcp-first Critical, public-safety, PII clause); handoff path notation standardized to `~/.willow/`; docs INDEX gains an Audits row (#308).
- **Upstream Contribution Tracker** — single stable `bot/upstream-tracker` branch, PR reuse, no self-triggered runs, concurrency cancel; 44 stale bot branches swept (#318).

### Fixed

- **Skill sync frontmatter** — `skill_text()` recognizes `@markdownai` ahead of YAML; all four surface trees regenerated, double frontmatter and placeholder descriptions gone (#310).
- **Kart facade defects** — stdout clipped head+tail with explicit marker (was silent front-truncation), `script_body` shell shebangs rejected with a clear error, `willow_run(run_now)` returns the submitted task's own result; `gen_index.py` refuses to regenerate inside the sandbox (#311).
- **17-Questions parser** — extraction terminates at the next section instead of EOF (#319).

### Security / Privacy

- **Operator data untracked** — machine-private `settings.local.json` removed from the repo; desktop IP/username in `tools/xfer.sh` moved to env vars; kart skill examples parameterized; Desktop/Ashokoa sandbox binds demoted to `bind_try` (#309).

## [2026.06.5] - 2026-06-10

Minor release: fleet service inventory, public contract hardening, open-web search, handoff index fixes, and agent permission templates since `v2026.06.4`.

### Added

- **Fleet service inventory** — centralized `WILLOW_SYSTEMD_SERVICES` / `WILLOW_STOP_SERVICES` in `willow.sh`; `journal-watcher` unit; broader `status-all` visibility (#302).
- **Wildcard permission templates** — global MCP/native allow patterns for agent install surfaces (#300).
- **Open web search** — `willow_web_search` MCP tool (DuckDuckGo HTML, no API key) (#294).
- **Operator alert lane** — `notify-send` + `pg_notify` on human-required queue enqueue.
- **Ratatosk** — local app suite for phone and desktop (#296).
- **Nest seed** — portable Nest bootstrap from file dump (#298).
- **RH test harness** — clean vs dirty KB ingestion comparison sandbox (#297).

### Changed

- **Public Willow contract** — `mcp-first` elevated to Critical; verification-based `finish-to-completion`; new `public-safety` default-deny PII rule (#302).
- **Kart sandbox** — `/run/media` bind for removable media paths (#302).

### Fixed

- **Handoff index** — `handoff_latest` prefers newer same-day KB atoms by mtime over lexicographic id (#303).
- **Handoff index** — remove cross-agent fallbacks in `handoff_latest` (#295).
- **Jeles web search** — module-level `_SEARCH_EXECUTOR`; concurrent source dispatch with wall-clock cap (#292, #293).
- **Claude global hook** — Fylgja venv path fix (#299).
- **Kart sandbox** — fail-loud guard in `sign_manifest` for bwrap sandbox.
- **Gate** — `willow_web_search` added to `PERMISSION_GROUPS` and MCP profiles.

## [2026.06.4] - 2026-06-09

Minor release: Willow 2.0 surface integration, persona boot overlays, human-required gates, and KB ship-shape maintenance since `v2026.06.3`.

### Added

- **Willow 2.0 surfaces** — local, remote, and public agent surfaces wired through Fylgja boot and desk attention (#288).
- **Persona boot overlays** — built-in persona voice/posture overlays at boot step 7 (#289).
- **Human-required queue** — durable consent/attestation/review/onboarding queue with operator-load routing and MCP tools (#291).
- **Human attestation** — durable attestation records for elevated promotion and EdgeE-style approvals (#291).
- **KB ship-shape tooling** — preflight metrics, dry-run repair runner, quality gates, edge proposals, ship-log writer, and grouped queue reporting (#291).
- **MCP facade + profiles** — `willow_*` facade tools, core profile, retrieval gold checks, and comfort gates (#270).
- **Intake obligation field** — obligation metadata on orin classify and `intake_promote` (#252).
- **Template discovery** — cleanup and file JSONB audit tooling (#290).
- **Upstream watcher** — systemd unit and service wiring (#284).

### Changed

- **Public Willow contract** — operator anonymization and public-fallback config alignment (#287).
- **CI** — Dependabot and tracker-bot PR auto-merge (#282); path-guard and MCP registry strict checks for new human tools (#291).

### Fixed

- **Status strip** — persona file path uses `willow_home()` instead of a hardcoded fleet path (#291).

## [2026.06.3] - 2026-06-08

Patch release: fleet memory audit remediation (#247) and hybrid retrieval gold-query ranking (#248).

### Added

- **Fleet memory audit (C1–C10)** — hybrid-first `kb_search`, fleet-wide intake promote, binder→`public.edges` sync, canonical quality gate, dream queue, audit close-out doc (#247).

### Fixed

- **Hybrid retrieval** — metadata-aware row text, token-filtered BM25 candidates, lexical coverage bias; audit gold queries Hit@1 (#248).
- **`app_status` MCP wiring** — inspect full command line so `bash -lc …unified_mcp.sh` apps (e.g. ask-jeles) no longer report `stale: -lc` (#248).
- **CI** — close `PgBridge` in bitemporal test fixture to prevent pytest 3.11 coverage hang (#248).

## [2026.06.2] - 2026-06-07

Patch release: live docs alignment and Bayesian Knowledge Tracing (BKT) wiring across hooks, skill loading, and Outcomes API records (#240, #242–#246).

### Added

- **BKT priors and mastery gate** — seed priors script and `skill_mastery` integration in the skill management gate (#242).
- **BKT hook wiring** — shutdown outcomes recorded from the Stop hook, boot outcomes recorded from the PostToolUse sentinel path, and Outcomes API terminal states recorded by `skill_id` (#243, #244, #246).
- **Skill scrutiny gate** — `skill_load` annotates risky or low-mastery skills with `needs_scrutiny` (#245).

### Changed

- Live docs aligned with the `v2026.06.1` launcher and canonical fleet-home contract (#240).

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
