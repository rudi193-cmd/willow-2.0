# Cross-Session Delta Report

## Sessions Compared
- target: `1c029e8d-ddb5-413c-a856-e62d799adda4`
- candidate: `011197fb-3827-400f-9d67-378ffa5c256f`
- baseline: `fe5fba38-d8f1-49b5-8fa6-a01bea6b37d0`

## Time Windows
- baseline: `2026-05-14T07:45:44.938Z` → `2026-05-14T07:58:39.992Z`
- candidate: `2026-05-14T18:21:39.990Z` → `2026-05-14T18:21:46.847Z`
- target: `2026-05-14T17:23:11.679Z` → `2026-05-14T18:41:39.887Z`

## Startup/Hooks Drift
### baseline → target
- `hook_cancelled`: 3 → 14 (delta +11)
### candidate → target
- `hook_cancelled`: 0 → 14 (delta +14)

## MCP Instruction Delta (addedNames)
### baseline → target
- No MCP added-name drift detected.
### candidate → target
- No MCP added-name drift detected.

## Tool Surface/Usage Drift
### baseline → target
- `AskUserQuestion`: 0 → 3 (delta +3)
- `Bash`: 13 → 6 (delta -7)
- `Edit`: 0 → 24 (delta +24)
- `Read`: 6 → 11 (delta +5)
- `Skill`: 1 → 0 (delta -1)
- `Write`: 3 → 8 (delta +5)
### candidate → target
- `AskUserQuestion`: 0 → 3 (delta +3)
- `Bash`: 0 → 6 (delta +6)
- `Edit`: 0 → 24 (delta +24)
- `Read`: 0 → 11 (delta +11)
- `Write`: 0 → 8 (delta +8)

## Event Shape Drift
### baseline → target
- `ai-title`: 10 → 21 (delta +11)
- `assistant`: 63 → 117 (delta +54)
- `attachment`: 12 → 27 (delta +15)
- `file-history-snapshot`: 17 → 30 (delta +13)
- `last-prompt`: 9 → 20 (delta +11)
- `permission-mode`: 10 → 21 (delta +11)
- `system`: 31 → 51 (delta +20)
- `user`: 40 → 75 (delta +35)
### candidate → target
- `ai-title`: 0 → 21 (delta +21)
- `assistant`: 2 → 117 (delta +115)
- `attachment`: 5 → 27 (delta +22)
- `file-history-snapshot`: 1 → 30 (delta +29)
- `last-prompt`: 1 → 20 (delta +19)
- `permission-mode`: 2 → 21 (delta +19)
- `system`: 2 → 51 (delta +49)
- `user`: 2 → 75 (delta +73)

## Summary
- Target session shows a much larger tool-use footprint than both comparison sessions.
- MCP instruction names are stable at the high level (`claude.ai Grove`, `grove`, `willow`) versus candidate, and changed versus baseline where `openclaw` also appeared.
- Hook profile differs materially: target has many `hook_cancelled` + stop summaries while baseline has startup hook success/context blocks.

## Gap Closure Notes
- Backup resolution gap is closed: previous unresolved refs were due to scanning `~/.claude/projects`; canonical backup store is `~/.claude/file-history/<session-id>/`.
- Re-check confirms all 20 backup refs for target session resolve under `~/.claude/file-history/1c029e8d-ddb5-413c-a856-e62d799adda4/`.
- MCP added-name drift remained stable for target vs candidate; baseline had historical `openclaw` in neighboring sessions but not as a target-session delta for these two files.
