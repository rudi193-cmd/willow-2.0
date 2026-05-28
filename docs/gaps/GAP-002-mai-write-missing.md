@markdownai v1.0

# GAP-002 — mai_write_file (resolved)

| Field | Value |
|-------|-------|
| ID | GAP-002 |
| Severity | MEDIUM |
| Discovered | 2026-05-25 |
| **Status** | **Resolved** (2026-05-28) |
| Fix | `mai_write_file` in `sap/mai/tools.py`; Write/Edit redirect in `pre_tool.py` + `sap/mai/hooks/preToolUse.mjs` |

## Resolution

- **Tool:** `mai_write_file(path, content, cwd="")` on unified willow MCP (10 `mai_*` tools).
- **Hooks:** IDE Write/Edit/StrReplace on `@markdownai` `.md` → use `mai_write_file`; Read → `mai_read_file`.
- **Canonical hook:** `sap/mai/hooks/preToolUse.mjs` (copy to `~/.markdownai/hooks/` on install).

ΔΣ=42
