"""Tests for scripts/archive_block_flags.py — corrections lifecycle part (c)."""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import sys
import types


def _make_store(flags, telemetry_by_key):
    store = MagicMock()

    def _all(collection):
        if "flags" in collection:
            return list(flags)
        return []

    def _get(collection, record_id):
        if "block_telemetry" in collection:
            return telemetry_by_key.get(record_id)
        return None

    store.all.side_effect = _all
    store.get.side_effect = _get
    return store


def _run(store, days=7, dry_run=False):
    fake_module = types.ModuleType("core.willow_store")
    fake_module.WillowStore = lambda: store
    with patch.dict(sys.modules, {"core.willow_store": fake_module}):
        import importlib
        import scripts.archive_block_flags as m
        importlib.reload(m)
        with patch("scripts.archive_block_flags._load_store", return_value=store):
            import io
            import contextlib
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                with patch("sys.argv", ["archive_block_flags.py"] + (["--dry-run"] if dry_run else []) + ["--days", str(days)]):
                    m.main()
    return buf.getvalue(), store


NOW = datetime.now(timezone.utc)
OLD = (NOW - timedelta(days=10)).isoformat()
RECENT = (NOW - timedelta(days=2)).isoformat()


def _flag(flag_id, state, rule_key):
    return {"id": flag_id, "source": "block_telemetry", "flag_state": state, "rule_key": rule_key}


def _telemetry(last_seen):
    return {"last_seen": last_seen, "hit_count": 5}


def test_archives_resolved_silent_flag():
    store = _make_store(
        [_flag("flag-abc", "resolved", "block-abc")],
        {"block-abc": _telemetry(OLD)},
    )
    out, store = _run(store, days=7)
    put_calls = [c for c in store.put.call_args_list if "flags" in str(c.args[0])]
    assert put_calls, "Should archive the silent resolved flag"
    written = put_calls[0].args[1]
    assert written["flag_state"] == "archived"
    assert "archived_at" in written


def test_skips_resolved_flag_with_recent_activity():
    store = _make_store(
        [_flag("flag-abc", "resolved", "block-abc")],
        {"block-abc": _telemetry(RECENT)},
    )
    out, store = _run(store, days=7)
    put_calls = [c for c in store.put.call_args_list if "flags" in str(c.args[0])]
    assert not put_calls, "Should not archive a flag whose rule is still firing"
    assert "still active" in out


def test_skips_open_flags():
    store = _make_store(
        [_flag("flag-abc", "open", "block-abc")],
        {"block-abc": _telemetry(OLD)},
    )
    out, store = _run(store, days=7)
    put_calls = [c for c in store.put.call_args_list if "flags" in str(c.args[0])]
    assert not put_calls, "Should not touch open flags"


def test_skips_non_block_telemetry_flags():
    flag = {"id": "flag-manual", "source": "manual", "flag_state": "resolved", "rule_key": "x"}
    store = _make_store([flag], {})
    out, store = _run(store, days=7)
    put_calls = [c for c in store.put.call_args_list if "flags" in str(c.args[0])]
    assert not put_calls, "Should only process block_telemetry flags"


def test_dry_run_does_not_write():
    store = _make_store(
        [_flag("flag-abc", "resolved", "block-abc")],
        {"block-abc": _telemetry(OLD)},
    )
    out, store = _run(store, days=7, dry_run=True)
    put_calls = [c for c in store.put.call_args_list if "flags" in str(c.args[0])]
    assert not put_calls, "Dry run should not write anything"
    assert "dry-run" in out
