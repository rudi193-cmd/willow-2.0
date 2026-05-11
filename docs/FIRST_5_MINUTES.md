## Willow 1.9 — First 5 Minutes

You are going to:

- Install Willow
- Confirm it’s healthy
- Start it
- (Optional) check it from your phone on the same Wi‑Fi

If anything goes wrong, jump to **If something fails** at the bottom.

---

## 0) Install (Linux / macOS)

Copy/paste this whole block:

```bash
git clone https://github.com/rudi193-cmd/willow-1.9
cd willow-1.9
python3 root.py
```

### What you should see

- A bunch of setup steps running.
- When it finishes, you get your normal prompt back.

---

## 1) Check status

Copy/paste:

```bash
./willow.sh status
```

### What you should see

- A short status report.
- If most items show `[✓]`, you’re good.

---

## 2) Start Willow

Copy/paste:

```bash
./willow.sh start
```

### What you should see

- Output indicating services started.
- If it stays attached and keeps printing logs, leave it running in that terminal and open a new one for the next steps.

---

## 3) Optional: check your computer from your phone (same Wi‑Fi)

This lets your phone ask your computer “are you up?” without Discord/Telegram/cloud relays.

### On your computer

Copy/paste:

```bash
./willow.sh serve
```

### What you should see

- A line that it’s listening on `:7777`
- A token file location like `~/.willow/grove_token`

Leave this running.

### On your phone (Android + Termux)

Install Termux (F‑Droid recommended), then:

```bash
pkg install python git
git clone https://github.com/rudi193-cmd/willow-1.9
cd willow-1.9
python3 root.py --termux --skip-pg
```

Copy the token from your computer into the phone:

```bash
echo "TOKEN" > ~/.willow/grove_token && chmod 600 ~/.willow/grove_token
```

Ask your computer for status (replace the IP):

```bash
bash ~/willow-1.9/willow.sh grove send <COMPUTER_IP>:7777 status-all
```

### What you should see

- Your computer’s status printed on the phone.

---

## Optional: connect Grove to claude.ai (external tunnel)

By default Grove MCP runs on `localhost:8765` — Claude Code sessions on this machine connect automatically. To reach it from claude.ai or any external client, you need a tunnel.

**Step 1** — Start an ngrok tunnel:
```bash
ngrok http 8765
# → https://your-id.ngrok-free.app
```

**Step 2** — Tell the Grove MCP service about the tunnel URL (persists across reboots):
```bash
systemctl --user edit grove-mcp
```
Add:
```ini
[Service]
Environment=GROVE_MCP_URL=https://your-id.ngrok-free.app
```
Then: `systemctl --user restart grove-mcp`

**Step 3** — In claude.ai → Settings → Integrations → MCP servers, add:
```
https://your-id.ngrok-free.app/mcp
```

Each user sets their own tunnel URL. No shared hardcoded value — the service file is the only place it lives.

---

## Optional: enable a cloud model key

Willow works without cloud keys. If you *want* to add one:

```bash
./willow.sh providers enable anthropic --key <your_key>
./willow.sh providers list
```

---

## Where your data lives (plain English)

- `~/.willow/` — your local Willow data folder
- `~/.willow/store/` — local “state + memory” store
- `~/.willow/grove_token` — the secret your phone uses to talk to your computer

Nothing is uploaded by default.

---

## If something fails

### “Command not found” / wrong folder

Make sure you’re inside the `willow-1.9` folder:

```bash
pwd
ls
```

You should see `willow.sh` and `root.py`.

### Status shows Postgres down

Re-run the installer:

```bash
python3 root.py
```

### Phone can’t connect

- Make sure phone + computer are on the same Wi‑Fi
- Make sure `./willow.sh serve` is still running on the computer
- Make sure you used the computer’s LAN IP (not `127.0.0.1`)
- Re-check token file permissions on the phone: `chmod 600 ~/.willow/grove_token`

