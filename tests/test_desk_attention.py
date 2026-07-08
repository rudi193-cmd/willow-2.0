"""tests/test_desk_attention.py"""
import json

from willow.fylgja.desk_attention import fetch_attention_summary


def test_fetch_attention_summary_nest_and_flags(tmp_path, monkeypatch):
    monkeypatch.setenv("WILLOW_HOME", str(tmp_path))
    monkeypatch.setenv("WILLOW_STORE_ROOT", str(tmp_path / "store"))
    monkeypatch.setattr(
        "willow.fylgja.willow_home.private_config_available", lambda: False
    )
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
    monkeypatch.setattr(
        "willow.fylgja.willow_home.private_config_available", lambda: False
    )

    s = fetch_attention_summary(agent="testagent", inbox=[])
    assert s.open_flags == 0


def test_dream_due_false_after_recent_dream_despite_stale_env(tmp_path, monkeypatch):
    from datetime import datetime, timezone

    private = tmp_path / "private"
    private.mkdir()
    (private / "willow.md").write_text("private\n", encoding="utf-8")
    stale = tmp_path / "stale-store"
    stale.mkdir()

    monkeypatch.setenv("WILLOW_STORE_ROOT", str(stale))
    monkeypatch.setattr(
        "willow.fylgja.willow_home.private_home", lambda: private
    )
    monkeypatch.setattr(
        "willow.fylgja.willow_home.private_config_available", lambda: True
    )

    from core.store_port import get_store_port

    store = get_store_port(root=str(private / "store"))
    store.put(
        "willow/dream",
        {
            "last_dream_at": datetime.now(timezone.utc).isoformat(),
            "locked": False,
        },
        record_id="state",
    )

    s = fetch_attention_summary(agent="willow", inbox=[])
    assert s.dream_due is False
