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
| `RATATOSK_TRANSPORT` | `tailnet` | `tailnet`, `ngrok`, `cloudflare`, `pangolin`, `funnel` — all select a base URL only; the wire protocol is the same MCP client for every mode, `pangolin` included |
| `RATATOSK_GROVE_TAILNET_URL` | — | Private Grove base URL on tailnet |
| `GROVE_URL` | — | Explicit override (any adapter) |
| `GROVE_TOKEN` | `~/.willow/grove_token` | Bearer token for the Grove MCP server's OAuth session (see below) |
| `WILLOW_AGENT_NAME` | `ratatosk` | Node identity |
| `OLLAMA_URL` | `http://localhost:11434` | Local inference |
| `RATATOSK_PUBLIC_EXPOSURE` | `0` | Set `1` only when using public relay adapters |

## Grove transport

Ratatosk talks to Grove as an **MCP client**, not over a bespoke REST API.
The real Grove remote server (`safe-app-willow-grove`, `grove/mcp_local.py
--serve`) is an MCP streamable-HTTP server with OAuth, exposing tools —
`grove_send_message`, `grove_get_history`, `grove_list_channels`, etc. — at
`{grove_url}/mcp`. `ratatosk.transport.grove_client.GroveClient` speaks that
protocol directly (JSON-RPC `initialize` handshake, then `tools/call` per
operation) over `requests`, so no extra MCP SDK dependency is needed on
either the desktop or the Termux phone install.

`GroveClient`'s public methods are unchanged and map onto Grove MCP tools:

| `GroveClient` method | Grove MCP tool |
|---|---|
| `get_history(channel, since_id, limit)` | `grove_get_history(channel_name, limit, since_id)` |
| `post(channel, content, sender)` | `grove_send_message(channel_name, content, sender)` |
| `post_envelope(channel, envelope, sender)` | `post()` with the envelope's JSON as `content` |
| `tail_cursor(channel)` | `grove_get_history(channel_name, limit=1)`, cursor = last id |
| `list_channels()` | `grove_list_channels()` |
| `ping()` | `grove_list_channels()` as a reachability probe |

The transport-mode config (`RATATOSK_TRANSPORT` and the per-adapter
`*_URL` vars) is unchanged — it only selects which base URL becomes the MCP
endpoint. `pangolin` works the same as every other mode: URL selection
only, same MCP client underneath.

**Auth:** the OAuth bearer token obtained from Grove's `/grove-approve` flow
(see `safe-app-willow-grove/grove/mcp_auth.py`) is read from `GROVE_TOKEN`
or `~/.willow/grove_token` and sent as `Authorization: Bearer <token>` on
every MCP request. Ratatosk does not perform the OAuth dance itself — it
expects a token already minted by that flow (or dropped in by hand for
dev/testing) to be present at one of those two locations.

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
