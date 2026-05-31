# Willow 2.0 — Quick start

Local-first AI stack. Your hardware. Your data. No API key required to begin.

Simpler path? [`FIRST_5_MINUTES.md`](FIRST_5_MINUTES.md).

---

## What you get

| Piece | Role |
|-------|------|
| **Ollama** | Default inference on your machine |
| **KB (LOAM)** | Postgres or SQLite — memory that survives sessions |
| **SAP MCP** | 40+ tools: KB, SOIL, fleet, tasks, handoffs, inference |
| **Fylgja** | Skills and powers — Markdown behaviors, any model |
| **Grove** | Terminal dashboard + LAN remote (sibling repo for full bus) |
| **SAFE gate** | Every tool call checked against manifests |

Cloud providers are optional.

---

## Install

### Linux / macOS

```bash
git clone https://github.com/rudi193-cmd/willow-2.0
cd willow-2.0
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"   # optional: pytest, ruff, mypy
python3 seed.py
```

`seed.py` sets up: deps, GPG, vault, `willow_20`, KB seed, PATH, optional Grove network URL.

### Termux

```bash
pkg install python postgresql git
git clone https://github.com/rudi193-cmd/willow-2.0
cd willow-2.0
python3 seed.py --termux --skip-pg
```

---

## First commands

```bash
./willow.sh fleet_status      # health JSON (no MCP)
./willow.sh handoff_latest      # last session handoff
./willow.sh status              # human-readable status
./willow.sh verify              # SAFE manifests
./willow.sh ledger              # FRANK chain check
```

Add a cloud provider when you want one:

```bash
./willow.sh providers enable anthropic --key YOUR_KEY
```

LAN server:

```bash
./willow.sh serve
# → 0.0.0.0:7777, token in ~/.willow/grove_token
```

---

## MCP (IDE)

**Willow server** — `sap/willow_mcp.sh` → `sap/sap_mcp.py`

```json
{
  "mcpServers": {
    "willow": {
      "command": "bash",
      "args": ["sap/willow_mcp.sh"],
      "env": {
        "WILLOW_AGENT_NAME": "your_agent",
        "WILLOW_PG_DB": "willow_20"
      }
    }
  }
}
```

Boot tools (in order): `fleet_status` → `handoff_latest` → `kb_search` on your task.

Full agent contract: [`CONTRACT.md`](CONTRACT.md) · private full: [`willow.md`](../willow.md) · [`sap/ONBOARDING.md`](../sap/ONBOARDING.md)

**Grove server** — separate repo `safe-app-willow-grove`, module `grove.mcp_local`.

---

## Skills

Built-in: `willow/fylgja/skills/`  
Powers (router): `willow/fylgja/powers/registry.json`

```bash
willow skill load system-health   # when CLI wired
```

ClawHub skills work when you install them — same Markdown contract as 1.9.

---

## Knowledge base

```bash
# CLI wrappers vary; MCP is canonical:
# kb_search, kb_ingest, kb_get
```

Search before you write. Duplicates cost everyone time.

---

## Develop

```bash
export WILLOW_AGENT_NAME=heimdallr
export WILLOW_SAFE_ROOT=$HOME/SAFE/Applications
export WILLOW_PG_DB=willow_20
export PYTHONPATH=$(pwd)

pytest
ruff check .
```

---

## What's next

- [`CONCEPT.md`](CONCEPT.md) — why local-first
- [`../wiki/`](../wiki/) — fleet synthesis
- [`CODE_DIFF_1.9_to_2.0.md`](CODE_DIFF_1.9_to_2.0.md) — 1.9 → 2.0
- [`archive/docs/TECHNICAL_SPEC.md`](../archive/docs/TECHNICAL_SPEC.md) — deep reference

---

Willow is a stack you install once. The graph grows. Skills accumulate. Nodes multiply. The foundation stays local. That is the point.

*ΔΣ=42*
