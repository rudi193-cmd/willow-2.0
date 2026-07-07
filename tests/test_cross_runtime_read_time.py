"""cross_runtime read-time rebuild + digest-backed anchor lines (ADR-20260703)."""
from __future__ import annotations

import willow.fylgja.cross_runtime as cross_runtime


def test_ensure_fresh_bridge_always_rebuilds(monkeypatch, tmp_path):
    """The bridge must be rebuilt at read time even when the cached file looks
    newer than the live handoff — intra-day staleness was the whole bug."""
    calls = {"build": 0}

    import scripts.bridge_cross_runtime as bridge_mod

    def fake_build(agent="", **kwargs):
        calls["build"] += 1
        return {"handoff_source": "session_handoff-2026-07-03z_willow.md", "open_threads": []}

    monkeypatch.setattr(bridge_mod, "build_bridge", fake_build)
    monkeypatch.setattr(bridge_mod, "BRIDGE_PATH", tmp_path / "cross-runtime.json")
    monkeypatch.setattr(bridge_mod, "HANDOFF_DIR", tmp_path)

    out = cross_runtime.ensure_fresh_bridge(
        "willow", "session_handoff-2026-07-01a_willow.md", "2026-07-01"
    )
    assert calls["build"] == 1
    assert out["handoff_source"] == "session_handoff-2026-07-03z_willow.md"
    assert (tmp_path / "cross-runtime.json").is_file()


def test_ensure_fresh_bridge_falls_back_to_cache_on_failure(monkeypatch):
    import scripts.bridge_cross_runtime as bridge_mod

    def boom(agent="", **kwargs):
        raise RuntimeError("no session jsonl")

    monkeypatch.setattr(bridge_mod, "build_bridge", boom)
    monkeypatch.setattr(cross_runtime, "read_bridge", lambda: {"handoff_source": "cached"})
    assert cross_runtime.ensure_fresh_bridge("willow")["handoff_source"] == "cached"


def test_anchor_lines_inject_digest_not_bridge_threads(monkeypatch):
    monkeypatch.setattr(
        cross_runtime,
        "read_bridge",
        lambda: {
            "claude_latest": {"session_id": "abcd1234efgh", "runtime": "claude",
                              "duration_minutes": 5, "turn_count": 3},
            "open_threads": ["STALE COPY — must not inject"],
            "next_bite": "STALE NEXT — must not inject",
        },
    )
    import willow.fylgja.boot_digest as boot_digest_mod

    def fake_digest(agent, **kwargs):
        assert kwargs.get("max_claims") == 8
        return {
            "agent": agent, "generated_at": "2026-07-03T05:00:00+00:00",
            "handoff": {"filename": "session_handoff-2026-07-03c_willow.md",
                        "date": "2026-07-03", "format": "v3"},
            "claims": [], "next_bite": None, "attention": {}, "degraded": [],
        }

    monkeypatch.setattr(boot_digest_mod, "build_boot_digest", fake_digest)

    lines = cross_runtime.anchor_lines()
    text = "\n".join(lines)
    assert "[CROSS-RUNTIME]" in text
    assert "claude abcd1234" in text
    assert "[DIGEST]" in text
    assert "STALE COPY" not in text
    assert "STALE NEXT" not in text
    # Ambient marker: a resumed session must not mistake another session's
    # digest for its own memory (FRANK a6986a1a contamination incident).
    assert "this session's own memory" in text


def test_anchor_lines_survive_digest_failure(monkeypatch):
    monkeypatch.setattr(cross_runtime, "read_bridge", lambda: {})
    import willow.fylgja.boot_digest as boot_digest_mod

    def boom(agent, **kwargs):
        raise RuntimeError("store down")

    monkeypatch.setattr(boot_digest_mod, "build_boot_digest", boom)
    lines = cross_runtime.anchor_lines()
    assert any("[DIGEST] unavailable" in line for line in lines)
