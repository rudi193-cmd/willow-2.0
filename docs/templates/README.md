@markdownai v1.0

# Documentation templates (for agents)

**b17:** DOCTPL · ΔΣ=42

**Canonical router for agent-written artifacts.** Copy a template, fill it, save to the destination path. Do not edit `.template.md` files in place.

**Discovery paths:** [`docs/INDEX.md`](../INDEX.md) · [`AGENTS.md`](../../AGENTS.md) · boot step 12 in [`willow/fylgja/skills/boot.md`](../../willow/fylgja/skills/boot.md)

---

## Prose artifact templates (copy/paste)

| Lifespan | Template | Where it lives after fill |
|----------|----------|---------------------------|
| **Session continuity** | [`HANDOFF.template.md`](HANDOFF.template.md) | `~/github/.willow/handoffs/<agent>/session_handoff-YYYY-MM-DD_<agent>.md` |
| **Multi-hour arc** | [`DEV_LOG.template.md`](DEV_LOG.template.md) | `willow-2.0/docs/dev-log-YYYY-MM-DD-<slug>.md` |
| **Architecture decision** | [`ADR.template.md`](ADR.template.md) | `willow-2.0/docs/adrs/ADR-YYYYMMDD-<slug>.md` |
| **Operator task** | [`TASK.template.md`](TASK.template.md) | `willow-config` → `~/github/.willow/tasks/T-YYYYMMDD-<slug>.md` |
| **Audit / review** | [`AUDIT.template.md`](AUDIT.template.md) | `willow-2.0/docs/audits/<TOPIC>_AUDIT_YYYY-MM-DD.md` |
| **Debug / root cause** | [`INVESTIGATION.template.md`](INVESTIGATION.template.md) | `willow-2.0/docs/investigations/YYYY-MM-DD-<slug>.md` |
| **Grove decision** | [`GROVE_DECISION.template.md`](GROVE_DECISION.template.md) | Grove post + optional `docs/decisions/…` mirror |
| **KB / SOIL atom** | [`ATOM.template.md`](ATOM.template.md) | ingest via `kb_ingest` / `soil_put` / optional `docs/atoms/…` |
| **PR / worktree** | [`PR_WORKTREE.template.md`](PR_WORKTREE.template.md) | `docs/worktrees/…` or PR description draft |
| **Release** | [`RELEASE.template.md`](RELEASE.template.md) | `willow-2.0/CHANGELOG.md` section or tag notes |

### By lifecycle

| Phase | Reach for |
|-------|-----------|
| Boot / continuity | HANDOFF |
| Long implementation session | DEV_LOG |
| Durable policy | ADR |
| Fleet/subsystem review | AUDIT |
| Single bug or hypothesis | INVESTIGATION |
| Ratified human/agent decision | GROVE_DECISION |
| Memory to retrieve later | ATOM |
| Branch ready for PR | PR_WORKTREE |
| Deferred operator action | TASK |
| Version ship | RELEASE |

---

## Runtime / config templates (install renders — do not copy as prose)

These live under `willow/fylgja/config/` and are rendered by `install_project` / `setup.sh`. They are **not** agent-authored markdown artifacts.

| Canonical source | Purpose | Rendered to |
|------------------|---------|-------------|
| [`mcp.template.json`](../../willow/fylgja/config/mcp.template.json) | Unified MCP server config | `agents/<agent>/config/mcp.json`, IDE symlinks |
| [`codex-mcp.toml.template`](../../willow/fylgja/config/codex-mcp.toml.template) | Codex MCP fragment | `~/.codex/config.toml` |
| [`fleet.env.example`](../../willow/fylgja/config/fleet.env.example) | Private-mode env bootstrap | `$WILLOW_HOME/env` |
| [`public/env.example`](../../willow/fylgja/config/public/env.example) | Public-fallback env | `$WILLOW_HOME/env` |
| [`public/settings.local.json`](../../willow/fylgja/config/public/settings.local.json) | Safe IDE permissions | `$WILLOW_HOME/agents/<agent>/settings.local.json` |
| [`cursor-hooks.json`](../../willow/fylgja/config/cursor-hooks.json) | Cursor hook wiring | `.cursor/hooks.json` |
| [`claude-settings.json`](../../willow/fylgja/config/claude-settings.json) | Claude Code settings | `.claude/settings.json` |
| [`ide-manifest.json`](../../willow/fylgja/config/ide-manifest.json) | IDE template index | referenced by install |

**Deprecated / duplicate examples (do not treat as canonical):**

| Path | Status |
|------|--------|
| `.mcp.json.example` | legacy example; prefer `mcp.template.json` |
| `agents/willow/config/mcp.json.example` | legacy example; prefer `mcp.template.json` |

**GitHub workflow templates (not in this folder):**

| Path | Use |
|------|-----|
| [`.github/PULL_REQUEST_TEMPLATE.md`](../../.github/PULL_REQUEST_TEMPLATE.md) | PR body scaffold |
| [`.github/ISSUE_TEMPLATE/`](../../.github/ISSUE_TEMPLATE/) | bug/feature issue forms |

---

## Extension slot (reserved)

Reserved for a future template not yet ratified. When added, register it in:

1. this README table
2. [`docs/INDEX.md`](../INDEX.md) templates section
3. [`scripts/index_annotations.json`](../../scripts/index_annotations.json)

Do not invent ad-hoc template locations outside `docs/templates/` without updating those three files.

---

## Agent rules

1. **Copy the template** — duplicate with a real name; do not edit `.template.md` in place.
2. **Fill every section** — if N/A, write `None` or `N/A` with one line why.
3. **Receipts** — ADRs, audits, handoffs, and Grove decisions need Grove ids and/or git SHAs.
4. **No secrets** — never paste API keys, tokens, or `drop.env` contents into docs.
5. **Repos** — contract/tasks → **willow-config**; code/docs/ADRs/dev logs → **willow-2.0**.
6. **One arc = one dev log** — routine sessions use HANDOFF; investigations use INVESTIGATION before escalating to AUDIT or ADR.

## MarkdownAI (mai) compliance

| Artifact | `@markdownai v1.0` | `b17:` stamp | Read tool |
|----------|-------------------|--------------|-----------|
| Dev log | Yes (line 1) | `DEVLOG` | `mai_read_file` |
| ADR | Yes (line 1) | `ADRTL` | `mai_read_file` |
| Handoff | Yes (body line 1) | `HNDOFF` | `mai_read_file` |
| Audit | Yes (line 1) | `AUDIT` | `mai_read_file` |
| Investigation | Yes (line 1) | `INVEST` | `mai_read_file` |
| Grove decision | Yes (line 1) | `GROVED` | `mai_read_file` |
| Atom | Yes (line 1) | `ATOM` | `mai_read_file` |
| PR / worktree | Yes (line 1) | `PRWT` | `mai_read_file` |
| Task | No (plain md) | optional | normal Read/Write |
| Release fragment | No | n/a | n/a |
| This README | Yes | `DOCTPL` | `mai_read_file` |

## When to use what

```text
Routine coding session      → HANDOFF (+ handoff skill sequence)
Big infrastructure move     → DEV_LOG + ADR(s) + TASK(s)
Subsystem / fleet review    → AUDIT
Single bug / repro          → INVESTIGATION
Ratified decision in Grove  → GROVE_DECISION (+ ADR if durable)
Durable memory to retrieve  → ATOM → kb_ingest / soil_put
Branch ready for review     → PR_WORKTREE
"Remind USER to add keys"   → TASK
Shipped v2.0.x on master    → RELEASE
```

## Examples (this fleet)

| Artifact | Example |
|----------|---------|
| Dev log | [`../dev-log-2026-05-27-fleet-github-layout.md`](../dev-log-2026-05-27-fleet-github-layout.md) |
| ADR | [`../adrs/ADR-20260525-post-push-stabilization.md`](../adrs/ADR-20260525-post-push-stabilization.md) |
| Audit | [`../audits/WILLOW_KB_MCP_AUDIT_2026-06-08.md`](../audits/WILLOW_KB_MCP_AUDIT_2026-06-08.md) |
| Handoff skill | [`willow/fylgja/skills/handoff.md`](../../willow/fylgja/skills/handoff.md) |
| Handoff template | [`HANDOFF.template.md`](HANDOFF.template.md) |

*ΔΣ=42*
