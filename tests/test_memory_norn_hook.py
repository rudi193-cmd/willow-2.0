"""
tests/test_memory_norn_hook.py

Tests for willow.memory.norn_hook — PII-scrubbing pre-extraction hook.

No external dependencies required (no spaCy, no Postgres).
"""
from __future__ import annotations

import pytest

from willow.memory.norn_hook import NornScrubber, ScrubResult, PiiFinding, notice


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def make_scrubber(**kwargs) -> NornScrubber:
    return NornScrubber(use_spacy=False, **kwargs)


# ---------------------------------------------------------------------------
# Tests: token / API key patterns (aligned with adjoint redact.py)
# ---------------------------------------------------------------------------

class TestTokenPatterns:
    def test_anthropic_api_key(self):
        sc = make_scrubber()
        text = "export ANTHROPIC_API_KEY=sk-ant-api03-verylongkeyhere1234567890abcdef"
        r = sc.scrub(text)
        assert "[REDACTED:anthropic_api_key]" in r.redacted
        assert "sk-ant-api03" not in r.redacted
        assert any(f.label == "anthropic_api_key" for f in r.findings)

    def test_github_pat(self):
        sc = make_scrubber()
        text = "Token: ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ123456789012"
        r = sc.scrub(text)
        assert "[REDACTED:github_pat]" in r.redacted

    def test_openai_key(self):
        sc = make_scrubber()
        # 48 chars after sk-
        key = "sk-" + "A" * 48
        r = sc.scrub(f"key={key}")
        assert "[REDACTED:" in r.redacted
        assert key not in r.redacted

    def test_slack_token(self):
        sc = make_scrubber()
        text = "token=xoxb-1234-5678-abcdefghijklmno"
        r = sc.scrub(text)
        assert "[REDACTED:slack_token]" in r.redacted

    def test_aws_access_key(self):
        sc = make_scrubber()
        text = "aws_access_key_id=AKIAIOSFODNN7EXAMPLE"
        r = sc.scrub(text)
        assert "[REDACTED:aws_access_key]" in r.redacted


# ---------------------------------------------------------------------------
# Tests: PII patterns (Norn contribution)
# ---------------------------------------------------------------------------

class TestPiiPatterns:
    def test_email_redacted(self):
        sc = make_scrubber()
        text = "Contact me at sean@example.com for details."
        r = sc.scrub(text)
        assert "[REDACTED:email]" in r.redacted
        assert "sean@example.com" not in r.redacted
        assert any(f.label == "email" for f in r.findings)

    def test_phone_us_redacted(self):
        sc = make_scrubber()
        text = "Call me at 415-555-1234 or (415) 555-9876."
        r = sc.scrub(text)
        assert "[REDACTED:phone_us]" in r.redacted

    def test_ssn_redacted(self):
        sc = make_scrubber()
        text = "SSN: 123-45-6789"
        r = sc.scrub(text)
        assert "[REDACTED:ssn]" in r.redacted

    def test_ipv4_redacted(self):
        sc = make_scrubber()
        text = "Server at 203.0.113.42 responded with 200."
        r = sc.scrub(text)
        assert "[REDACTED:ipv4]" in r.redacted

    def test_loopback_ip_not_redacted(self):
        sc = make_scrubber()
        text = "Connect to 127.0.0.1:5432"
        r = sc.scrub(text)
        # Loopback is allowlisted
        assert "127.0.0.1" in r.redacted
        assert r.clean

    def test_rfc1918_not_redacted(self):
        sc = make_scrubber()
        text = "Internal host at 192.168.1.100"
        r = sc.scrub(text)
        assert "192.168.1.100" in r.redacted  # RFC1918 allowlisted


# ---------------------------------------------------------------------------
# Tests: clean text
# ---------------------------------------------------------------------------

class TestCleanText:
    def test_clean_text_passes_through(self):
        sc = make_scrubber()
        text = "The build passed all 42 tests. Deploy to staging."
        r = sc.scrub(text)
        assert r.redacted == text
        assert r.clean
        assert r.findings == []

    def test_empty_string(self):
        sc = make_scrubber()
        r = sc.scrub("")
        assert r.redacted == ""
        assert r.clean

    def test_none_like_empty(self):
        sc = make_scrubber()
        r = sc.scrub("")
        assert r.original == ""


# ---------------------------------------------------------------------------
# Tests: overlapping spans and multiple hits
# ---------------------------------------------------------------------------

class TestOverlappingSpans:
    def test_two_different_pii_in_one_string(self):
        sc = make_scrubber()
        text = "Email sean@example.com and key=sk-ant-api03-longkeyvalue123456789abcdef"
        r = sc.scrub(text)
        assert "[REDACTED:email]" in r.redacted
        assert "[REDACTED:anthropic_api_key]" in r.redacted
        assert "sean@example.com" not in r.redacted

    def test_multiple_emails(self):
        sc = make_scrubber()
        text = "To: a@foo.com and b@bar.com"
        r = sc.scrub(text)
        assert "a@foo.com" not in r.redacted
        assert "b@bar.com" not in r.redacted
        # Both should be redacted
        assert r.redacted.count("[REDACTED:email]") == 2


# ---------------------------------------------------------------------------
# Tests: custom extra_patterns
# ---------------------------------------------------------------------------

class TestExtraPatterns:
    def test_custom_pattern_fires(self):
        sc = NornScrubber(
            extra_patterns={"internal_token": r"wlw_[A-Za-z0-9]{16}"},
            use_spacy=False,
        )
        text = "token=wlw_AbCdEfGhIjKlMnOp"
        r = sc.scrub(text)
        assert "[REDACTED:internal_token]" in r.redacted

    def test_invalid_extra_pattern_is_skipped(self):
        # Should not raise; bad pattern is silently dropped
        sc = NornScrubber(
            extra_patterns={"bad_pattern": r"[invalid(regex"},
            use_spacy=False,
        )
        r = sc.scrub("some text")
        assert r.redacted == "some text"


# ---------------------------------------------------------------------------
# Tests: ScrubResult helpers
# ---------------------------------------------------------------------------

class TestScrubResult:
    def test_clean_property(self):
        r = ScrubResult(original="text", redacted="text", findings=[])
        assert r.clean is True

    def test_dirty_property(self):
        r = ScrubResult(
            original="text",
            redacted="[REDACTED:email]",
            findings=[PiiFinding(label="email", start=0, end=10, excerpt="a@b.com")],
        )
        assert r.clean is False

    def test_summary_clean(self):
        r = ScrubResult(original="x", redacted="x")
        assert r.summary() == "clean"

    def test_summary_with_findings(self):
        r = ScrubResult(
            original="x",
            redacted="y",
            findings=[
                PiiFinding(label="email", start=0, end=5, excerpt="x"),
                PiiFinding(label="phone_us", start=6, end=15, excerpt="y"),
            ],
        )
        s = r.summary()
        assert "email" in s
        assert "phone_us" in s


# ---------------------------------------------------------------------------
# Tests: scrub_batch
# ---------------------------------------------------------------------------

class TestScrubBatch:
    def test_batch_scrubs_all(self):
        sc = make_scrubber()
        texts = ["clean text", "email: a@b.com", "another clean"]
        results = sc.scrub_batch(texts, surface="test")
        assert results[0].clean
        assert not results[1].clean
        assert results[2].clean

    def test_batch_empty_list(self):
        sc = make_scrubber()
        assert sc.scrub_batch([]) == []


# ---------------------------------------------------------------------------
# Tests: notice() convenience function
# ---------------------------------------------------------------------------

class TestNoticeFunction:
    def test_notice_returns_scrub_result(self):
        r = notice("Hello sean@example.com", surface="test", session_id="sess001")
        assert isinstance(r, ScrubResult)
        assert "[REDACTED:email]" in r.redacted

    def test_notice_singleton_reuse(self):
        # Calling notice twice should reuse the same scrubber (no side effects)
        r1 = notice("clean text")
        r2 = notice("also clean text")
        assert r1.clean
        assert r2.clean

    def test_notice_clean_text(self):
        r = notice("The build is green.")
        assert r.clean
        assert r.redacted == "The build is green."


# ---------------------------------------------------------------------------
# Tests: redacted format compatibility with adjoint
# ---------------------------------------------------------------------------

class TestAdjointCompatibility:
    """Verify our REDACTED token format matches adjoint's redact.py format.

    adjoint uses [REDACTED:<label>] — we must match exactly so downstream
    consumers (adjoint's lint.py, log parsers, etc.) handle our output the
    same way.
    """

    def test_redaction_token_format(self):
        sc = make_scrubber()
        text = "key=sk-ant-api03-LONGKEYVALUE123456789abcdefghijklmnopqrstuvwxyz"
        r = sc.scrub(text)
        # Format must be exactly [REDACTED:<label>]
        assert "[REDACTED:anthropic_api_key]" in r.redacted
        # No double-bracket or space variants
        assert "[[REDACTED" not in r.redacted
        assert "[REDACTED :" not in r.redacted

    def test_multiple_redaction_tokens_are_distinct(self):
        sc = make_scrubber()
        text = "a@b.com and sk-ant-api03-LONGKEYHERE123456789abcdef"
        r = sc.scrub(text)
        # Both labels appear, not a single merged token
        assert "[REDACTED:email]" in r.redacted
        assert "[REDACTED:anthropic_api_key]" in r.redacted
