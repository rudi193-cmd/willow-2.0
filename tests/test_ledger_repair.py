"""FRANK ledger chain repair (PR 4)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.pg_bridge import PgBridge


@pytest.fixture
def pg():
    bridge = PgBridge()
    with bridge.conn.cursor() as cur:
        cur.execute("DELETE FROM frank_ledger WHERE project = %s", ("repair_test",))
    bridge.conn.commit()
    return bridge


def test_ledger_repair_fixes_forked_prev_hash(pg):
    a = pg.ledger_append("repair_test", "first", {"n": 1})
    b = pg.ledger_append("repair_test", "second", {"n": 2})
    assert pg.ledger_verify()["valid"] is True

    with pg.conn.cursor() as cur:
        cur.execute(
            "UPDATE frank_ledger SET prev_hash = %s WHERE id = %s",
            ("deadbeef" * 8, b),
        )
    pg.conn.commit()
    broken = pg.ledger_verify()
    assert broken["valid"] is False
    assert broken["broken_at"] == b

    preview = pg.ledger_repair_chain(dry_run=True)
    assert preview["would_repair"] >= 1

    result = pg.ledger_repair_chain(dry_run=False)
    assert result["repaired"] >= 1
    assert result["valid_after"] is True
    assert pg.ledger_verify()["valid"] is True

    rows = pg.ledger_read(project="repair_test", limit=10)
    ids = {r["id"] for r in rows}
    assert {a, b} <= ids
