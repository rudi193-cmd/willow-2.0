"""Tests for curated continuity retrieval pool."""
from __future__ import annotations

import os

import pytest

from willow.ranking.continuity_pool import (
    b2_source_types,
    curated_continuity_source_types,
    resolve_continuity_source_types,
)


def test_b2_includes_handoff_kb_and_external():
    types = set(b2_source_types())
    assert "handoff" in types
    assert "mcp" in types
    assert "external" in types
    assert "session_promote" in types


def test_curated_excludes_intake():
    curated = curated_continuity_source_types()
    assert "intake" not in curated
    assert "intake" in b2_source_types()
    assert len(curated) == len(b2_source_types()) - 1


def test_resolve_defaults_to_curated():
    os.environ.pop("WILLOW_CONTINUITY_POOL", None)
    pool = resolve_continuity_source_types()
    assert pool is not None
    assert "intake" not in pool


def test_resolve_full_pool():
    assert resolve_continuity_source_types(pool="full") is None
    assert resolve_continuity_source_types(pool="off") is None


def test_resolve_env_override(monkeypatch):
    monkeypatch.setenv("WILLOW_CONTINUITY_POOL", "full")
    assert resolve_continuity_source_types() is None
    monkeypatch.setenv("WILLOW_CONTINUITY_POOL", "curated")
    assert resolve_continuity_source_types() is not None


def test_resolve_unknown_pool():
    with pytest.raises(ValueError, match="unknown continuity pool"):
        resolve_continuity_source_types(pool="bogus")
