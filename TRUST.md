# Trust — Willow 2.0 public

**Short answer:** By default, nothing leaves your machine.

## What stays local

| Data | Where |
|------|--------|
| Knowledge atoms (memory) | Postgres on your machine (Docker `willow-db` or system Postgres) |
| SOIL / session state | Under your Willow home (`.willow/generated` in public mode) |
| Chat in the public demo | Loopback only (`127.0.0.1`) — not sent to Willow's servers (there are none) |

## What can leave your machine (opt-in only)

| Feature | When data leaves |
|---------|------------------|
| Cloud inference (Groq, OpenRouter, Anthropic, etc.) | Only if you set API keys and call those providers |
| Ollama | Stays local; optional for richer chat after demo |
| MCP HTTP mode | Only if you bind beyond loopback without `WILLOW_MCP_API_KEY` (warned in logs) |
| Grove LAN / u2u | Only if you explicitly enable remote Grove pairing |

## Demo mode honesty

`python willow-launcher.py` seeds **demo memory** so you can feel retrieval before you write anything real. The UI and terminal state this clearly. Your memory starts when you chat for real.

## Verify the code

- Source: [github.com/rudi193-cmd/willow-2.0](https://github.com/rudi193-cmd/willow-2.0)
- Agent manifests: `./willow.sh verify` (GPG signatures when manifests are signed from a host terminal)
- HTTP API key gate: `sap/security_middleware.py` when `WILLOW_MCP_API_KEY` is set

## Docker

The public quickstart runs Postgres in a local container (`willow-db`). Data volumes stay on your disk under Docker's volume store (`pgdata`). No Willow cloud receives it.

*ΔΣ=42*
