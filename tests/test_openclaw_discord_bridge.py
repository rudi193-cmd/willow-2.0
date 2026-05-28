"""Tests for scripts/openclaw_discord_bridge.py command parsing."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.openclaw_discord_bridge import parse_command, validate_discord_targets


def test_grove_channel_message():
    a = parse_command("grove:dispatch @hanuman check PR #5")
    assert a["type"] == "grove_send"
    assert a["channel"] == "dispatch"
    assert "hanuman" in a["content"]


def test_grove_default_channel():
    a = parse_command("grove: hello fleet")
    assert a["type"] == "grove_send"
    assert a["channel"] == "general"
    assert a["content"] == "hello fleet"


def test_willow_status_all():
    a = parse_command("status-all")
    assert a == {"type": "willow_cmd", "cmd": "status-all"}


def test_handoff():
    a = parse_command("handoff willow")
    assert a == {"type": "handoff", "agent": "willow"}


def test_ignore_chatter():
    assert parse_command("hey what's up") is None


def test_validate_placeholder_channel():
    err = validate_discord_targets({"discord_channel_id": "REPLACE_WITH_CHANNEL_ID"})
    assert err and "placeholder" in err


def test_validate_real_channel():
    cid = "1234567890123456789"
    assert validate_discord_targets({
        "discord_channel_id": cid,
        "discord_target": f"channel:{cid}",
    }) is None
