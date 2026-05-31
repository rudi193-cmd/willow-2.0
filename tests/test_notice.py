"""tests/test_notice.py — Unit tests for core.notice Norn Pattern."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import pytest
from unittest.mock import patch

from core.notice import notice, NoticeResult


class TestNoticeCleanInput:
    def test_clean_text_returns_unchanged(self):
        result = notice("nothing sensitive here")
        assert result.redacted == "nothing sensitive here"
        assert result.matches == []
        assert result.voiced is False

    def test_returns_notice_result_type(self):
        result = notice("hello")
        assert isinstance(result, NoticeResult)


class TestNoticeSecretDetection:
    def test_api_key_redacted(self, capsys):
        result = notice("key gsk_sBZoR7eWy8U2ClfmhGFFWGdyb3FYtest", session_id="test")
        assert "gsk_sBZoR7eWy8U2ClfmhGFFWGdyb3FYtest" not in result.redacted
        assert result.matches

    def test_voice_printed_for_secret(self, capsys):
        notice("key gsk_sBZoR7eWy8U2ClfmhGFFWGdyb3FYtest", session_id="test")
        out = capsys.readouterr().out
        assert "[NOTICE]" in out

    def test_silent_suppresses_voice(self, capsys):
        notice("key gsk_sBZoR7eWy8U2ClfmhGFFWGdyb3FYtest", session_id="test", silent=True)
        out = capsys.readouterr().out
        assert "[NOTICE]" not in out

    def test_voiced_flag_reflects_output(self, capsys):
        result = notice("key gsk_sBZoR7eWy8U2ClfmhGFFWGdyb3FYtest", session_id="test")
        assert result.voiced is True

    def test_silent_voiced_is_false(self):
        result = notice("key gsk_sBZoR7eWy8U2ClfmhGFFWGdyb3FYtest", session_id="test", silent=True)
        assert result.voiced is False


class TestNoticeHighestSeverityVoiced:
    def test_only_one_voice_line_per_call(self, capsys):
        # SSN (sev 3) + email (sev 1) — should voice only once
        text = "ssn 123-45-6789 and email test@example.com"
        notice(text, session_id="test")
        out = capsys.readouterr().out
        assert out.count("[NOTICE]") == 1

    def test_highest_severity_match_voiced(self, capsys):
        text = "ssn 123-45-6789 and email test@example.com"
        notice(text, session_id="test")
        out = capsys.readouterr().out
        # SSN copy_template contains "Social Security"
        assert "Social Security" in out


class TestNoticeWitness:
    def test_witness_writes_log(self, tmp_path):
        log = tmp_path / "notices_test.jsonl"
        with patch("core.notice._NOTICES_LOG", log):
            notice("ssn 123-45-6789", session_id="sess-abc", surface="prompt")
        assert log.exists()
        lines = [json.loads(line) for line in log.read_text().strip().splitlines()]
        assert len(lines) == 1
        assert lines[0]["type"] == "id:ssn"
        assert lines[0]["surface"] == "prompt"
        assert lines[0]["session_id"] == "sess-abc"

    def test_witness_multiple_matches(self, tmp_path):
        log = tmp_path / "notices_test.jsonl"
        with patch("core.notice._NOTICES_LOG", log):
            notice("ssn 123-45-6789 email test@example.com", session_id="sess-xyz")
        lines = log.read_text().strip().splitlines()
        assert len(lines) == 2

    def test_witness_fires_even_when_silent(self, tmp_path):
        log = tmp_path / "notices_test.jsonl"
        with patch("core.notice._NOTICES_LOG", log):
            notice("ssn 123-45-6789", session_id="s", silent=True)
        assert log.exists()
        assert log.stat().st_size > 0


class TestNoticeSSN:
    def test_ssn_refused_and_redacted(self):
        result = notice("my ssn is 123-45-6789")
        assert "123-45-6789" not in result.redacted
        ssns = [m for m in result.matches if m.type == "id:ssn"]
        assert ssns


class TestNoticeMultipleMatches:
    def test_all_pii_redacted(self):
        text = "email test@example.com ssn 123-45-6789"
        result = notice(text)
        assert "test@example.com" not in result.redacted
        assert "123-45-6789" not in result.redacted
        assert len(result.matches) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
