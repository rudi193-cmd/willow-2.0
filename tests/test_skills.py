"""tests/test_skills.py — Willow Skills registry tests."""
import pytest
from core.willow_store import WillowStore
from willow.skills import skill_put, skill_load, skill_list


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_STORE_ROOT", str(tmp_path))
    return WillowStore()


def test_skill_put_and_list(store):
    skill_put(store,
        name="willow-status",
        domain="session",
        content="## Status\nRun willow_status and report.",
        trigger="status check boot",
        auto_load=True,
    )
    skills = skill_list(store)
    names = [s["name"] for s in skills]
    assert "willow-status" in names


def test_skill_load_by_context(store):
    skill_put(store,
        name="willow-fork",
        domain="fork",
        content="## Fork\nCreate a fork with willow_fork_create.",
        trigger="fork create branch session",
        auto_load=True,
    )
    skill_put(store,
        name="willow-status",
        domain="session",
        content="## Status\nRun willow_status.",
        trigger="status boot check",
        auto_load=True,
    )
    results = skill_load(store, context="session started, checking status")
    names = [s["name"] for s in results]
    assert "willow-status" in names


def test_skill_load_respects_auto_load(store):
    skill_put(store,
        name="manual-only",
        domain="session",
        content="## Manual",
        trigger="status",
        auto_load=False,
    )
    results = skill_load(store, context="status")
    names = [s["name"] for s in results]
    assert "manual-only" not in names


def test_skill_list_by_domain(store):
    skill_put(store, name="s1", domain="session", content="c", trigger="t", auto_load=True)
    skill_put(store, name="s2", domain="fork", content="c", trigger="t", auto_load=True)
    session_skills = skill_list(store, domain="session")
    assert all(s["domain"] == "session" for s in session_skills)


# ── mastery-aware re-rank (#3a) ──────────────────────────────────────────────

def _seed_overlap_pair(store):
    """A high-overlap unpractised skill and a low-overlap mastered skill.
    Context 'alpha beta gamma' overlaps 3 words with high-overlap, 1 with low."""
    skill_put(store, name="high-overlap", domain="session", content="c",
              trigger="alpha beta gamma", auto_load=True)
    skill_put(store, name="low-overlap", domain="session", content="c",
              trigger="alpha", auto_load=True)
    from core import skill_mastery as sm
    for _ in range(8):
        sm.record("low-overlap", correct=True)  # demonstrably mastered


def test_skill_load_default_ignores_mastery(store):
    """Default (mastery_bias=0.0): order is overlap-only — the more-relevant
    skill wins even though the other is far more mastered."""
    _seed_overlap_pair(store)
    ranked = skill_load(store, context="alpha beta gamma")
    assert ranked[0]["name"] == "high-overlap"


def test_skill_load_mastery_bias_reranks_toward_mastered(store):
    """A large positive bias lets the mastered (but less-relevant) skill win."""
    _seed_overlap_pair(store)
    ranked = skill_load(store, context="alpha beta gamma", mastery_bias=5.0)
    assert ranked[0]["name"] == "low-overlap"
