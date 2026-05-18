"""tests/test_pii_detect.py — Unit tests for core.pii_detect Phase 1."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.pii_detect import detect_all, redact_all, PIIMatch
from core.secret_prefixes import detect_secret


# ── secret detection ──────────────────────────────────────────────────────────

class TestSecretDetection:
    def test_groq_key_detected(self):
        hits = detect_all("key is gsk_sBZoR7eWy8U2ClfmhGFFWGdyb3FYtest done")
        assert any(h.type == "secret:groq" for h in hits)

    def test_anthropic_key_detected(self):
        hits = detect_all("sk-ant-api03-abcdefghijklmnopqrstuvwxyz12345678")
        assert any(h.type == "secret:anthropic" for h in hits)

    def test_gemini_key_detected(self):
        hits = detect_all("AIzaSyAbcdefghijklmnopqrstuvwxyz1234567")
        assert any(h.type == "secret:gemini" for h in hits)

    def test_secret_action_is_vault(self):
        hits = detect_all("gsk_sBZoR7eWy8U2ClfmhGFFWGdyb3FYtest")
        secrets = [h for h in hits if h.type.startswith("secret:")]
        assert all(h.suggested_action == "vault" for h in secrets)

    def test_secret_severity_is_3(self):
        hits = detect_all("gsk_sBZoR7eWy8U2ClfmhGFFWGdyb3FYtest")
        secrets = [h for h in hits if h.type.startswith("secret:")]
        assert all(h.severity == 3 for h in secrets)

    def test_short_prefix_not_detected(self):
        # prefix + fewer than 8 chars should not match
        hits = detect_all("gsk_short")
        assert not any(h.type.startswith("secret:") for h in hits)

    def test_secret_redacted_form_truncates(self):
        hits = detect_all("gsk_sBZoR7eWy8U2ClfmhGFFWGdyb3FYtest")
        secrets = [h for h in hits if h.type.startswith("secret:")]
        assert secrets
        assert "…" in secrets[0].redacted


# ── SSN detection ─────────────────────────────────────────────────────────────

class TestSSNDetection:
    def test_ssn_with_dashes(self):
        hits = detect_all("my ssn is 123-45-6789")
        assert any(h.type == "id:ssn" for h in hits)

    def test_ssn_without_dashes(self):
        hits = detect_all("ssn: 123456789")
        assert any(h.type == "id:ssn" for h in hits)

    def test_ssn_action_is_refuse(self):
        hits = detect_all("123-45-6789")
        ssns = [h for h in hits if h.type == "id:ssn"]
        assert all(h.suggested_action == "refuse" for h in ssns)

    def test_ssn_severity_is_3(self):
        hits = detect_all("123-45-6789")
        ssns = [h for h in hits if h.type == "id:ssn"]
        assert all(h.severity == 3 for h in ssns)

    def test_ssn_invalid_area_000_not_detected(self):
        hits = detect_all("000-45-6789")
        assert not any(h.type == "id:ssn" for h in hits)

    def test_ssn_invalid_area_666_not_detected(self):
        hits = detect_all("666-45-6789")
        assert not any(h.type == "id:ssn" for h in hits)

    def test_ssn_redacted_shows_last_four(self):
        hits = detect_all("123-45-6789")
        ssns = [h for h in hits if h.type == "id:ssn"]
        assert ssns and "6789" in ssns[0].redacted


# ── Credit card detection ─────────────────────────────────────────────────────

class TestCreditCardDetection:
    def test_valid_visa_detected(self):
        # 4532015112830366 — valid Luhn
        hits = detect_all("card: 4532015112830366")
        assert any(h.type == "id:credit_card" for h in hits)

    def test_invalid_luhn_not_detected(self):
        hits = detect_all("card: 4532015112830360")
        assert not any(h.type == "id:credit_card" for h in hits)

    def test_cc_action_is_refuse(self):
        hits = detect_all("4532015112830366")
        cc = [h for h in hits if h.type == "id:credit_card"]
        assert all(h.suggested_action == "refuse" for h in cc)

    def test_cc_redacted_shows_last_four(self):
        hits = detect_all("4532015112830366")
        cc = [h for h in hits if h.type == "id:credit_card"]
        assert cc and "0366" in cc[0].redacted


# ── Email detection ───────────────────────────────────────────────────────────

class TestEmailDetection:
    def test_email_detected(self):
        hits = detect_all("email me at test@example.com please")
        assert any(h.type == "contact:email" for h in hits)

    def test_email_action_is_ask(self):
        hits = detect_all("test@example.com")
        emails = [h for h in hits if h.type == "contact:email"]
        assert all(h.suggested_action == "ask" for h in emails)

    def test_email_severity_is_1(self):
        hits = detect_all("test@example.com")
        emails = [h for h in hits if h.type == "contact:email"]
        assert all(h.severity == 1 for h in emails)

    def test_no_false_positive_on_plain_text(self):
        hits = detect_all("nothing sensitive here")
        assert not hits


# ── Phone detection ───────────────────────────────────────────────────────────

class TestPhoneDetection:
    def test_us_phone_detected(self):
        hits = detect_all("call 555-867-5309")
        assert any(h.type == "contact:phone" for h in hits)

    def test_phone_with_parens_detected(self):
        hits = detect_all("reach me at (555) 867-5309")
        assert any(h.type == "contact:phone" for h in hits)

    def test_phone_action_is_ask(self):
        hits = detect_all("555-867-5309")
        phones = [h for h in hits if h.type == "contact:phone"]
        assert all(h.suggested_action == "ask" for h in phones)


# ── redact_all ────────────────────────────────────────────────────────────────

class TestRedactAll:
    def test_redact_replaces_secret(self):
        text = "key: gsk_sBZoR7eWy8U2ClfmhGFFWGdyb3FYtest"
        redacted_text, mapping = redact_all(text)
        assert "gsk_sBZoR7eWy8U2ClfmhGFFWGdyb3FYtest" not in redacted_text
        assert "…" in redacted_text

    def test_redact_replaces_ssn(self):
        text = "my ssn is 123-45-6789 thanks"
        redacted_text, mapping = redact_all(text)
        assert "123-45-6789" not in redacted_text

    def test_redact_clean_input_unchanged(self):
        text = "nothing sensitive here"
        redacted_text, mapping = redact_all(text)
        assert redacted_text == text
        assert mapping == {}

    def test_redact_multiple_hits(self):
        text = "email test@example.com and ssn 123-45-6789"
        redacted_text, mapping = redact_all(text)
        assert "test@example.com" not in redacted_text
        assert "123-45-6789" not in redacted_text


# ── secret_prefixes standalone ────────────────────────────────────────────────

class TestDetectSecret:
    def test_groq_returns_canonical_name(self):
        result = detect_secret("gsk_sBZoR7eWy8U2ClfmhGFFWGdyb3FYtest")
        assert result is not None
        name, label = result
        assert name == "groq_api_key"
        assert label == "Groq"

    def test_none_on_unknown(self):
        assert detect_secret("nothing") is None

    def test_none_on_short_prefix_only(self):
        assert detect_secret("gsk_abc") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
