@markdownai v1.0

<!--
AGENT INSTRUCTIONS
- Use for: KB atom candidates, SOIL memory notes, journal entries before kb_ingest / intake_write.
- Save as: draft locally or ingest directly; optional mirror at willow-2.0/docs/atoms/YYYY-MM-DD-<slug>.md
- Required: title, summary, structured content JSON, destination choice (KB vs SOIL vs intake).
- Do not store secrets, tokens, or drop.env contents.
- MarkdownAI: keep @markdownai v1.0 line 1. Read with mai_read_file; write with mai_write_file.
-->

# Atom Candidate — <title>

**b17:** ATOM · ΔΣ=42

**Date:** YYYY-MM-DD  
**Agent:** <agent_id>  
**Destination:** knowledge | soil | intake | ledger-only

## Title

<short searchable title>

## Summary

~500 chars: durable fact, decision, or procedure worth retrieving later.

## Content

```json
{
  "summary": "",
  "category": "",
  "source_type": "session|audit|investigation|decision|procedure",
  "tags": [],
  "open_threads": [],
  "agreements": [],
  "key_actions": [],
  "next_steps": [],
  "signals": {"health": "ok", "grove": "up"},
  "receipts": {
    "grove": null,
    "git": null,
    "related_docs": []
  }
}
```

## Why This Atom

- Retrieval value:
- Authority / freshness:
- Supersedes:

## Ingest Path

| Destination | Tool | Notes |
|-------------|------|-------|
| KB | `kb_ingest` | durable fleet memory |
| SOIL | `soil_put` | mutable working state |
| Intake | `intake_write` | staged promotion |
| Ledger | `ledger_write` | session receipt only |

## Receipts

| Type | Ref |
|------|-----|
| Ingested id | |
| Related handoff | |
| Related ADR | |

---

*b17: ATOM · ΔΣ=42*
