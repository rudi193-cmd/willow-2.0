@markdownai v1.0

# GAP-002 — mai MCP has no write tool for MarkdownAI files

| Field | Value |
|-------|-------|
| ID | GAP-002 |
| Severity | MEDIUM |
| Discovered | 2026-05-25 |
| Status | **Open** |
| Affects | All agents writing to `.md` files with `@markdownai` headers |
| b17 | GAP02 ΔΣ=42 |

---

## Summary

`mai_read_file` exists in the willow MCP and is the correct tool for reading MarkdownAI documents (the `preToolUse` hook blocks the Read tool for these files and redirects to `mai_read_file`). There is no corresponding `mai_write_file` tool.

When an agent needs to write or update a MarkdownAI file, it has no sanctioned path. The Write and Edit tools require a prior Read-tool call (which is blocked by the hook), so agents fall back to Bash (`echo >>` or similar), which is incorrect tool selection.

---

## Impact

- Agents silently reach for Bash when updating MarkdownAI files (e.g. `MEMORY.md`, skill files, MarkdownAI documents in `docs/`).
- No way to update these files through the MCP layer — the hook enforces MCP for reads but leaves writes unsanctioned.
- Discovered when updating `memory/MEMORY.md` index after a correction: `mai_read_file` worked, then both Write and Edit tools blocked, then Bash was used without naming the gap.

---

## Workaround (interim)

Use Bash to write MarkdownAI files, but **name it explicitly** as using the gap workaround:

> "No `mai_write_file` tool available (GAP-002). Using Bash as interim write path."

Do not silently fall back to Bash.

---

## Resolution

Implement `mai_write_file` in the willow MCP server (`sap/mai/` or `sap/servers/`). Mirror the `mai_read_file` interface:

```
mai_write_file(path, content) → ok | error
```

The `preToolUse` hook for Write/Edit on `@markdownai` files should be updated to redirect to `mai_write_file` once it exists, or the tool should bypass the hook check if it originates from the MCP layer.

---

ΔΣ=42
