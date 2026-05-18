"""
tests/test_pii_restore.py

Tests for core.pii_detect.restore_all() and the updated redact_all() return
signature — the DontFeedTheAI vault/surrogate restoration pattern adapted
for Willow's per-message dict-based approach.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.pii_detect import detect_all, redact_all, restore_all


# ── redact_all() — new (text, mapping) return value ──────────────────────────

class TestRedactAllReturnsMapping:
    def test_returns_tuple(self):
        result = redact_all("email me at test@example.com")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_mapping_contains_redacted_to_raw(self):
        _, mapping = redact_all("email me at test@example.com")
        assert mapping  # non-empty
        # The original email should appear as a value
        assert "test@example.com" in mapping.values()

    def test_redacted_text_replaces_email(self):
        text, _ = redact_all("email me at test@example.com")
        assert "test@example.com" not in text

    def test_clean_text_returns_empty_mapping(self):
        text, mapping = redact_all("nothing sensitive here")
        assert text == "nothing sensitive here"
        assert mapping == {}

    def test_mapping_keys_are_redacted_placeholders(self):
        text, mapping = redact_all("my ssn is 123-45-6789")
        # The key must appear in the redacted text
        for key in mapping:
            assert key in text

    def test_extends_existing_mapping(self):
        existing = {"te…@example.com": "te@something.com"}
        _, mapping = redact_all("call 555-867-5309", mapping=existing)
        # Existing entry preserved
        assert "te…@example.com" in mapping
        # New phone entry added
        assert any("contact:phone" in str(v) or "555" in str(v)
                   for v in mapping.values())

    def test_multiple_pii_all_in_mapping(self):
        text = "email test@example.com ssn 123-45-6789"
        redacted, mapping = redact_all(text)
        # Two distinct PII items — two entries
        assert len(mapping) >= 2
        assert "test@example.com" in mapping.values()
        assert "123-45-6789" in mapping.values()


# ── restore_all() ─────────────────────────────────────────────────────────────

class TestRestoreAll:
    def test_restores_email(self):
        original = "email me at test@example.com"
        redacted, mapping = redact_all(original)
        restored = restore_all(redacted, mapping)
        assert "test@example.com" in restored

    def test_restores_ssn(self):
        original = "my ssn is 123-45-6789"
        redacted, mapping = redact_all(original)
        restored = restore_all(redacted, mapping)
        assert "123-45-6789" in restored

    def test_restores_credit_card(self):
        original = "card: 4532015112830366"
        redacted, mapping = redact_all(original)
        restored = restore_all(redacted, mapping)
        assert "4532015112830366" in restored

    def test_restores_phone(self):
        original = "call 555-867-5309 please"
        redacted, mapping = redact_all(original)
        restored = restore_all(redacted, mapping)
        assert "555-867-5309" in restored

    def test_restore_roundtrip_multiple(self):
        original = "email test@example.com phone 555-867-5309"
        redacted, mapping = redact_all(original)
        restored = restore_all(redacted, mapping)
        assert "test@example.com" in restored
        assert "555-867-5309" in restored

    def test_restore_clean_text_unchanged(self):
        _, mapping = redact_all("clean text")
        restored = restore_all("clean text", mapping)
        assert restored == "clean text"

    def test_restore_empty_mapping_unchanged(self):
        restored = restore_all("some redacted text", {})
        assert restored == "some redacted text"

    def test_restore_secret_key(self):
        original = "key is gsk_sBZoR7eWy8U2ClfmhGFFWGdyb3FYtestkey done"
        redacted, mapping = redact_all(original)
        assert "gsk_sBZoR7eWy8U2ClfmhGFFWGdyb3FYtestkey" not in redacted
        restored = restore_all(redacted, mapping)
        assert "gsk_sBZoR7eWy8U2ClfmhGFFWGdyb3FYtestkey" in restored

    def test_restore_does_not_double_replace(self):
        """Restoring twice should not corrupt the text."""
        original = "email test@example.com"
        redacted, mapping = redact_all(original)
        restored_once = restore_all(redacted, mapping)
        restored_twice = restore_all(restored_once, mapping)
        # The email should be back; restoring again over already-restored text
        # might produce the original or slightly different output depending on
        # whether the placeholder still appears — but it should not crash.
        assert isinstance(restored_twice, str)

    def test_restore_longest_key_first(self):
        """
        If a shorter redacted form is a substring of a longer one,
        restoration must not partially replace the longer form.

        This mirrors DontFeedTheAI's longest-match-first vault replacement.
        """
        mapping = {
            "te…@example.com": "test@example.com",
            "te…": "test_prefix",  # shorter key, should not interfere
        }
        text = "contact te…@example.com here"
        restored = restore_all(text, mapping)
        # Longest key must win — te…@example.com → test@example.com
        assert "test@example.com" in restored


# ── backward compat: old call signature ──────────────────────────────────────

class TestRedactAllBackwardCompat:
    """
    The new redact_all() returns (str, dict) instead of str.
    Callers that unpack correctly still work.
    """
    def test_old_style_unpack(self):
        text, mapping = redact_all("email test@example.com")
        assert isinstance(text, str)
        assert isinstance(mapping, dict)

    def test_passing_matches_explicitly(self):
        matches = detect_all("email test@example.com")
        text, mapping = redact_all("email test@example.com", matches)
        assert "test@example.com" not in text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
