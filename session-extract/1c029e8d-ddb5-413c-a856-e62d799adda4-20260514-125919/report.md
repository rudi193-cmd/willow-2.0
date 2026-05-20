# Session Extraction Report

- Session ID: `1c029e8d-ddb5-413c-a856-e62d799adda4`
- Source JSONL: `/home/sean-campbell/.claude/projects/-home-sean-campbell-github-willow-2-0/1c029e8d-ddb5-413c-a856-e62d799adda4.jsonl`
- Extraction folder: `/home/sean-campbell/github/willow-2.0/session-extract/1c029e8d-ddb5-413c-a856-e62d799adda4-20260514-125919`
- Records parsed: **362**
- Time range: `2026-05-14T17:23:11.679Z` → `2026-05-14T18:41:39.887Z`
- Extraction confidence: **1.00**

## Key Metrics
- Event types: `{'permission-mode': 21, 'file-history-snapshot': 30, 'user': 75, 'attachment': 27, 'ai-title': 21, 'assistant': 117, 'system': 51, 'last-prompt': 20}`
- Roles: `{'user': 75, 'assistant': 117}`
- Models: `{'claude-sonnet-4-6': 117}`
- Tool calls: `52` | inline tool results: `52`
- Backup refs: `20` total; resolved `20`, unresolved `0`

## Completeness
- Every tool call has a matching inline tool_result reference.
- All backup pointers resolved to physical files in `~/.claude/file-history`.
- Parse errors: `0`
- Count reconciliation passed: raw JSONL lines (`362`) == parsed records (`362`) == event rows (`362`).
