"""Tests for Ratatosk envelope protocol."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from ratatosk.protocol.envelope import (
    Intent,
    build_envelope,
    clear_nonce_cache,
    parse_grove_message,
    validate_envelope,
)


@pytest.fixture(autouse=True)
def _clear_nonces():
    clear_nonce_cache()
    yield
    clear_nonce_cache()


def test_build_envelope_defaults():
    env = build_envelope(to="ratatosk", prompt="hello")
    assert env.v == 1
    assert env.intent == Intent.CHAT.value
    assert env.requires_confirm is False
    assert env.trace_id.startswith("tr-")


def test_high_risk_requires_confirm():
    env = build_envelope(to="ratatosk", prompt="rm -rf", intent=Intent.RUN_TASK.value)
    assert env.requires_confirm is True


def test_parse_json_envelope():
    payload = build_envelope(to="ratatosk", prompt="ping", intent=Intent.OPEN_STATUS.value)
    msg = {"content": payload.to_json(), "sender": "phone"}
    env = parse_grove_message(msg, default_node="ratatosk")
    assert env is not None
    assert env.prompt == "ping"
    assert env.intent == Intent.OPEN_STATUS.value


def test_parse_addressed_text():
    msg = {"content": "ratatosk: ship it", "sender": "sean"}
    env = parse_grove_message(msg, default_node="hanuman")
    assert env is not None
    assert env.to == "ratatosk"
    assert env.prompt == "ship it"


def test_validate_expired():
    env = build_envelope(to="ratatosk", prompt="late", ttl_seconds=1)
    env.expires_at = (datetime.now(timezone.utc) - timedelta(seconds=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = validate_envelope(env, node="ratatosk")
    assert not result.ok
    assert "expired" in result.errors[0]


def test_validate_replay():
    env = build_envelope(to="ratatosk", prompt="once", nonce="fixed-nonce")
    assert validate_envelope(env, node="ratatosk").ok
    assert not validate_envelope(env, node="ratatosk").ok


def test_validate_wrong_node():
    env = build_envelope(to="loki", prompt="nope")
    result = validate_envelope(env, node="ratatosk")
    assert not result.ok
