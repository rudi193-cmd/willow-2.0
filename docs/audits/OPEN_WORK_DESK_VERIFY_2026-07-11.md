# OPEN_WORK desk verification — 2026-07-11

*Ada audit pass · fleet identity willow · verified against git history + live GitHub.*

## Scope

- **Primary doc:** `docs/OPEN_WORK.md` (curated upstream desk + internal backlog stub)
- **Reference sources:** `CONTRIBUTORS.md`, GitHub issue [#6](https://github.com/rudi193-cmd/willow-2.0/issues/6), `gh pr view`, `git log`
- **Pull performed:** `master` fast-forward `1ec2ccde` → `04aa1793` (PR #790, 2026-07-10)

## Repository state at audit

| Field | Value |
|-------|-------|
| HEAD | `04aa1793` — docs: auto-update upstream contributions tracker (#790) |
| OPEN_WORK.md last commit | `75cb2f14` — 2026-06-30 (`docs(upstream): desk touch — stash #14 open, Tauon #2208 merged`) |
| CONTRIBUTORS.md | Auto-maintained; 29+ bot PRs (#589–#790) since 2026-06-30 |
| Issue #6 | Updated 2026-07-11 by `.github/scripts/update_tracker.py` |
| willow-2.0 merges since 2026-06-30 | 127 (sample: #765–#787 Kart/watchmen/reload wave) |

## Documentation architecture (finding)

| Artifact | Update mechanism | Role |
|----------|------------------|------|
| `CONTRIBUTORS.md` | `.github/workflows/upstream-pr-check.yml` → `update_tracker.py` → bot PR | Full merged/closed ledger |
| Issue #6 | Same script | Live open/merged snapshot |
| `docs/OPEN_WORK.md` | Manual desk pass per `UPSTREAM_CONTRIBUTION_STRATEGY.md` | Curated preflight scores, lanes, desk rules |
| `docs/audits/KART_FAILURE_MODES.md` | Manual + shipping PRs | Internal Kart/watchmen queue |

**Classification:** documentation drift — not upstream state failure. Live truth is issue #6 + `CONTRIBUTORS.md`. `OPEN_WORK.md` lags because it is not wired to the bot.

## OPEN_WORK.md vs live GitHub

### Still correct (open, maintainer-blocked)

| PR | Live state (2026-07-11) |
|----|-------------------------|
| [moazbuilds/claudeclaw #234](https://github.com/moazbuilds/claudeclaw/pull/234) | OPEN — `CHANGES_REQUESTED` (stale review vs parent still applies) |
| [alash3al/stash #14](https://github.com/alash3al/stash/pull/14) | OPEN |
| [openedx/codejail #309](https://github.com/openedx/codejail/pull/309) | OPEN — `REVIEW_REQUIRED` |
| [castroquiles/glapagos #20](https://github.com/castroquiles/glapagos/pull/20) | OPEN — `REVIEW_REQUIRED` |
| [coleam00/mcp-mem0 #18](https://github.com/coleam00/mcp-mem0/pull/18) | OPEN |
| [PDFMathTranslate/PDFMathTranslate #1148](https://github.com/PDFMathTranslate/PDFMathTranslate/pull/1148) | OPEN |
| [kelos-dev/kanon #34](https://github.com/kelos-dev/kanon/pull/34) | OPEN — label gate |
| [NousResearch/hermes-agent #40737](https://github.com/NousResearch/hermes-agent/pull/40737) | OPEN — red lane |

**Actionable on us:** still **none** — all maintainer-blocked.

### Stale — doc says open/wait, actually merged

| PR | OPEN_WORK | Live | Merged |
|----|-----------|------|--------|
| [zeroc00I/DontFeedTheAI #8](https://github.com/zeroc00I/DontFeedTheAI/pull/8) | yellow, wait | **MERGED** | 2026-07-08 |
| [mex-memory/mex #84](https://github.com/mex-memory/mex/pull/84) | yellow, wait | **MERGED** | 2026-07-06 |

### Missing from OPEN_WORK — merged since 2026-06-30 desk pass

| PR | Note |
|----|------|
| [Taiko2k/Tauon #2209](https://github.com/Taiko2k/Tauon/pull/2209) | Merged 2026-07-02 — #2208 is in doc; #2209 is not |
| almanac-data org (~40+ PRs) | July propagate-engine / schema / headless-fallback wave — in `CONTRIBUTORS.md` + issue #6 |

### Missing from OPEN_WORK — open, present in issue #6

| PR | Note |
|----|------|
| [basicmachines-co/basic-memory #1010](https://github.com/basicmachines-co/basic-memory/pull/1010) | OPEN — uncredentialed project list fix |
| [castroquiles/HeatWatch #20](https://github.com/castroquiles/HeatWatch/pull/20) | OPEN — geo_utils off-by-one |

### Internal section

`OPEN_WORK.md` § Internal is a single stale provenance bullet. Does not reflect 127 willow-2.0 merges since 2026-06-30. Internal Kart/watchmen queue is tracked in `docs/audits/KART_FAILURE_MODES.md` (last touch 2026-07-08/09).

## Git history cross-check

```
OPEN_WORK.md commits (recent):
  75cb2f14 docs(upstream): desk touch — stash #14 open, Tauon #2208 merged
  f5482f53 docs(upstream): reconcile open-work desk to 2026-06-29 live state
  …
  (no commits to OPEN_WORK.md since 2026-06-30)

Upstream-related commits since 2026-06-30 (not OPEN_WORK):
  04aa1793..3a65087c  — CONTRIBUTORS bot PRs #589–#790
  bb426f08            — KART_FAILURE_MODES.md added
  404253a8, cc68511a  — KART_FAILURE_MODES updates
  #765–#787           — Kart revenge tour + watchmen (internal, not OPEN_WORK)
```

## PR #790 delta (latest pull)

Removed 11 stale **closed** rows from `CONTRIBUTORS.md` (hermes-agent, openclaw, litellm, rich, etc.). No additions — convergence cleanup only.

## Issue #6 snapshot (2026-07-11)

- **10 open** external PRs (matches `gh search prs --author rudi193-cmd --state open`)
- Merged section includes full almanac-data wave + Tauon #2208/#2209

## Recommended follow-up (not executed)

1. Manual desk touch on `docs/OPEN_WORK.md` — reconcile preflight + waiting tables to issue #6; move DontFeedTheAI #8 and mex #84 to merged; add #2209, basic-memory #1010, HeatWatch #20.
2. Optionally fold almanac desk into OPEN_WORK or cross-link issue #6 as canonical open-queue (strategy doc step 2).
3. Expand § Internal or point to `KART_FAILURE_MODES.md` for willow-2.0 shipping queue.

---

*Filed. ΔΣ=42*
