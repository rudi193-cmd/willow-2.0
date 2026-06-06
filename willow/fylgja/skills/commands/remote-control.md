---
name: remote-control
description: Start Discord remote control — phone ↔ Claude Code CLI via Discord REST bridge
skill_args: $ARGUMENTS
---

# /remote-control

Connects this Claude Code session to Discord so Sean can send commands from his phone and see responses.

## What this does

1. Starts `scripts/discord_remote.py run` as a background daemon (if not already running)
2. Posts a "remote control online" message to Discord
3. Enters a polling loop: checks Grove `hanuman` for inbound commands from `discord-bridge`, processes each one, posts the response back to Grove so the bridge forwards it to Discord

## Steps

### 1. Start the bridge daemon

Submit a background kart task to start the bridge if not already running:

```
agent_task_submit(
  task="cd ~/github/willow-2.0 && source ~/github/.willow/env && python3 scripts/discord_remote.py status || python3 scripts/discord_remote.py run --interval 30 &",
  app_id="hanuman"
)
```

Check `discord_remote.py status` first — if already running, skip the start.

### 2. Announce online

Post to Grove `hanuman` as `hanuman`:
```
grove_send_message(channel="hanuman", text="remote-control online — listening for Discord commands")
```

The bridge will forward this to Discord within 30 seconds.

### 3. Poll loop

Use `grove_get_history(channel_name="hanuman", limit=20, since_id=<cursor>)` to check for new messages.

For each message where `sender == "discord-bridge"`:
- Strip the `[Discord/<username>] ` prefix to get the raw command
- Process it: answer questions, run fleet checks, execute tasks
- Post the response to Grove `hanuman` as sender `hanuman`
  - The bridge picks this up and forwards to Discord

Store the cursor in SOIL `hanuman/remote-control/cursor` between wakeups.

### 4. Reschedule

After each cycle, call `ScheduleWakeup(delaySeconds=60, prompt="/remote-control", reason="polling Grove for Discord commands")` to keep the loop alive.

## Commands Sean can send from Discord

Any free-form message is routed to Claude Code as a command. Examples:
- `fleet status` → run fleet_status and reply
- `what's on the docket` → summarize open threads from handoff
- `handoff hanuman` → post latest handoff summary
- Anything else → Claude Code processes it and replies

## Stopping

Sean types `stop remote-control` in Discord → bridge routes to Grove → Claude Code stops rescheduling.

## Notes

- Bridge daemon runs at `~/.willow/discord_remote.pid` / `~/.willow/discord_remote.log`
- Token in `~/.willow/env` as `DISCORD_BOT_TOKEN`
- Channel: `1509605940578615487`
- Grove loop-prevention: bridge only forwards messages from `hanuman` sender to Discord (not its own `discord-bridge` posts)
