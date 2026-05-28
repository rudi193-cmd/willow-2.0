# Discord Developer Portal walkthrough — Willow Mode A

**Goal:** Use the **Discord app on your phone** to talk to Willow fleet. OpenClaw runs on your **desktop** (same machine as Postgres). The Willow bridge forwards `#alerts` / `#handoffs` out and `grove:` commands in.

**Time:** ~20 minutes first time.

---

## What you are creating (three pieces)

| Piece | Where it lives | Secret? |
|-------|----------------|---------|
| **Discord application + bot** | [Discord Developer Portal](https://discord.com/developers/applications) | Bot token = password |
| **OpenClaw gateway** | Desktop `~/.openclaw/` | Reads bot token |
| **Willow bridge** | Desktop `~/.willow/openclaw_discord.json` | Channel ID only (not secret) |

You do **not** put the bot token in Willow’s repo or in Discord chat.

---

## Part 1 — Discord Developer Portal

### 1.1 Create the application

1. Open **https://discord.com/developers/applications**
2. Log in with the same Discord account you use on your phone.
3. Click **New Application** (top right).
4. Name it e.g. **Willow Fleet** (users see this name).
5. Accept the terms → **Create**.

You land on **General Information**. You can ignore most of this for now.

### 1.2 Create the bot user

1. Left sidebar → **Bot**.
2. Click **Add Bot** (or **Reset Token** if a bot already exists).
3. Set **Username** to something recognizable (e.g. `willow-fleet-bot`).

### 1.3 Enable intents (required)

Still on **Bot**, scroll to **Privileged Gateway Intents**:

| Intent | Enable? | Why |
|--------|---------|-----|
| **Message Content Intent** | **Yes** | Bot must read message text (required for OpenClaw) |
| **Server Members Intent** | Recommended | Guild allowlists / member lookups |
| **Presence Intent** | No | Not needed for Willow bridge |

Click **Save Changes** if Discord prompts you.

Without **Message Content Intent**, the bot sees empty messages and OpenClaw will not work.

### 1.4 Copy the bot token (do this once, carefully)

1. On **Bot**, find **Token**.
2. Click **Reset Token** → confirm.
3. **Copy** the token immediately. Discord shows it only once.

Store it temporarily in a password manager or a local file you will delete after setup:

```bash
# Example — on desktop only, never commit
nano ~/.willow/discord_bot_token.txt
chmod 600 ~/.willow/discord_bot_token.txt
```

**Never** paste the token in:
- Grove channels
- GitHub issues
- Discord messages
- Cursor chat logs you might share

If leaked: **Developer Portal → Bot → Reset Token** (old token dies instantly).

### 1.5 Generate invite URL (add bot to your server)

1. Left sidebar → **OAuth2** → **URL Generator**.

2. Under **SCOPES**, check:
   - `bot`
   - `applications.commands` (slash commands; OpenClaw expects this)

3. A **Bot Permissions** panel appears. Minimum for text in a private channel:

   **General**
   - View Channels

   **Text**
   - Send Messages
   - Send Messages in Threads (optional; useful for threads)
   - Read Message History
   - Embed Links
   - Attach Files

4. Copy the **Generated URL** at the bottom.

5. Paste URL in a browser → pick **your server** (create a private server first if needed: *Create My Own → For me and my friends*).

6. Click **Authorize**. Complete captcha if shown.

7. In the Discord app (phone or desktop), confirm the bot appears in the member list (offline until OpenClaw gateway runs).

### 1.6 Optional: Application ID

On **OAuth2 → General**, copy **Client ID** (Application ID). OpenClaw can use `channels.discord.applicationId` if startup is slow or rate-limited — optional for first setup.

---

## Part 2 — Discord app (phone or desktop)

### 2.1 Enable Developer Mode

1. Discord → **User Settings** (gear next to your avatar).
2. **Advanced** → turn on **Developer Mode**.

### 2.2 Copy IDs you will need

| ID | How to copy | Used for |
|----|-------------|----------|
| **Server ID** | Right-click your **server icon** (left sidebar) → **Copy Server ID** | OpenClaw guild allowlist |
| **Your User ID** | Right-click **your avatar** → **Copy User ID** | DM pairing / allowlists |
| **Channel ID** | Right-click your target **text channel** → **Copy Channel ID** | Willow `openclaw_discord.json` |

### 2.3 Create a channel for fleet traffic

On your server (private recommended):

1. Create channel e.g. **`#willow-fleet`** (text channel).
2. Right-click **`#willow-fleet`** → **Copy Channel ID** — this is the number for Willow config.

Optional: create **`#alerts`** only on Grove (Postgres); the bridge forwards Grove `#alerts` into `#willow-fleet` on Discord.

### 2.4 Channel permissions for the bot

`#willow-fleet` → **Edit Channel** → **Permissions** → add your bot role or the bot member:

- View Channel — Allow  
- Send Messages — Allow  
- Read Message History — Allow  

Or rely on server-wide permissions if the bot has them from the invite.

### 2.5 Private server: respond without @mention

By default OpenClaw only replies in guild channels when **@mentioned**. For a private `#willow-fleet` where only you and the bot post, you will want **requireMention: false** in OpenClaw config (Part 3).

---

## Part 3 — OpenClaw on the desktop

OpenClaw must run on the machine that has **Postgres** (`willow_20`) and can run `willow.sh`.

### 3.1 Install OpenClaw CLI

```bash
cd ~/github/willow-2.0
./willow.sh skills openclaw-setup --with-cli
# or: npm install -g openclaw@latest
openclaw --version
```

If CLI says **config is invalid** (`<root>: Invalid input`), repair the legacy Willow stub:

```bash
python3 scripts/setup_openclaw_skills.py --repair-config
openclaw config validate
willow skills openclaw-setup --with-cli
```

### 3.2 Put the bot token in config (env — recommended)

```bash
# In ~/.bashrc or ~/.willow/.env (gateway service reads this)
export DISCORD_BOT_TOKEN="paste_token_here"
```

Or patch config (OpenClaw 2026 style):

```bash
cat > /tmp/discord.patch.json5 <<'EOF'
{
  channels: {
    discord: {
      enabled: true,
      token: { source: "env", provider: "default", id: "DISCORD_BOT_TOKEN" },
      groupPolicy: "allowlist",
      guilds: {
        YOUR_SERVER_ID: {
          requireMention: false,
          users: ["YOUR_USER_ID"],
        },
      },
    },
  },
}
EOF
# Replace YOUR_SERVER_ID and YOUR_USER_ID before running:
openclaw config patch --file /tmp/discord.patch.json5
```

Replace `YOUR_SERVER_ID` and `YOUR_USER_ID` with the numeric IDs from Part 2 (no quotes in JSON5 keys — use the raw snowflake strings).

### 3.3 Start the gateway

```bash
openclaw gateway
# or: openclaw onboard --install-daemon  # if you want a background service
```

Bot should show **online** in Discord.

### 3.4 First contact (DM pairing vs channel)

**If you use DMs first** (OpenClaw default):

1. DM the bot from Discord.
2. It replies with a **pairing code**.
3. On desktop:
   ```bash
   openclaw pairing list discord
   openclaw pairing approve discord <CODE>
   ```

**For Willow Mode A (channel `#willow-fleet`)** you usually skip DMs and post directly in `#willow-fleet` once `requireMention: false` and guild allowlist are set.

Test in `#willow-fleet`:

```
hello
```

You should get an OpenClaw agent reply (not the Willow bridge yet — that is the next part).

---

## Part 4 — Willow Discord bridge

### 4.1 Create Willow config

```bash
cd ~/github/willow-2.0
willow.sh openclaw-discord init-config
```

Edit **`~/.willow/openclaw_discord.json`**:

```json
{
  "enabled": true,
  "discord_channel_id": "PASTE_CHANNEL_ID_FROM_PART_2",
  "discord_target": "channel:PASTE_SAME_CHANNEL_ID",
  "openclaw_agent_id": "main",
  "grove_default_channel": "general",
  "grove_forward_channels": ["alerts", "handoffs"],
  "grove_sender": "discord-bridge",
  "poll_interval_sec": 30
}
```

`discord_target` must be `channel:` + the same numeric ID.

### 4.2 Test outbound (desktop → phone)

```bash
willow.sh openclaw-discord test-discord
```

Check **`#willow-fleet`** on your phone — you should see the test message.

If this fails: OpenClaw gateway not running, wrong token, or wrong channel ID.

### 4.3 Test inbound path (Grove)

```bash
willow.sh openclaw-discord test-grove
```

Check Grove `#general` (desktop dashboard or `scripts/grove_msg.py history general`).

### 4.4 Run the bridge loop

```bash
willow.sh openclaw-discord run
```

Leave it running in a terminal (or add a user systemd unit later).

### 4.5 Test from phone

In **`#willow-fleet`** on Discord:

| Send | Expect |
|------|--------|
| `status-all` | Bot replies with desktop status output |
| `grove:general test from phone` | Message appears in Grove `#general` |
| `handoff willow` | Handoff text on Discord |

**Note:** The bridge reads **your** messages from OpenClaw **session transcripts**, not directly from Discord API. So OpenClaw gateway must process your Discord message first; then within ~30s the bridge picks it up.

---

## Part 5 — End-to-end checklist

- [ ] Application created in Developer Portal  
- [ ] Bot created, **Message Content Intent** on  
- [ ] Token copied and stored securely  
- [ ] Bot invited to server with text permissions  
- [ ] Developer Mode on, **Channel ID** copied for `#willow-fleet`  
- [ ] `DISCORD_BOT_TOKEN` set on desktop  
- [ ] OpenClaw `channels.discord` configured with guild allowlist  
- [ ] `openclaw gateway` running, bot online  
- [ ] OpenClaw replies in `#willow-fleet` to `hello`  
- [ ] `~/.willow/openclaw_discord.json` filled in  
- [ ] `willow.sh openclaw-discord test-discord` works on phone  
- [ ] `willow.sh openclaw-discord run` running  
- [ ] `status-all` from phone returns output  

---

## Troubleshooting

| Symptom | Likely fix |
|---------|------------|
| Bot offline | Start `openclaw gateway` on desktop |
| Bot sees messages but does not reply | Approve DM pairing, or fix guild allowlist / `requireMention` |
| OpenClaw replies, `grove:` does nothing | Start `willow.sh openclaw-discord run`; wait 30s |
| `test-discord` fails | Wrong `discord_channel_id`; bot lacks Send Messages in channel |
| `test-grove` fails | Postgres down; Grove schema missing |
| Token invalid | Reset token in Portal, update env, restart gateway |
| Bridge ignores commands | Message must be from **you** (user role) in OpenClaw transcript |

---

## Security reminders

- Rotate bot token if exposed.  
- Use a **private server**; do not add the bot to public servers without tightening allowlists.  
- `grove:` prefix prevents accidental Grove spam from normal chat.  
- Willow bridge only runs **allowlisted** `willow.sh` commands (`status-all`, `health`, etc.).

---

## References

- [OpenClaw Discord channel docs](https://docs.openclaw.ai/channels/discord)  
- `willow/fylgja/skills/openclaw-discord.md`  
- `scripts/openclaw_discord_bridge.py`

*ΔΣ=42*
