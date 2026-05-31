# First five minutes — Willow 2.0

You will:

1. Install
2. Check health
3. Start services
4. (Optional) ping your desktop from your phone on the same Wi‑Fi

If something breaks, jump to **If something fails** at the bottom.

---

## 0) Install

Copy this block (Linux / macOS):

```bash
git clone https://github.com/rudi193-cmd/willow-2.0
cd willow-2.0
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
python3 seed.py
```

**Agents without willow-config:** read [`docs/CONTRACT.md`](CONTRACT.md) for the public fleet contract snapshot. Full operator contract lives in private **willow-config** — see [`docs/WILLOW_CONFIG.md`](WILLOW_CONFIG.md).

**Fleet operators:** clone `willow-config` to `~/github/.willow`, then run `bash setup.sh` so `willow.md` symlinks correctly.

**Optional — pre-commit hooks** (ruff + path guard; mypy on push):

```bash
pip install -e ".[dev]"
pre-commit install
pre-commit install --hook-type pre-push
```

**What you should see:** setup steps scrolling, then your shell prompt back. No panic unless it stops with an error.

Default database name is **`willow_20`**. If you still have `willow_19` from an old install, see [`CODE_DIFF_1.9_to_2.0.md`](CODE_DIFF_1.9_to_2.0.md).

---

## 1) Check status

```bash
./willow.sh fleet_status
./willow.sh status
```

**Good:** JSON or lines with `[✓]` on postgres, ollama, manifests.  
**Bad:** `degraded`, `not_connected`, or a traceback — stop and fix before step 2.

---

## 2) Start Willow

```bash
./willow.sh start
```

Leave that terminal open if it streams logs. Open a second terminal for the next steps.

---

## 3) Optional — phone on same Wi‑Fi

### Desktop

```bash
./willow.sh serve
```

Note the listening port (usually `7777`) and `~/.willow/grove_token`.

### Phone (Termux)

```bash
pkg install python git
git clone https://github.com/rudi193-cmd/willow-2.0
cd willow-2.0
python3 seed.py --termux --skip-pg
```

Copy the desktop token:

```bash
echo "TOKEN" > ~/.willow/grove_token && chmod 600 ~/.willow/grove_token
```

Ask the desktop for status (replace IP):

```bash
bash ~/willow-2.0/willow.sh grove send 192.168.x.x:7777 status-all
```

**Good:** your desktop’s status printed on the phone.

---

## Optional — IDE (Cursor / Claude Code)

Copy [`.mcp.json.example`](../.mcp.json.example) to `.mcp.json`. Set:

- `WILLOW_AGENT_NAME` — your agent id (e.g. `heimdallr`)
- `WILLOW_PG_DB` — `willow_20`

Launchers:

- `sap/willow_mcp.sh` — Willow tools
- `sap/markdownai_mcp.sh` — reads `willow.md` and skills

Details: [`IDE_INTEGRATION.md`](IDE_INTEGRATION.md)

---

## Optional — cloud model

Not required. Ollama is enough to start.

```bash
./willow.sh providers enable anthropic --key YOUR_KEY
./willow.sh providers list
```

---

## Where your data lives

| Path | What |
|------|------|
| `~/.willow/` | Local Willow home |
| `~/.willow/store/` | SOIL collections |
| `~/.willow/grove_token` | LAN pairing secret |
| Postgres `willow_20` | KB atoms (desktop) |

Nothing uploads by default.

---

## If something fails

**Wrong folder**

```bash
pwd && ls willow.sh seed.py
```

**Postgres down**

```bash
python3 seed.py
```

**Phone cannot connect**

- Same Wi‑Fi as desktop
- `./willow.sh serve` still running
- LAN IP, not `127.0.0.1`
- `chmod 600 ~/.willow/grove_token`

**Tests or agents complain about identity**

```bash
export WILLOW_AGENT_NAME=your_agent
export WILLOW_SAFE_ROOT=$HOME/SAFE/Applications
```

---

*ΔΣ=42*
