"""tests/test_desk_attention.py"""
import json

from willow.fylgja.desk_attention import fetch_attention_summary


def test_fetch_attention_summary_nest_and_flags(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_HOME", str(tmp_path))
    (tmp_path / "nest-queue.json").write_text(json.dumps([
        {"status": "pending"},
        {"status": "done"},
    ]))
    (tmp_path / "session_anchor.json").write_text(json.dumps({"open_flags": 3}))

    s = fetch_attention_summary(inbox=[])
    assert s.nest_pending == 1
    assert s.open_flags == 3
    assert "nest pending" in " · ".join(s.lines)
