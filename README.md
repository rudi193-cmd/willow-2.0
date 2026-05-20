# Willow 2.0

b17: RDM20 · ΔΣ=42

Local-first AI stack · Ollama by default

---

## The demo

A phone on Termux sends a signed command to a desktop on Linux.

The answer comes back in under a second:

```
Willow 2.0 — system status

  [✓] postgres          up
  [✓] ollama            up
  [✓] grove-mcp         running
  [✓] sap_mcp.py        running
```

No Discord. No Telegram. No cloud relay. The phone read live state from your machine over the LAN — authenticated with a token that never left either device.

That is not a party trick. Run `./willow.sh serve` and it is the default.

---

## What Willow is

A local-first stack. Not a wrapper. Not a chat client.

- **Knowledge graph** — Postgres (desktop) or SQLite (Termux). Atoms persist across sessions, models, and providers.
- **Skills** — plain Markdown behaviors. Any LLM can run them.
- **SAP** — authorization gate on every tool call.
- **Grove** — messaging bus for humans and agents (sibling repo: `safe-app-willow-grove`).
- **Nodes talk directly** — HMAC-SHA256, shared token, ~100 lines of HTTP. No middleman.

**Ollama is the default.** Cloud keys (Anthropic, OpenAI, Gemini) are optional. Turn them on when you want them.

---

## Quick start

New here? [`docs/FIRST_5_MINUTES.md`](docs/FIRST_5_MINUTES.md) — copy, paste, done.

### Linux / macOS

```bash
git clone https://github.com/rudi193-cmd/willow-2.0
cd willow-2.0
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
python3 seed.py
```

`seed.py` walks you through dependencies, GPG, providers, Postgres (`willow_20`), KB seed, and PATH.

### Android / Termux

```bash
pkg install python postgresql git
git clone https://github.com/rudi193-cmd/willow-2.0
cd willow-2.0
python3 seed.py --termux --skip-pg
```

SQLite instead of Postgres. Everything else matches.

### Boot without MCP

```bash
./willow.sh fleet_status
./willow.sh handoff_latest
./willow.sh status
```

---

## Connect your phone

On the desktop:

```bash
./willow.sh serve
```

```
[grove-serve] Listening on 0.0.0.0:7777
[grove-serve] Token: ~/.willow/grove_token
```

On the phone (Termux):

```bash
echo "TOKEN" > ~/.willow/grove_token && chmod 600 ~/.willow/grove_token
bash ~/willow-2.0/willow.sh grove send 192.168.x.x:7777 status-all
```

Use the token from the desktop and your LAN IP — not `127.0.0.1`.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              USER / IDE (Cursor, Claude Code, phone)     │
└───────────────┬─────────────────────┬───────────────────┘
                │ stdio MCP           │ HTTP :7777
                ▼                     ▼
        ┌───────────────┐    ┌────────────────┐
        │  SAP MCP      │    │  Grove serve   │
        │  sap_mcp.py   │    │ grove_serve.py │
        └───────┬───────┘    └───────┬────────┘
                │                    │
                ▼                    ▼
        ┌───────────────────────────────────────┐
        │            willow.sh (CLI)             │
        └────┬──────────┬──────────┬────────────┘
             ▼          ▼          ▼
    ┌─────────────┐ ┌────────┐ ┌──────────────┐
    │ LOAM (PG/   │ │ SOIL   │ │ LiteLLM →    │
    │ SQLite KB)  │ │ store  │ │ Ollama :11434│
    └─────────────┘ └────────┘ └──────────────┘
```

| Layer | What it holds |
|-------|----------------|
| **LOAM** | Long-term KB. Bi-temporal atoms — history closes, nothing is erased. |
| **SOIL** | Session-local structured state. Fast reads and writes. |
| **SAP** | MCP server + gate. Scans outbound results for injection. |

Agents boot from [`willow.md`](willow.md). Humans boot from [`docs/FIRST_5_MINUTES.md`](docs/FIRST_5_MINUTES.md).

---

## Philosophy

> Once there was a tree that remembered everything. Not in rings and seasons — precisely.

Most AI tools store your history in a cloud you cannot audit. Willow keeps continuity on hardware you own.

Fylgja is wired in, not bolted on. Nine hard stops: child primacy, human final authority, no capture. `willow nuke` is a forensic delete. No phone home. Telemetry off unless you opt in.

---

## Requirements

- Python 3.10+
- PostgreSQL (or SQLite on Termux)
- GPG (SAFE app identity)
- Ollama (local inference, no key required)

Optional cloud: `./willow.sh providers enable anthropic YOUR_KEY`

---

## Docs

| Doc | For |
|-----|-----|
| [FIRST_5_MINUTES.md](docs/FIRST_5_MINUTES.md) | First run, no theory |
| [QUICKSTART.md](docs/QUICKSTART.md) | Technical onboarding |
| [CONCEPT.md](docs/CONCEPT.md) | Why local-first |
| [INDEX.md](docs/INDEX.md) | Full map |
| [BRANDING.md](docs/BRANDING.md) | b17 / b20 / voice schema |
| [FOR_AHS.md](docs/FOR_AHS.md) | Beta reader — start here (AHS) |
| [nomenclature/AXW-20.md](docs/nomenclature/AXW-20.md) | A×W-20 crossover naming (40k × LLMPhysics) |
| [nomenclature/AXW-20-NECRONS.md](docs/nomenclature/AXW-20-NECRONS.md) | Necron dynasty overlay (AHS) |
| [ROOT_LAYOUT.md](docs/ROOT_LAYOUT.md) | What lives at repo root |
| [CODE_DIFF_1.9_to_2.0.md](docs/CODE_DIFF_1.9_to_2.0.md) | What changed from 1.9 |
| [wiki/](wiki/) | Fleet synthesis (living) |
| [archive/docs/TECHNICAL_SPEC.md](archive/docs/TECHNICAL_SPEC.md) | Deep architecture (1.9-era, still useful) |

---

## License

PolyForm Noncommercial 1.0.0 · [`LICENSE`](LICENSE)

**Plant the tree. Tend the roots. Name the ones you love. Let nothing be lost.**
