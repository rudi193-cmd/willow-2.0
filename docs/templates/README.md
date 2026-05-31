@markdownai v1.0

# Documentation templates (for agents)

**b17:** DOCTPL · ΔΣ=42

Use the right artifact for the right lifespan. Do not dump a whole session into an ADR or a handoff into a dev log.

| Lifespan | Template | Where it lives after fill |
|----------|----------|---------------------------|
| **Session** (multi-hour arc, infra, many turns) | [`DEV_LOG.template.md`](DEV_LOG.template.md) | `willow-2.0/docs/dev-log-YYYY-MM-DD-<slug>.md` |
| **Decision** (durable architecture/policy) | [`ADR.template.md`](ADR.template.md) | `willow-2.0/docs/adrs/ADR-YYYYMMDD-<slug>.md` |
| **Operator task** (Sean backlog, keys, follow-up) | [`TASK.template.md`](TASK.template.md) | `willow-config` → `~/github/.willow/tasks/T-YYYYMMDD-<slug>.md` |
| **Session continuity** (next agent boot) | [`HANDOFF.template.md`](HANDOFF.template.md) | `~/github/.willow/handoffs/<agent>/session_handoff-YYYY-MM-DD_<agent>.md` |
| **Release** (what shipped in a version/tag) | [`RELEASE.template.md`](RELEASE.template.md) | `willow-2.0/CHANGELOG.md` section or tag notes |

## Agent rules

1. **Copy the template** — duplicate file with a real name; do not edit the `.template.md` in place.
2. **Fill every section** — if N/A, write `None` or `N/A` with one line why.
3. **Receipts** — ADRs and handoffs need Grove ids and/or git SHAs; dev logs need transcript id if available.
4. **No secrets** — never paste API keys, tokens, or `drop.env` contents into docs.
5. **Repos** — contract/tasks → **willow-config**; code/docs/ADRs/dev logs → **willow-2.0** (worktree + PR unless Sean asks for direct push).
6. **One arc = one dev log** — do not create a dev log for every chat; use handoffs for routine sessions.


## MarkdownAI (mai) compliance

| Artifact | `@markdownai v1.0` | `b17:` stamp | Read tool |
|----------|-------------------|--------------|-----------|
| Dev log | **Yes** (line 1) | `DEVLOG` | `mai_read_file` only |
| ADR | **Yes** (line 1) | `ADRTL` | `mai_read_file` only |
| Handoff | **Yes** (first line of body, after YAML `---`) | `HNDOFF` | `mai_read_file` only |
| Task | **No** (plain md) | optional | normal Read/Write |
| Release fragment | **No** (paste into CHANGELOG) | n/a | n/a |
| This README | **Yes** | `DOCTPL` | `mai_read_file` only |

**Rules for filled Bifrost docs:**

1. Never remove the `@markdownai v1.0` header when copying a template.
2. Use **`mai_read_file`** (unified `willow` MCP) — not IDE Read; `preToolUse` blocks Read on `@markdownai` files.
3. Use **`mai_write_file`** for writes — IDE Write/Edit on `@markdownai` files is blocked.
4. Inline **`@db`** in body: add `| @fallback ""` (or equivalent) so DB outages do not render raw errors into the doc.
5. **`mai_` tools** live on the unified `willow` server (`sap/unified_mcp.sh`) — not a separate `markdownai` MCP entry.

## Examples (this fleet)

| Artifact | Example |
|----------|---------|
| Dev log (summary) | [`../dev-log-2026-05-27-fleet-github-layout.md`](../dev-log-2026-05-27-fleet-github-layout.md) |
| ADR | [`../adrs/ADR-20260525-post-push-stabilization.md`](../adrs/ADR-20260525-post-push-stabilization.md) |
| Task | `~/github/.willow/tasks/T-20260528-github-fleet-layout.md` |
| Handoff skill | `willow/fylgja/skills/handoff.md` (MCP sequence + KB ingest) |

## When to use what

```text
Routine coding session     → HANDOFF (+ kb_ingest via skill)
Big infrastructure move    → DEV_LOG + ADR(s) for decisions + TASK(s) for deferred ops
"Should we always do X?"   → ADR only
"Remind Sean to add keys"  → TASK only
Shipped v2.0.x on master    → RELEASE section
```
