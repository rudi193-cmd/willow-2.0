@markdownai v1.0

<!--
AGENT INSTRUCTIONS
- Use for: structured audits, fleet health reviews, subsystem assessments, post-incident reviews.
- Save as: willow-2.0/docs/audits/<TOPIC>_AUDIT_YYYY-MM-DD.md
- Mode: read-only unless USER explicitly authorizes fixes in the same session.
- Required: live inventory table, working/degraded split, receipts (tool calls, SHAs, Grove ids).
- Link related ADRs or dev logs; do not duplicate decision prose here.
- MarkdownAI: keep @markdownai v1.0 line 1. Read with mai_read_file; write with mai_write_file.
-->

# <Topic> Audit

**b17:** AUDIT · ΔΣ=42

**Date:** YYYY-MM-DD  
**Agent:** <agent_id>  
**Mode:** read-only audit | audit + remediation  
**Scope:** <subsystem, repo, or fleet area>

## Executive Summary

2–4 sentences: what was audited, overall health, and the single highest-priority finding.

## Live Inventory

| Area | Observed state |
|------|----------------|
| | |

## Working Well

- 

## Degraded or Not Working

| Issue | Impact |
|-------|--------|
| | |

## Findings

### Finding 1 — <title>

**Severity:** low | medium | high | critical  
**Evidence:** <tool output, file path, count, error>  
**Recommendation:** <one concrete next bite>

## Resolution / Follow-up

| Action | Owner | Target |
|--------|-------|--------|
| | | |

## Receipts

| Type | Ref |
|------|-----|
| Grove | `#channel` message id `…` |
| Git | `<repo>` commit `…` |
| Tools | `willow_status`, `kb_search`, … |
| Related | `docs/audits/…`, ADR-… |

---

*b17: AUDIT · ΔΣ=42*

## Agent Notes for Human

<!-- reminders, to-do's, stated unfinished tasks, patterns surfaced — max 17 lines -->

-

## Human Notes to Agent

<!-- operator writes here after review -->

-
