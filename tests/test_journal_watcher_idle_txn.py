"""journal_watcher poll must not leave idle-in-transaction on PgBridge."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_WATCHER = _ROOT / "agents" / "hanuman" / "bin" / "journal_watcher.py"


def _load_watcher():
    spec = importlib.util.spec_from_file_location("journal_watcher", _WATCHER)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["journal_watcher"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def watcher():
    return _load_watcher()


def test_pending_entries_rolls_back_after_read(watcher):
    pg = MagicMock()
    cur = MagicMock()
    cur.fetchall.return_value = [("entry-1",), ("entry-2",)]
    pg.conn.cursor.return_value.__enter__.return_value = cur

    ids = watcher._pending_entries(pg)

    assert ids == ["entry-1", "entry-2"]
    cur.execute.assert_called_once()
    pg.conn.rollback.assert_called_once()
