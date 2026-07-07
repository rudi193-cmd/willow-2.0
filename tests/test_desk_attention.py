"""tests/test_desk_attention.py"""
import json

from willow.fylgja.desk_attention import fetch_attention_summary


def test_fetch_attention_summary_nest_and_flags(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_HOME", str(tmp_path))
    monkeypatch.setenv("WILLOW_STORE_ROOT", str(tmp_path / "store"))
    (tmp_path / "nest-queue.json").write_text(json.dumps([
        {"status": "pending"},
        {"status": "done"},
    ]))

    from core.store_port import get_store_port

    store = get_store_port(root=str(tmp_path / "store"))
    store.put("testagent/flags", {"title": "real bug", "flag_state": "open"}, record_id="f1")
    store.put("testagent/flags", {"title": "closed bug", "flag_state": "closed"}, record_id="f2")
    store.put("testagent/flags", {"title": "Blessed path noise", "flag_state": "open"}, record_id="f3")
    store.put("testagent/gaps", {"title": "open gap", "status": "open"}, record_id="g1")

    s = fetch_attention_summary(agent="testagent", inbox=[])
    assert s.nest_pending == 1
    assert s.open_flags == 2
    assert "nest pending" in " · ".join(s.lines)
    assert "open flags" in " · ".join(s.lines)


def test_fetch_attention_summary_defaults_when_store_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_HOME", str(tmp_path))
    monkeypatch.setenv("WILLOW_STORE_ROOT", str(tmp_path / "store"))

    s = fetch_attention_summary(agent="testagent", inbox=[])
    assert s.open_flags == 0
