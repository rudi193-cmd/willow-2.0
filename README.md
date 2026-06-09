# Willow 2.0

**→ [Front door (GitHub Pages)](https://rudi193-cmd.github.io/willow-2.0/)** — Oden voiceover, Huginn & Muninn vox pops, dark + colorful. [`docs/LANDING_DESIGN.md`](docs/LANDING_DESIGN.md)

**Local-first memory and tools for AI agents.**

Willow keeps a knowledge graph on hardware you control, exposes it through an MCP server, and runs local inference with Ollama by default. Cloud API keys are optional. Your data stays in Postgres (desktop) or SQLite (Termux).

**Found family:** This repo is tended for the people who show up in real life — not as users, as kin. If you're **[AHS](docs/FOR_AHS.md)** (AllHailSeizure: beta reader, r/LLMPhysics, optional Necron decoder ring, Windows port contributor) or **[Felix](README-FELIX.md)** (Windows/WSL install path), those pages are your front door. Everyone else: keep reading below.

---

## What you get

| Piece | What it does |
|-------|----------------|
| **Knowledge base** | Atoms that survive across sessions, models, and IDEs |
| **SAP MCP** | Unified MCP with profile-filtered tools for memory, fleet health, tasks, handoffs, and inference |
| **SAFE gate** | Every tool call checked against manifests before it runs |
| **SOIL** | Fast structured state on disk (per agent / collection) |
| **Grove** | Terminal dashboard + LAN remote control (`./willow.sh serve`) |
| **Fylgja** | Skills and powers — Markdown behaviors any model can follow |
| **HNS** | Routes inference to the best available node by VRAM — activate with `WILLOW_INFERENCE_PROVIDER=hns` |

IDEs connect via MCP (`sap/sap_mcp.py`). Humans use `./willow.sh` and the docs below.

---

## Choose Your Path

| You are | Start with | What happens |
|---------|------------|--------------|
| New human or contributor | `bash setup.sh --public` | Uses only files in this public repo; no private config required |
| Fleet operator | `bash setup.sh` | Uses private `~/github/.willow` as an overlay for credentials, handoffs, and settings |
| Agent in an IDE | [`willow.md`](willow.md), then [`docs/IDE_INTEGRATION.md`](docs/IDE_INTEGRATION.md) | Boots from the public contract, then loads MCP/handoff context when available |

## Quick Start

**New here:** [`docs/FIRST_5_MINUTES.md`](docs/FIRST_5_MINUTES.md) — copy, paste, verify health.

```bash
git clone https://github.com/rudi193-cmd/willow-2.0
cd willow-2.0
bash setup.sh --public
```

Then:

```bash
./willow.sh fleet_status   # postgres, ollama, manifests
./willow.sh start          # services
./willow.sh status         # version + summary
```

**Termux:** same clone, then `python3 seed.py --termux --skip-pg` (SQLite instead of Postgres). Details in [`docs/QUICKSTART.md`](docs/QUICKSTART.md).

**Windows:** use `install-windows.ps1` and `seed-windows.py` instead. Postgres must be installed separately — `seed.py` uses `apt-get` and will not work on Windows. Details in [`docs/QUICKSTART.md`](docs/QUICKSTART.md).

Default database name is **`willow_20`**. Upgrading from 1.9? See [`docs/CODE_DIFF_1.9_to_2.0.md`](docs/CODE_DIFF_1.9_to_2.0.md).

---

## Connect Cursor / Claude Code

Install an agent profile for the IDE you actually use:

```bash
./willow.sh agents active <agent>
./willow.sh agents install <agent> --ide <cursor|claude|codex>
```

The installer writes MCP config for `sap/unified_mcp.sh`. Agents boot from [`willow.md`](willow.md), check fleet health and handoff, then act. Details: [`docs/IDE_INTEGRATION.md`](docs/IDE_INTEGRATION.md).

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

- Python 3.11+ (3.12 supported; CI matrix covers both)
- PostgreSQL 15+ with pgvector (or SQLite on Termux)
- GPG (SAFE app identity)
- [Ollama](https://ollama.com) for local inference
- **Windows:** use `install-windows.ps1` + `seed-windows.py`; `pywin32` and `windows-curses` are platform-scoped in `requirements.txt`. See [`docs/QUICKSTART.md`](docs/QUICKSTART.md).

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
| [CONTRIBUTING.md](CONTRIBUTING.md) | Dev setup, CI, releases, branch hygiene |
| [QUICKSTART.md](docs/QUICKSTART.md) | Technical onboarding |
| [CONCEPT.md](docs/CONCEPT.md) | Why local-first |
| [IDE_INTEGRATION.md](docs/IDE_INTEGRATION.md) | Cursor / Claude Code MCP |
| [INDEX.md](docs/INDEX.md) | Full doc map |
| [OPEN_WORK.md](docs/OPEN_WORK.md) | Curated open backlog |

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
