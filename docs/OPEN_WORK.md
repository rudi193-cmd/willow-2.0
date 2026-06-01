# Open work (curated)

b17: OPWORK · ΔΣ=42

**Not install blockers.** This page tracks fleet backlog items that are open but not broken in `master`. For engineering gaps (something misleads or fails today), see [`KNOWN_GAPS.md`](KNOWN_GAPS.md). For human ratifications (R1–R9), see [`../wiki/active-decisions.md`](../wiki/active-decisions.md).

Curators: update when a handoff closes a thread or Sean ratifies a decision. Do not dump raw handoff files here.

---

## Near term

| Item | Notes |
|------|--------|
| Skill catalog phase 3 | After quality audit; see [`SKILL_SURFACE_STRATEGY.md`](SKILL_SURFACE_STRATEGY.md) |
| Enforced mypy / coverage / bandit | CI report-only today; pick thresholds when baselines shrink |
| LoCoMo Path A memory v2 | **Phase 1 shipped** in `~/Desktop/Nest/locomo_memory.py` — dated atoms, session summaries, hybrid retrieval; re-run Haiku on host with `--memory-profile v2 --force-ingest` |

---

## Cross-runtime / ops

| Item | Notes |
|------|--------|
| teachers-app redirect loop | HTTP + localStorage `cos_config`; devtools investigation |
| teachers-app git | No remote; mostly untracked |
| Upstream PR #5 (claude-deep-review) | Awaiting re-review |
| GEMINI_API_KEY | Deferred — Groq + Ollama sufficient |
| Bulk branch delete | `scripts/list_stale_branches.sh` lists only; ~88+ remotes |
| `openclaw_discord_watch.py` | Untracked; ship or ignore |

---

## Documentation hygiene

Phases A–D merged (PR #162). Follow-ups landed: `docs/CONTRACT.md`, MCP instruction split (`sap/MCP_INSTRUCTIONS.md`), handoffs archived + `docs/handoffs/` gitignored. Upstream tracker fix: PR #163.

| Item | Notes |
|------|--------|
| Worktree maintenance scripts | `scripts/cleanup_worktrees.sh`, `restore_upstream_worktrees.sh`, `upstream_worktree_allowlist.txt` |
| `scripts/fleet_hardening_scan.py` | Operator scan — run before release cut |

---

*Last curated: 2026-05-31 · releases `v2026.05.1` + `v2026.05.2` shipped*

*ΔΣ=42*
