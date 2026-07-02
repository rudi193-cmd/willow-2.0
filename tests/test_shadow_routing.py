"""Shadow routing — complexity classifier, veto resolution, record shape.

ADR-20260702 step 3. Pure-function coverage; the DB insert path (log_shadow)
is exercised by the live verification harness, not unit tests.
"""
from willow.routing.shadow import (
    RUNGS,
    classify_complexity,
    resolve_shadow_engine,
    shadow_decision,
)


class TestClassifyComplexity:
    def test_trivial_short_prompt(self):
        r = classify_complexity("hi")
        assert r["rung"] == "r1_trivial"
        assert r["score"] == 0

    def test_rung_is_known(self):
        for prompt in ["", "x", "explain why " * 50, "```\ncode\n```"]:
            assert classify_complexity(prompt)["rung"] in RUNGS

    def test_code_bumps_score(self):
        plain = classify_complexity("summarize this note")
        coded = classify_complexity("```python\ndef f(): pass\n```")
        assert coded["score"] > plain["score"]
        assert "code" in coded["signals"]

    def test_reasoning_heavy_signal_fires(self):
        # A one-line reasoning question is still short → the length term keeps it
        # low, but the reasoning_heavy signal must fire so long reasoning prompts
        # escalate. Verify the signal, not a specific rung, for the short case.
        r = classify_complexity(
            "Analyze the tradeoff and derive why we should refactor this design."
        )
        assert "reasoning_heavy" in r["signals"]
        assert r["rung"] in ("r2_simple", "r3_moderate")

    def test_reasoning_plus_length_escalates(self):
        r = classify_complexity(
            "Here is a long brief. " + "context " * 600 +
            " Analyze the tradeoff and derive why we should refactor this design."
        )
        assert "reasoning_heavy" in r["signals"]
        assert r["rung"] in ("r4_complex", "r5_frontier")

    def test_very_long_complex(self):
        r = classify_complexity("word " * 1000 + " why prove derive analyze")
        assert r["rung"] in ("r4_complex", "r5_frontier")

    def test_deterministic(self):
        p = "Compare these two approaches and design the better one. Why?"
        assert classify_complexity(p) == classify_complexity(p)


class TestResolveShadowEngine:
    def test_low_rung_local(self):
        eng = resolve_shadow_engine("r1_trivial", "open")
        assert eng["complexity_engine"] == "local"
        assert eng["router_engine"] == "local"
        assert eng["veto_applied"] is False

    def test_high_rung_open_goes_cloud(self):
        eng = resolve_shadow_engine("r5_frontier", "open")
        assert eng["complexity_engine"] == "cloud"
        assert eng["router_engine"] == "cloud"
        assert eng["veto_applied"] is False

    def test_sensitive_vetoes_high_rung_to_local(self):
        eng = resolve_shadow_engine("r5_frontier", "sensitive")
        assert eng["complexity_engine"] == "cloud"
        assert eng["router_engine"] == "local"
        assert eng["veto_applied"] is True

    def test_unknown_fails_closed(self):
        eng = resolve_shadow_engine("r5_frontier", "unknown")
        assert eng["router_engine"] == "local"
        assert eng["veto_applied"] is True

    def test_sensitive_low_rung_no_veto_flag(self):
        # already local; sensitivity changes nothing, veto_applied stays False
        eng = resolve_shadow_engine("r1_trivial", "sensitive")
        assert eng["router_engine"] == "local"
        assert eng["veto_applied"] is False


class TestShadowDecision:
    def test_record_shape(self):
        rec = shadow_decision("Explain why this design works.", sensitivity="open",
                              actual_engine="ollama")
        for k in ("rung", "score", "signals", "sensitivity", "complexity_engine",
                  "router_engine", "veto_applied", "actual_engine"):
            assert k in rec
        assert rec["actual_engine"] == "ollama"
        assert rec["sensitivity"] == "open"

    def test_default_sensitivity_unknown_fails_closed(self):
        rec = shadow_decision("word " * 1000 + " analyze derive prove why")
        assert rec["sensitivity"] == "unknown"
        assert rec["router_engine"] == "local"
