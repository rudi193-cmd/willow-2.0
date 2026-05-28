# Willow 2.0

**→ [Front door (GitHub Pages)](https://rudi193-cmd.github.io/willow-2.0/)** — Oden voiceover, Huginn & Muninn vox pops, dark + colorful. [`docs/LANDING_DESIGN.md`](docs/LANDING_DESIGN.md)

**Local-first memory and tools for AI agents.**

Willow keeps a knowledge graph on hardware you control, exposes it through an MCP server, and runs local inference with Ollama by default. Cloud API keys are optional. Your data stays in Postgres (desktop) or SQLite (Termux).

**Found family:** This repo is tended for the people who show up in real life — not as users, as kin. If you're **[AHS](docs/FOR_AHS.md)** (AllHailSeizure: beta reader, r/LLMPhysics, optional Necron decoder ring) or **[Felix](README-FELIX.md)** (Windows/WSL install path), those pages are your front door. Everyone else: keep reading below.

---

## What you get

| Piece | What it does |
|-------|----------------|
| **Knowledge base** | Atoms that survive across sessions, models, and IDEs |
| **SAP MCP** | ~40 tools — search memory, fleet health, tasks, handoffs, inference |
| **SAFE gate** | Every tool call checked against manifests before it runs |
| **SOIL** | Fast structured state on disk (per agent / collection) |
| **Grove** | Terminal dashboard + LAN remote control (`./willow.sh serve`) |
| **Fylgja** | Skills and powers — Markdown behaviors any model can follow |

IDEs connect via MCP (`sap/sap_mcp.py`). Humans use `./willow.sh` and the docs below.

---

## Quick start

**New here:** [`docs/FIRST_5_MINUTES.md`](docs/FIRST_5_MINUTES.md) — copy, paste, verify health.

```bash
git clone https://github.com/rudi193-cmd/willow-2.0
cd willow-2.0
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"   # omit .[dev] if you skip tests
python3 seed.py
```

Then:

```bash
./willow.sh fleet_status   # postgres, ollama, manifests
./willow.sh start          # services
./willow.sh status         # version + summary
```

**Termux:** same clone, then `python3 seed.py --termux --skip-pg` (SQLite instead of Postgres). Details in [`docs/QUICKSTART.md`](docs/QUICKSTART.md).

Default database name is **`willow_20`**. Upgrading from 1.9? See [`docs/CODE_DIFF_1.9_to_2.0.md`](docs/CODE_DIFF_1.9_to_2.0.md).

---

## Connect Cursor / Claude Code

Point MCP at `sap/willow_mcp.sh` (or follow [`docs/IDE_INTEGRATION.md`](docs/IDE_INTEGRATION.md)). Agents boot from [`willow.md`](willow.md) — health check, handoff, then act.

---

## Phone on the same Wi‑Fi (optional)

Run a signed HTTP listener on your desktop; ping it from Termux. No Discord, no cloud relay.

**Desktop:**

```bash
./willow.sh serve
# Token: ~/.willow/grove_token
```

**Phone:**

```bash
echo "TOKEN" > ~/.willow/grove_token && chmod 600 ~/.willow/grove_token
bash ~/willow-2.0/willow.sh grove send 192.168.x.x:7777 status-all
```

Use your LAN IP, not `127.0.0.1`. Full walkthrough: [`docs/FIRST_5_MINUTES.md`](docs/FIRST_5_MINUTES.md) §3.

---

## Layout (high level)

```
IDE / CLI / phone
       │
       ├── SAP MCP (stdio) ──► KB, SOIL, fleet, tasks
       │
       └── Grove serve :7777 ──► remote status / commands
                │
                ▼
         Postgres or SQLite  +  Ollama (default)
```

Repo map: [`docs/ROOT_LAYOUT.md`](docs/ROOT_LAYOUT.md). Deeper architecture: [`wiki/what-is-willow.md`](wiki/what-is-willow.md).

---

## Requirements

- Python 3.10+
- PostgreSQL 15+ with pgvector (or SQLite on Termux)
- GPG (SAFE app identity)
- [Ollama](https://ollama.com) for local inference

Optional: `./willow.sh providers enable anthropic YOUR_KEY` (or OpenAI / Gemini).

---

## Status

**Beta (2.0)** — tests and packaging are in place; wiki and archive specs may lag code. Honest gaps: [`docs/KNOWN_GAPS.md`](docs/KNOWN_GAPS.md). Audit snapshot: [`docs/BETA_AUDIT_REPORT.md`](docs/BETA_AUDIT_REPORT.md).

**Canonical repo:** `willow-1.9`, `willow-mcp`, `willow-nest`, and `willow-seed` are archived — everything ships here now. Upgrading from 1.9: [`docs/CODE_DIFF_1.9_to_2.0.md`](docs/CODE_DIFF_1.9_to_2.0.md).

---

## Documentation

| Start here | |
|------------|---|
| [FIRST_5_MINUTES.md](docs/FIRST_5_MINUTES.md) | Install and first green checks |
| [QUICKSTART.md](docs/QUICKSTART.md) | Technical onboarding |
| [CONCEPT.md](docs/CONCEPT.md) | Why local-first |
| [IDE_INTEGRATION.md](docs/IDE_INTEGRATION.md) | Cursor / Claude Code MCP |
| [INDEX.md](docs/INDEX.md) | Full doc map |

| Reference | |
|-----------|---|
| [wiki/](wiki/) | Living fleet synthesis |
| [BRANDING.md](docs/BRANDING.md) | Voice and artifact codes |
| [FOR_AHS.md](docs/FOR_AHS.md) | Beta reader guide (friend onboarding) |
| [nomenclature/](docs/nomenclature/) | Optional crossover naming (40k × LLMPhysics) |

---

## License

PolyForm Noncommercial 1.0.0 — see [`LICENSE`](LICENSE).

*Plant the tree. Tend the roots. Name the ones you love. Let nothing be lost.*
