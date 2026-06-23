"""Tests for core/safe_ops.py."""
from __future__ import annotations

import logging

from core.safe_ops import safe_db_op


def test_safe_db_op_returns_value():
    @safe_db_op
    def ok():
        return 42

    assert ok() == 42


def test_safe_db_op_logs_and_returns_none(caplog):
    @safe_db_op
    def boom():
        raise RuntimeError("db down")

    with caplog.at_level(logging.ERROR):
        assert boom() is None
    assert "boom failed" in caplog.text
