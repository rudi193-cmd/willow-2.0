"""Tests for canonical KB lane write-time enforcement."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.canonical_lanes import (
    CANONICAL_LANES,
    OffLaneProjectError,
    normalize_project,
)
from core.pg_bridge import PgBridge


class TestNormalizeProject:
    def test_canonical_pass_through(self):
        for lane in CANONICAL_LANES:
            assert normalize_project(lane) == lane

    def test_agent_alias_hanuman_to_willow(self):
        assert normalize_project("hanuman", agent="hanuman") == "willow"

    def test_synthetic_dark_matter_to_willow(self):
        assert normalize_project("dark_matter") == "willow"

    def test_derived_source_type_off_lane_to_willow(self):
        assert normalize_project(
            "some-rogue-label",
            source_type="revelation",
        ) == "willow"

    def test_empty_defaults_global(self):
        assert normalize_project(None) == "global"
        assert normalize_project("") == "global"

    def test_off_lane_raises(self):
        with pytest.raises(OffLaneProjectError):
            normalize_project("not-a-real-lane")


@pytest.fixture
def pg():
    bridge = PgBridge()
    with bridge.conn.cursor() as cur:
        cur.execute(
            "DELETE FROM knowledge WHERE id LIKE 'lane_test_%'"
        )
    bridge.conn.commit()
    return bridge


def test_knowledge_put_rejects_off_lane(pg):
    with pytest.raises(OffLaneProjectError):
        pg.knowledge_put({
            "id": "lane_test_bad",
            "project": "rogue_fragmented_lane",
            "title": "should not land",
            "summary": "off-lane write blocked",
        })


def test_knowledge_put_coerces_hanuman(pg):
    pg.knowledge_put({
        "id": "lane_test_hanuman",
        "project": "hanuman",
        "title": "agent alias",
        "summary": "maps to willow",
    })
    with pg.conn.cursor() as cur:
        cur.execute("SELECT project FROM knowledge WHERE id = 'lane_test_hanuman'")
        row = cur.fetchone()
    assert row[0] == "willow"


def test_knowledge_put_coerces_synthetic(pg):
    pg.knowledge_put({
        "id": "lane_test_dm",
        "project": "dark_matter",
        "title": "synthetic",
        "summary": "maps to willow",
        "source_type": "dark_matter",
    })
    with pg.conn.cursor() as cur:
        cur.execute("SELECT project FROM knowledge WHERE id = 'lane_test_dm'")
        row = cur.fetchone()
    assert row[0] == "willow"
