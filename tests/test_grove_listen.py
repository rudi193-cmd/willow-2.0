"""Tests for willow/grove_listen.py mention detection logic.
b17: GRVLS  ΔΣ=42
"""
import importlib
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _load(agent="hanuman", watch=None):
    """Reimport grove_listen with a specific WILLOW_AGENT_NAME."""
    env = {"WILLOW_AGENT_NAME": agent}
    if watch is not None:
        env["GROVE_MENTION_WATCH"] = watch
    else:
        env.pop("GROVE_MENTION_WATCH", None)
    with patch.dict(os.environ, env, clear=False):
        import willow.grove_listen as gl
        importlib.reload(gl)
    return gl


@pytest.fixture(autouse=True)
def _reset_cache():
    """Clear lru_cache between tests so reloads don't inherit stale regex."""
    import willow.grove_listen as gl
    gl._alias_regex.cache_clear()
    yield
    gl._alias_regex.cache_clear()


# ── is_broadcast_mention ──────────────────────────────────────────────────────

def test_broadcast_all():
    import willow.grove_listen as gl
    assert gl.is_broadcast_mention("hey @all, meeting now") is True


def test_broadcast_all_case_insensitive():
    import willow.grove_listen as gl
    assert gl.is_broadcast_mention("@All please read") is True


def test_broadcast_not_matched_mid_word():
    import willow.grove_listen as gl
    # @alliance should NOT match @all
    assert gl.is_broadcast_mention("join @alliance today") is False


def test_broadcast_false_for_unrelated():
    import willow.grove_listen as gl
    assert gl.is_broadcast_mention("just a regular message") is False


# ── is_direct_mention ─────────────────────────────────────────────────────────

def test_direct_hanuman_primary():
    import willow.grove_listen as gl
    assert gl.is_direct_mention("@hanuman can you check this", "hanuman") is True


def test_direct_hanuman_alias():
    import willow.grove_listen as gl
    assert gl.is_direct_mention("@hanu look at this", "hanuman") is True


def test_direct_vishwakarma_alias():
    import willow.grove_listen as gl
    assert gl.is_direct_mention("@vish build it", "vishwakarma") is True


def test_direct_karma_alias():
    import willow.grove_listen as gl
    assert gl.is_direct_mention("@karma deploy now", "vishwakarma") is True


def test_direct_no_match():
    import willow.grove_listen as gl
    assert gl.is_direct_mention("no one is mentioned here", "hanuman") is False


def test_direct_not_matched_mid_word():
    import willow.grove_listen as gl
    # @hanuman123 should NOT match @hanuman
    assert gl.is_direct_mention("@hanuman123 is not hanuman", "hanuman") is False


def test_direct_auto_normalised():
    import willow.grove_listen as gl
    # ALIASES stores "auto" lowercase; lookup normalises agent name
    assert gl.is_direct_mention("@auto are you there", "Auto") is True


# ── _watch_identities_ordered ─────────────────────────────────────────────────

def test_watch_identities_default_adds_auto():
    with patch.dict(os.environ, {"WILLOW_AGENT_NAME": "hanuman"}, clear=False):
        import willow.grove_listen as gl
        importlib.reload(gl)
        ids = gl._watch_identities_ordered()
    assert ids[0] == "hanuman"
    assert "Auto" in ids


def test_watch_identities_auto_agent_no_dup():
    with patch.dict(os.environ, {"WILLOW_AGENT_NAME": "Auto"}, clear=False):
        import willow.grove_listen as gl
        importlib.reload(gl)
        ids = gl._watch_identities_ordered()
    assert ids.count("Auto") + ids.count("auto") == 1


def test_watch_identities_explicit_watch():
    env = {"WILLOW_AGENT_NAME": "hanuman", "GROVE_MENTION_WATCH": "loki,heimdallr"}
    with patch.dict(os.environ, env, clear=False):
        import willow.grove_listen as gl
        importlib.reload(gl)
        ids = gl._watch_identities_ordered()
    assert ids == ["hanuman", "loki", "heimdallr"]


def test_watch_identities_dedup():
    env = {"WILLOW_AGENT_NAME": "hanuman", "GROVE_MENTION_WATCH": "hanuman,loki"}
    with patch.dict(os.environ, env, clear=False):
        import willow.grove_listen as gl
        importlib.reload(gl)
        ids = gl._watch_identities_ordered()
    assert ids.count("hanuman") == 1


# ── direct_mention_identity ───────────────────────────────────────────────────

def test_direct_mention_identity_returns_name():
    import willow.grove_listen as gl
    result = gl.direct_mention_identity("@hanu check the logs")
    assert result == "hanuman"


def test_direct_mention_identity_returns_none():
    import willow.grove_listen as gl
    result = gl.direct_mention_identity("nothing here")
    assert result is None


def test_direct_mention_identity_broadcast_returns_none():
    import willow.grove_listen as gl
    # broadcasts are handled separately — direct_mention_identity skips them
    result = gl.direct_mention_identity("@all please read")
    # @all is not in ALIASES for hanuman, so direct_mention_identity returns None
    assert result is None


# ── _alias_regex caching ──────────────────────────────────────────────────────

def test_alias_regex_cached():
    import willow.grove_listen as gl
    r1 = gl._alias_regex("@hanuman")
    r2 = gl._alias_regex("@hanuman")
    assert r1 is r2  # same object from cache


def test_reconnect_closes_stale_connection():
    gl = _load(agent="hanuman")
    stale = MagicMock(name="stale_conn")
    fresh = MagicMock(name="fresh_conn")
    cur = MagicMock()
    fresh.cursor.return_value = cur
    stale.cursor.return_value = cur

    gl.connect = MagicMock(side_effect=[stale, fresh])
    gl.load_channels = MagicMock(return_value={1: "general"})

    calls = {"n": 0}

    def select_side_effect(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("link down")
        raise KeyboardInterrupt()

    gl.select.select = select_side_effect
    gl.time.sleep = MagicMock()

    with pytest.raises(KeyboardInterrupt):
        gl._run()

    stale.close.assert_called_once()


def test_pidlock_exits_on_unexpected_lock_failure():
    gl = _load(agent="hanuman")
    lock_path = MagicMock()
    pid_path = MagicMock()
    lock = gl._PidLock(lock_path, pid_path)
    lock.lock_path.parent.mkdir = MagicMock()
    pid_path.parent.mkdir = MagicMock()
    lock._fh = MagicMock()
    lock._fh.fileno.return_value = 3

    with patch("willow.grove_listen.portalocker.lock", side_effect=OSError("perm")):
        with pytest.raises(SystemExit) as exc:
            lock.__enter__()
    assert exc.value.code == 1
