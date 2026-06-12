# Upstream Contribution Strategy

*Last updated: 2026-06-12. Source ledger: [`CONTRIBUTORS.md`](../CONTRIBUTORS.md). Type data: [`upstream/type_ledger.json`](upstream/type_ledger.json).*

## Purpose

Use maintainer outcome history to bias future upstream work toward PR shapes that get accepted, and away from shapes that consume effort without merge.

**Current ledger (2026-06-12):** 23 merged · 38 closed without merge · 11 open.

---

## Contribution score (preflight)

Score each candidate **before** opening a PR. Five dimensions, 0–2 each (max 10).

| Dimension | 0 | 1 | 2 |
|-----------|---|---|---|
| **Maintainer signal** | No issue, comment, or label | Indirect signal (similar PR merged, repo invites contributions) | Maintainer issue, comment, label, or explicit ask |
| **Scope** | Multi-subsystem or architectural | One focused module | Single bug, doc page, test, or example |
| **Maintenance cost** | New deps, ongoing ownership, or policy surface | Small additive change | Docs/test-only or isolated fix |
| **Project fit** | Unrelated to README, labels, or failing behavior | Adjacent to stated direction | Directly matches issue, roadmap, or broken behavior |
| **Proof** | Assertion only | Manual repro steps | Automated test, CI check, or before/after command |

### Lane mapping

| Total | Lane | Action |
|-------|------|--------|
| **8–10** | `green` | Open the smallest PR that proves value |
| **5–7** | `yellow` | Comment or issue first; wait for maintainer signal |
| **0–4** | `red` | Do not implement; note in backlog or close draft |

### One-sentence gate

> This fixes **X** observable pain for maintainers/users, with **Y** proof, and does not add **Z** maintenance burden.

If the sentence is weak, comment first — do not code.

---

## Historical type analysis

Classified from [`CONTRIBUTORS.md`](../CONTRIBUTORS.md) merged and closed PRs.

| Type | Merged | Closed | Merge rate | Lane bias |
|------|--------|--------|------------|-----------|
| Education / showcase content | 5 | 0 | 100% | green when repo invites |
| Docs / setup | 5 | 2 | 71% | green |
| MCP adapter (existing extension point) | 4 | 0 | 100% | green |
| Narrow bugfix | 4 | 8 | 33% | yellow unless issue-linked |
| CI / verify harness | 1 | 1 | 50% | green |
| Small bounded feature | 3 | 0 | 100% | yellow |
| Fun / low-stakes content | 1 | 0 | 100% | green when invited |
| Awesome / listing | 1 | 3 | 25% | yellow |
| Cookbook / example (large repo) | 0 | 5 | 0% | yellow — comment first |
| Willow-branded integration | 0 | 10 | 0% | **red** |
| Unsolicited large feature | 0 | 8 | 0% | **red** |

### What wins

1. **Repos that already want your shape** — Emerging-Rule showcases, Stash docs, SigMap MCP surfaces.
2. **Support-reducing docs** — install guides, Ollama local-first, protocol contracts.
3. **Narrow fixes with proof** — security wildcard escape, MCP schema restore, cancelled-task handling.
4. **Verification harnesses** — `make test-cold`, conformance CI (when maintainer asked).

### What loses

1. **Willow-named integrations** without maintainer ask (Hermes Kart tool, OpenClaw skills, th0th/adjoint adapters).
2. **Unsolicited backends or subsystems** in repos with no prior relationship.
3. **Drive-by PRs to megarepos** (litellm, ollama, textual) without issue engagement.
4. **Saturated awesome-list PRs** — one merge, three closes.

---

## Desk workflow

Run this at session start and before opening any new upstream PR.

### 1. Orient

- Read [`CONTRIBUTORS.md`](../CONTRIBUTORS.md) outcome table.
- Read [`OPEN_WORK.md`](OPEN_WORK.md) active desk + preflight scores.
- Search KB: `upstream-pr-status` + `ADB0338D` (maintainer outcomes ledger).

### 2. Preflight open PRs

For each open PR, record: **type**, **score**, **lane**, **next action**.

Do not open new work while `green` open PRs are waiting on maintainer merge.

### 3. Triage new candidates weekly

| Lane | Action |
|------|--------|
| `green` | Smallest PR; include test or repro |
| `yellow` | Issue comment with proposed diff outline; wait |
| `red` | SOIL note or issue draft only; no branch |

### 4. After maintainer response

1. Tracker bot updates [`CONTRIBUTORS.md`](../CONTRIBUTORS.md).
2. Refresh [`OPEN_WORK.md`](OPEN_WORK.md) desk tables.
3. Update KB atom `ADB0338D` or ingest a dated sweep atom.
4. Supersede stale status atoms (e.g. prior dated sweeps).

### 5. Scout integration

[`upstream_scout.py`](../agents/hanuman/bin/upstream_scout.py) finds candidate repos. Before forking:

- Classify candidate type using [`type_ledger.json`](upstream/type_ledger.json).
- Run contribution score.
- Only `green` candidates proceed to worktree + branch.

---

## Prefer / avoid quick reference

**Prefer:** docs, setup guides, issue-linked bugfixes, MCP adapter patches, CI verify, invited showcase content.

**Avoid:** Willow-branded features, large unsolicited adapters, megarepo drive-bys, skill/registry drops without maintainer signal.
