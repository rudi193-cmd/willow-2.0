# Ratatosk Local App Suite

Two-ended local-first agent console: phone (Termux) and desktop (Willow/Ratatosk), connected over a private tailnet by default.

**b17:** RATSK2 · ΔΣ=42

## Layout

| Path | Purpose |
|------|---------|
| `ratatosk/protocol/` | Versioned envelope protocol shared by phone and desktop |
| `ratatosk/transport/` | Tailnet-first Grove transport + optional relay adapters |
| `ratatosk/listener.py` | Desktop capability-gated listener |
| `ratatosk/doctor.py` | Health, trace, and panic tools |
| `termux/` | Termux-first phone runtime (CLI, GUI scaffold, Boot, Widget) |

## Quick start (desktop)

```bash
cd apps/ratatosk
pip install -e ".[dev]"

ratatosk doctor
ratatosk listen --channel dispatch
```

## Quick start (phone / Termux)

```bash
cd termux
bash install.sh
python main.py                  # terminal REPL
python main.py --listen         # Grove dispatch listener
python main.py --gui            # Termux:GUI (when termux-gui installed)
ratatosk doctor                 # via parent package on PYTHONPATH
```

## Environment

| Var | Default | Purpose |
|-----|---------|---------|
| `RATATOSK_TRANSPORT` | `tailnet` | `tailnet`, `ngrok`, `cloudflare`, `pangolin`, `funnel` |
| `RATATOSK_GROVE_TAILNET_URL` | — | Private Grove base URL on tailnet |
| `GROVE_URL` | — | Explicit override (any adapter) |
| `GROVE_TOKEN` | `~/.willow/grove_token` | Bearer auth |
| `WILLOW_AGENT_NAME` | `ratatosk` | Node identity |
| `OLLAMA_URL` | `http://localhost:11434` | Local inference |
| `RATATOSK_PUBLIC_EXPOSURE` | `0` | Set `1` only when using public relay adapters |

## Envelope format (v1)

```json
{
  "v": 1,
  "to": "ratatosk",
  "from": "phone",
  "intent": "chat",
  "prompt": "status of willow fleet",
  "reply_channel": "general",
  "mode": "ollama",
  "capabilities": ["chat"],
  "nonce": "abc123",
  "trace_id": "tr-001",
  "expires_at": "2026-06-10T02:00:00Z",
  "requires_confirm": false
}
```

High-risk intents (`run_task`, `shell`) require `requires_confirm: true` and desktop approval.
