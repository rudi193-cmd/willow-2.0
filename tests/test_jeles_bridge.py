"""Tests for core/jeles_bridge.py — serendipity relevance floor (#653)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.jeles_bridge import (
    DEFAULT_MIN_COSINE,
    bridge_floor,
    informative_overlap,
    min_cosine,
    tokens,
)


def _embed_const(vec):
    return lambda text: vec


def test_tokens_min_length_and_case():
    assert tokens("The Law of the LAND") == {"land"}
    assert tokens("") == set()


def test_informative_overlap_strips_generic():
    # the Carla Bley case: only "united states" overlaps → nothing informative
    assert informative_overlap(
        "United States (Carla Bley recording)",
        "Federalism divides power between the United States and the states",
    ) == set()
    assert "amendment" in informative_overlap(
        "First Amendment jurisprudence", "amendment ratification process"
    )


def test_generic_only_overlap_fails_without_embedding():
    calls = []

    def spy_embed(text):
        calls.append(text)
        return [1.0]

    verdict = bridge_floor(
        "United States", "the United States government", embed=spy_embed
    )
    assert verdict["passes"] is False
    assert verdict["reason"] == "generic-only overlap"
    assert calls == []  # cheap rejection — no embed spent


def test_embedder_unavailable_fails_closed():
    verdict = bridge_floor(
        "habeas corpus for dinosaurs", "habeas corpus suspension clause",
        embed=_embed_const([]),
    )
    assert verdict["passes"] is False
    assert verdict["reason"] == "embedder unavailable"


def test_cosine_below_floor_fails():
    vecs = {"a": [1.0, 0.0], "b": [0.0, 1.0]}  # orthogonal → cosine 0

    def embed(text):
        return vecs["a"] if "gnome" in text else vecs["b"]

    verdict = bridge_floor(
        "garden gnome property rights", "takings clause property rights",
        floor=0.45, embed=embed,
    )
    assert verdict["passes"] is False
    assert verdict["cosine"] is not None and verdict["cosine"] < 0.01
    assert "below floor" in verdict["reason"]


def test_related_texts_pass():
    verdict = bridge_floor(
        "habeas corpus petition procedure", "habeas corpus suspension clause",
        floor=0.45, embed=_embed_const([0.5, 0.5]),  # identical vecs → cosine 1
    )
    assert verdict["passes"] is True
    assert verdict["cosine"] > 0.99
    assert "habeas" in verdict["overlap"]


def test_min_cosine_env_override(monkeypatch):
    monkeypatch.setenv("JELES_BRIDGE_MIN_COSINE", "0.9")
    assert min_cosine() == 0.9
    monkeypatch.setenv("JELES_BRIDGE_MIN_COSINE", "not-a-float")
    assert min_cosine() == DEFAULT_MIN_COSINE
