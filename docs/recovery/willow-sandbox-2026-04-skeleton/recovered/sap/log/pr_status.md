# PR Status Report

**Generated:** 2026-05-07T12:04:18Z

---

## Access Constraints

> The GitHub MCP server in this session is scoped exclusively to
> `rudi193-cmd/willow-1.9`. No `gh` CLI is available. All three requested PRs
> are in repositories outside that scope and return ACCESS_DENIED on every
> fetch attempt.

---

## PR: modelcontextprotocol/python-sdk #2494

| Field | Value |
|-------|-------|
| **State** | UNKNOWN — repository outside MCP scope |
| **CI checks** | UNKNOWN |
| **Reviews** | UNKNOWN |
| **Last commit SHA** | UNKNOWN |
| **Fetch error** | `Access denied: repository "modelcontextprotocol/python-sdk" is not configured for this session` |

---

## PR: punkpeye/awesome-mcp-servers #5247

| Field | Value |
|-------|-------|
| **State** | UNKNOWN — repository outside MCP scope |
| **CI checks** | UNKNOWN |
| **Reviews** | UNKNOWN |
| **Last commit SHA** | UNKNOWN |
| **Fetch error** | `Access denied: repository "punkpeye/awesome-mcp-servers" is not configured for this session` |

---

## PR: rudi193-cmd/willow-1.5 #4 *(closed without merge — tracked)*

| Field | Value |
|-------|-------|
| **State** | UNKNOWN — `willow-1.5` is outside MCP scope |
| **CI checks** | UNKNOWN |
| **Reviews** | UNKNOWN |
| **Last commit SHA** | UNKNOWN |
| **Fetch error** | `Access denied: repository "rudi193-cmd/willow-1.5" is not configured for this session` |

---

## Action Required

To enable cross-repo PR tracking, configure one of:

1. `GITHUB_TOKEN` / `GH_TOKEN` env var with `repo:read` scope and expand MCP allow-list, **or**
2. Expand MCP allow-list in session config to include the three repos above, **or**
3. Install and authenticate `gh` CLI (`gh auth login`).
