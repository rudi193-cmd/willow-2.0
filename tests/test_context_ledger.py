"""
tests/test_context_ledger.py — Unit tests for willow.context.ledger

Uses tmp_path for filesystem isolation. No network, no DB.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import willow.context.ledger as ledger_mod
from willow.context import ledger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _yesterday() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

class TestLedgerPath:
    def test_path_contains_agent_and_date(self, tmp_path):
        with patch.object(ledger_mod, "_WILLOW_HOME", tmp_path):
            p = ledger_mod._ledger_path("hanuman", "2026-01-01")
        assert "hanuman" in p.name
        assert "2026-01-01" in p.name
        assert p.suffix == ".jsonl"

    def test_default_date_is_today(self, tmp_path):
        with patch.object(ledger_mod, "_WILLOW_HOME", tmp_path):
            p = ledger_mod._ledger_path("hanuman")
        assert _today() in p.name


# ---------------------------------------------------------------------------
# append / write
# ---------------------------------------------------------------------------

class TestAppend:
    def test_creates_file_and_valid_json(self, tmp_path):
        with patch.object(ledger_mod, "_WILLOW_HOME", tmp_path):
            p = ledger_mod.append(
                "test content",
                entry_type=ledger.OBSERVATION,
                session_id="sess123",
                agent="hanuman",
            )
        lines = [l for l in p.read_text().splitlines() if l.strip()]
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["type"] == ledger.OBSERVATION
        assert entry["content"] == "test content"
        assert entry["agent"] == "hanuman"
        assert "sess" in entry["session_id"]

    def test_multiple_appends(self, tmp_path):
        with patch.object(ledger_mod, "_WILLOW_HOME", tmp_path):
            for i in range(5):
                ledger_mod.append(f"entry {i}", entry_type=ledger.ACTION, agent="hanuman")
            p = ledger_mod._ledger_path("hanuman")
        lines = [l for l in p.read_text().splitlines() if l.strip()]
        assert len(lines) == 5

    def test_content_is_truncated_at_2000(self, tmp_path):
        long = "x" * 3000
        with patch.object(ledger_mod, "_WILLOW_HOME", tmp_path):
            p = ledger_mod.append(long, entry_type=ledger.OBSERVATION, agent="hanuman")
        entry = json.loads(p.read_text().strip())
        assert len(entry["content"]) <= 2000

    def test_session_id_truncated_at_16(self, tmp_path):
        with patch.object(ledger_mod, "_WILLOW_HOME", tmp_path):
            p = ledger_mod.append(
                "x", entry_type=ledger.OBSERVATION, session_id="a" * 40, agent="hanuman"
            )
        entry = json.loads(p.read_text().strip())
        assert len(entry["session_id"]) <= 16


# ---------------------------------------------------------------------------
# Typed wrappers
# ---------------------------------------------------------------------------

class TestTypedWrappers:
    def test_log_observation_writes_type(self, tmp_path):
        with patch.object(ledger_mod, "_WILLOW_HOME", tmp_path):
            ledger_mod.log_observation("Hello world", session_id="s1")
            p = ledger_mod._ledger_path(ledger_mod._AGENT)
        entry = json.loads(p.read_text().strip())
        assert entry["type"] == ledger.OBSERVATION

    def test_log_observation_skips_empty(self, tmp_path):
        with patch.object(ledger_mod, "_WILLOW_HOME", tmp_path):
            ledger_mod.log_observation("", session_id="s1")
            p = ledger_mod._ledger_path(ledger_mod._AGENT)
        assert not p.exists() or p.read_text().strip() == ""

    def test_log_observation_skips_too_short(self, tmp_path):
        with patch.object(ledger_mod, "_WILLOW_HOME", tmp_path):
            ledger_mod.log_observation("hi", session_id="s1")  # len 2 < 4
            p = ledger_mod._ledger_path(ledger_mod._AGENT)
        assert not p.exists() or p.read_text().strip() == ""

    def test_log_block_format(self, tmp_path):
        with patch.object(ledger_mod, "_WILLOW_HOME", tmp_path):
            ledger_mod.log_block("Bash", "direct psql blocked")
            p = ledger_mod._ledger_path(ledger_mod._AGENT)
        entry = json.loads(p.read_text().strip())
        assert entry["type"] == ledger.BLOCK
        assert "BLOCKED" in entry["content"]
        assert "Bash" in entry["content"]

    def test_log_compact_snapshot(self, tmp_path):
        with patch.object(ledger_mod, "_WILLOW_HOME", tmp_path):
            ledger_mod.log_compact_snapshot("pre-compact summary")
            p = ledger_mod._ledger_path(ledger_mod._AGENT)
        entry = json.loads(p.read_text().strip())
        assert entry["type"] == ledger.COMPACT_SNAPSHOT


# ---------------------------------------------------------------------------
# load_recent
# ---------------------------------------------------------------------------

class TestLoadRecent:
    def test_empty_when_no_file(self, tmp_path):
        with patch.object(ledger_mod, "_WILLOW_HOME", tmp_path):
            entries = ledger_mod.load_recent(agent="hanuman")
        assert entries == []

    def test_loads_today_entries(self, tmp_path):
        with patch.object(ledger_mod, "_WILLOW_HOME", tmp_path):
            for i in range(3):
                ledger_mod.append(f"item {i}", entry_type=ledger.DECISION, agent="hanuman")
            entries = ledger_mod.load_recent(agent="hanuman")
        assert len(entries) == 3
        assert all(e["type"] == ledger.DECISION for e in entries)

    def test_limit_respected(self, tmp_path):
        with patch.object(ledger_mod, "_WILLOW_HOME", tmp_path):
            for i in range(20):
                ledger_mod.append(f"item {i}", entry_type=ledger.ACTION, agent="hanuman")
            entries = ledger_mod.load_recent(agent="hanuman", limit=5)
        assert len(entries) == 5

    def test_loads_yesterday_and_today(self, tmp_path):
        with patch.object(ledger_mod, "_WILLOW_HOME", tmp_path):
            # Write 2 yesterday entries
            ypath = tmp_path / f"ledger_hanuman_{_yesterday()}.jsonl"
            for i in range(2):
                ypath.parent.mkdir(parents=True, exist_ok=True)
                with ypath.open("a") as f:
                    f.write(json.dumps({
                        "ts": "2026-01-01T00:00:00+00:00",
                        "type": ledger.OBSERVATION,
                        "agent": "hanuman",
                        "session_id": "",
                        "content": f"yesterday {i}",
                    }) + "\n")
            # Write 2 today entries
            for i in range(2):
                ledger_mod.append(f"today {i}", entry_type=ledger.OBSERVATION, agent="hanuman")
            entries = ledger_mod.load_recent(agent="hanuman", days=2, limit=100)
        assert len(entries) == 4

    def test_skips_malformed_json(self, tmp_path):
        with patch.object(ledger_mod, "_WILLOW_HOME", tmp_path):
            p = ledger_mod._ledger_path("hanuman")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('{"valid": true, "type": "action", "agent": "hanuman", "session_id": "", "content": "ok", "ts": "2026-01-01T00:00:00+00:00"}\nnot json\n')
            entries = ledger_mod.load_recent(agent="hanuman")
        assert len(entries) == 1


# ---------------------------------------------------------------------------
# build_resume_context
# ---------------------------------------------------------------------------

class TestBuildResumeContext:
    def test_empty_when_no_ledger(self, tmp_path):
        with patch.object(ledger_mod, "_WILLOW_HOME", tmp_path):
            ctx = ledger_mod.build_resume_context(agent="hanuman")
        assert ctx == ""

    def test_contains_ledger_marker(self, tmp_path):
        with patch.object(ledger_mod, "_WILLOW_HOME", tmp_path):
            ledger_mod.append("decided to use postgres", entry_type=ledger.DECISION, agent="hanuman")
            ctx = ledger_mod.build_resume_context(agent="hanuman")
        assert "[LEDGER]" in ctx
        assert "decided to use postgres" in ctx

    def test_contains_entry_count(self, tmp_path):
        with patch.object(ledger_mod, "_WILLOW_HOME", tmp_path):
            for i in range(3):
                ledger_mod.append(f"entry {i}", entry_type=ledger.ACTION, agent="hanuman")
            ctx = ledger_mod.build_resume_context(agent="hanuman")
        assert "3 entries loaded" in ctx


# ---------------------------------------------------------------------------
# snapshot_for_compact
# ---------------------------------------------------------------------------

class TestSnapshotForCompact:
    def test_writes_compact_snapshot_entry(self, tmp_path):
        with patch.object(ledger_mod, "_WILLOW_HOME", tmp_path):
            ledger_mod.snapshot_for_compact(
                tool_name="Write",
                files_touched=["/src/foo.py", "/src/bar.py"],
                session_id="s42",
                note="pre-compact save",
            )
            p = ledger_mod._ledger_path(ledger_mod._AGENT)
        entry = json.loads(p.read_text().strip())
        assert entry["type"] == ledger.COMPACT_SNAPSHOT
        assert "pre-compact save" in entry["content"]
        assert "foo.py" in entry["content"]

    def test_no_details_snapshot(self, tmp_path):
        with patch.object(ledger_mod, "_WILLOW_HOME", tmp_path):
            ledger_mod.snapshot_for_compact()
            p = ledger_mod._ledger_path(ledger_mod._AGENT)
        entry = json.loads(p.read_text().strip())
        assert entry["type"] == ledger.COMPACT_SNAPSHOT
        assert "no details" in entry["content"]
