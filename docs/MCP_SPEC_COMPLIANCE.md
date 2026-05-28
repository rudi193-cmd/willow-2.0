# MCP spec compliance (Willow unified server)

b17: MCPCMP · ΔΣ=42

**Pinned spec:** [`sap/MCP_SPEC.lock.json`](../sap/MCP_SPEC.lock.json) → [2025-11-25 tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)

**Python SDK:** `mcp` package (`LATEST_PROTOCOL_VERSION` = `2025-11-25` in installed bindings)

Refresh local index: `./scripts/fetch_mcp_spec_index.sh` → `sap/spec/mcp-llms.txt`

---

## What we implement

| Spec feature | Willow status |
|--------------|---------------|
| Tool `name` / `description` / `inputSchema` | Yes (FastMCP) |
| Tool `title` | Yes — from `sap/mcp_enrich.py` + registry |
| Tool `annotations` (readOnly, destructive, idempotent) | Yes — inferred + registry overrides |
| Tool `_meta` (group, tier, lane, profile_min) | Yes — Willow extension for clients |
| `tools/call` execution errors (`ToolError` → `isError`) | Yes — profile blocks use `ToolError` |
| Profile filter (`WILLOW_MCP_PROFILE`) | Willow extension — not in spec |
| `fleet_tool_guide` catalog tool | Willow extension |
| `outputSchema` / `structuredContent` | Partial — only where FastMCP tools define output schemas |
| `tools/list` pagination (`cursor` / `nextCursor`) | **Gap** — single page; OK while profile &lt; ~100 tools |
| `tools.listChanged` notification | **Gap** — static tool set per process |
| `execution.taskSupport` | **Gap** — default forbidden |
| Resource / prompt capabilities | Not exposed on unified server |

---

## Registry drift

`scripts/check_mcp_registry.py` compares live tools vs `sap/mcp_registry.json`.

```bash
WILLOW_MCP_PROFILE=full python3 scripts/check_mcp_registry.py        # warn on drift
WILLOW_MCP_PROFILE=full python3 scripts/check_mcp_registry.py --strict  # fail if unregistered
```

All live tools are registered in `mcp_registry.json`. CI runs `check_mcp_registry.py --strict`.

---

## Stale surfaces to avoid

| File | Issue |
|------|--------|
| `sap/markdownai_server.mjs` | Declares `protocolVersion: 2024-11-05` — legacy Node path; unified Python MCP is canonical |

---

## Recommended next steps

1. Register remaining live tools in `mcp_registry.json` (tier + lane + description).
2. Add `outputSchema` on high-traffic tools (`fleet_status`, `kb_search`, `mai_write_file`).
3. Enable `tools/list` pagination if `full` profile is default anywhere.
4. When adding tools: update registry + run `check_mcp_registry.py --strict` locally.

## Comfort check (automated)

```bash
./scripts/comfort_check.sh --ci      # CI-safe (path-guard, registry, layout, fast tests)
./scripts/comfort_check.sh --local   # + home symlinks, systemd, agents check, ./willow.sh verify
```

CI runs `comfort_check.sh --ci` on every push (see `.github/workflows/tests.yml`).

ΔΣ=42
