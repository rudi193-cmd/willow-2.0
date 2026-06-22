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
    assert "would archive=1" in out


def _legacy_flag(flag_id):
    return {
        "id": flag_id,
        "source": "block_telemetry",
        "flag_state": "open",
        "title": "Blessed path for 'Bash' may be broken or missing",
        "rule_key": f"block-{flag_id}",
    }


def test_retire_legacy_archives_open_blessed_path_flags():
    store = _make_store([_legacy_flag("flag-old")], {})
    fake_module = types.ModuleType("core.willow_store")
    fake_module.WillowStore = lambda: store
    with patch.dict(sys.modules, {"core.willow_store": fake_module}):
        import importlib
        import scripts.archive_block_flags as m
        importlib.reload(m)
        with patch("scripts.archive_block_flags._load_store", return_value=store):
            count = m.retire_legacy_block_flags(dry_run=False)
    assert count == 1
    written = store.put.call_args.args[1]
    assert written["flag_state"] == "archived"
    assert "pre-#436" in written["archived_reason"]


def test_retire_legacy_skips_repeated_enforcement_titles():
    flag = {
        "id": "flag-new",
        "source": "block_telemetry",
        "flag_state": "open",
        "title": "Repeated enforcement: 'Bash' blocked 50× fleet-wide",
        "rule_key": "block-new",
    }
    store = _make_store([flag], {})
    import scripts.archive_block_flags as m
    with patch("scripts.archive_block_flags._load_store", return_value=store):
        assert m.retire_legacy_block_flags(dry_run=False) == 0
    put_calls = [c for c in store.put.call_args_list if "flags" in str(c.args[0])]
    assert not put_calls
