"""Tests for MCP identity bind (PR 1)."""
from __future__ import annotations

import os
from unittest import mock

from willow.fylgja.identity_bind import check_app_id, identity_bind_mode


def test_check_app_id_ok_when_match():
    with mock.patch.dict(os.environ, {"WILLOW_AGENT_NAME": "hanuman", "WILLOW_IDENTITY_BIND": "warn"}):
        action, msg = check_app_id("hanuman")
    assert action == "ok"
    assert msg is None


def test_check_app_id_warn_on_mismatch():
    with mock.patch.dict(os.environ, {"WILLOW_AGENT_NAME": "hanuman", "WILLOW_IDENTITY_BIND": "warn"}):
        action, msg = check_app_id("willow")
    assert action == "warn"
    assert msg and "hanuman" in msg


def test_check_app_id_block_in_strict():
    with mock.patch.dict(os.environ, {"WILLOW_AGENT_NAME": "hanuman", "WILLOW_IDENTITY_BIND": "strict"}):
        action, msg = check_app_id("willow")
    assert action == "block"
    assert msg


def test_check_app_id_off_skips():
    with mock.patch.dict(os.environ, {"WILLOW_AGENT_NAME": "hanuman", "WILLOW_IDENTITY_BIND": "off"}):
        action, msg = check_app_id("willow")
    assert action == "ok"


def test_identity_bind_mode_default_warn():
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("WILLOW_IDENTITY_BIND", None)
        assert identity_bind_mode() == "warn"
