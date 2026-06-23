# How to Add a New MCP Tool

Willow exposes MCP tools through `sap/sap_mcp.py` with domain prefixes and SAFE
gate checks. Use this pattern when adding a tool to an existing domain.

## 1. Pick your domain

Tools are grouped by prefix in [`sap/mcp_registry.json`](../sap/mcp_registry.json):

| Prefix | Domain |
|--------|--------|
| `kb_` | Knowledge base (Postgres) |
| `soil_` | Structured session state |
| `fleet_` | Node health, reload, status |
| `agent_` | Dispatch and Kart queue |
| `fork_` | Bounded work units |
| `mem_` | Jeles / binder / ratify |
| `handoff_` | Cross-session continuity |
| `infer_` | Local/cloud inference |
| … | See registry for the full list |

## 2. Template

```python
@mcp.tool()
@sap_gate("<domain>")
async def kb_example(app_id: str, query: str) -> dict:
    """One-line purpose shown in the tool picker."""
    # 1. Validate inputs
    # 2. Call pg_bridge / store / KB adapter (not raw WillowStore)
    # 3. Return a small dict — no secrets, no huge payloads
    return {"status": "ok", "data": result}
```

Register the tool in `sap/mcp_registry.json` when you add a new public name.

## 3. Safety checklist

- [ ] Tool is behind `@sap_gate("<domain>")`
- [ ] Input validation happens before any DB write
- [ ] Failures are logged (`core.safe_ops.safe_db_op` or explicit `logger.exception`)
- [ ] No silent `except: pass` on persistence paths
- [ ] HTTP MCP: set `WILLOW_MCP_API_KEY` when not on loopback (see `sap/security_middleware.py`)

## 4. Testing

```bash
cd /path/to/willow-2.0
.venv-dev/bin/python -c "from sap import sap_mcp  # noqa: F401 — import smoke"
.venv-dev/bin/pytest tests/test_mcp_domains.py -q
```

Add focused tests beside the domain you touched.

## 5. Submit

Open a PR: `feat(sap): add <prefix>_<name> tool`

Include a two-sentence summary: what the tool does, and why it is safe under the
SAFE gate.
