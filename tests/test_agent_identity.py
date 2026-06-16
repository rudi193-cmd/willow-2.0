"""Tests for core.agent_identity.require_agent_name — fleet identity gate."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from core.agent_identity import require_agent_name


def test_require_agent_name_returns_stripped_value():
    with patch.dict(os.environ, {"WILLOW_AGENT_NAME": "  willow  "}, clear=False):
        assert require_agent_name() == "willow"


def test_require_agent_name_raises_when_unset():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(EnvironmentError, match="WILLOW_AGENT_NAME is not set"):
            require_agent_name()


def test_require_agent_name_raises_when_blank():
    with patch.dict(os.environ, {"WILLOW_AGENT_NAME": "   "}, clear=False):
        with pytest.raises(EnvironmentError, match="WILLOW_AGENT_NAME is not set"):
            require_agent_name()
