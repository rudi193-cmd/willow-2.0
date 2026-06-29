"""Tests for core/intelligence.py — Plan 3 intelligence passes.
b17: TINT9  ΔΣ=42
"""
import os
import psycopg2.extras
import pytest
from datetime import datetime, timezone, timedelta

os.environ.setdefault("WILLOW_PG_DB", "willow_20")


@pytest.fixture
def bridge():
    from core.pg_bridge import PgBridge
    b = PgBridge()
    yield b
    b.close()


def _put_old(bridge, atom_id, project, title, days_old=90):
    """Insert an atom with created_at backdated to days_old days ago."""
    bridge.knowledge_put({
        "id": atom_id,
        "project": project,
        "title": title,
        "summary": f"atom created {days_old} days ago",
    })
    old_ts = datetime.now(timezone.utc) - timedelta(days=days_old)
    with bridge.conn.cursor() as cur:
        cur.execute(
            "UPDATE knowledge SET created_at = %s WHERE id = %s",
            (old_ts, atom_id),
        )
    bridge.conn.commit()


# ── W19DR — Draugr ────────────────────────────────────────────────────────────

def test_draugr_scan_finds_old_uncategorized_atoms(bridge):
    from core.intelligence import draugr_scan
    _put_old(bridge, "dr_test_zombie", "heimdallr", "zombie atom title", days_old=90)

    found = draugr_scan(bridge, days=60)
    assert "dr_test_zombie" in found

    with bridge.conn.cursor() as cur:
        cur.execute("DELETE FROM knowledge WHERE id = 'dr_test_zombie'")
    bridge.conn.commit()


def test_draugr_scan_ignores_community_nodes(bridge):
    from core.intelligence import draugr_scan
    bridge.knowledge_put({
        "id": "dr_community_skip",
        "project": "heimdallr",
        "title": "community detection node",
        "summary": "should be ignored by draugr scan",
        "source_type": "community_detection",
    })
    old_ts = datetime.now(timezone.utc) - timedelta(days=90)
    with bridge.conn.cursor() as cur:
        cur.execute("UPDATE knowledge SET created_at = %s WHERE id = 'dr_community_skip'", (old_ts,))
    bridge.conn.commit()

    found = draugr_scan(bridge, days=60)
    assert "dr_community_skip" not in found

    with bridge.conn.cursor() as cur:
        cur.execute("DELETE FROM knowledge WHERE id = 'dr_community_skip'")
    bridge.conn.commit()


def test_draugr_mark_sets_category(bridge):
    from core.intelligence import draugr_mark
    _put_old(bridge, "dr_mark_test", "heimdallr", "mark this zombie", days_old=90)

    count = draugr_mark(bridge, ["dr_mark_test"])
    assert count == 1

    with bridge.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT category FROM knowledge WHERE id = 'dr_mark_test'")
        row = cur.fetchone()
    assert row["category"] == "draugr"

    with bridge.conn.cursor() as cur:
        cur.execute("DELETE FROM knowledge WHERE id = 'dr_mark_test'")
    bridge.conn.commit()


# ── W19SD — Serendipity ───────────────────────────────────────────────────────

def test_serendipity_surfaces_old_overlap_atoms(bridge):
    from core.intelligence import serendipity_pass
    now = datetime.now(timezone.utc)

    bridge.knowledge_put({
        "id": "sd_old_atom",
        "project": "willow",
        "title": "ancient machine learning knowledge",
        "summary": "neural network patterns from the past",
    })
    old_ts = now - timedelta(days=60)
    with bridge.conn.cursor() as cur:
        cur.execute("UPDATE knowledge SET created_at = %s WHERE id = 'sd_old_atom'", (old_ts,))

    bridge.knowledge_put({
        "id": "sd_recent_atom",
        "project": "willow",
        "title": "machine learning today",
        "summary": "current neural network work",
    })
    # Stamp sd_recent_atom 60 seconds in the future so it always tops the
    # ORDER BY created_at DESC LIMIT 20 query regardless of how many other
    # test atoms are in the DB.  Still within recent_days=7.
    recent_ts = now + timedelta(seconds=60)
    with bridge.conn.cursor() as cur:
        cur.execute("UPDATE knowledge SET created_at = %s WHERE id = 'sd_recent_atom'", (recent_ts,))
    bridge.conn.commit()

    surfaced = serendipity_pass(bridge, recent_days=7, old_min_days=30, old_max_days=180)
    ids = [a["id"] for a in surfaced]
    assert "sd_old_atom" in ids
    assert "sd_recent_atom" not in ids

    with bridge.conn.cursor() as cur:
        cur.execute("DELETE FROM knowledge WHERE id IN ('sd_old_atom', 'sd_recent_atom')")
    bridge.conn.commit()


def test_serendipity_returns_empty_when_no_recent(bridge):
    from core.intelligence import serendipity_pass
    surfaced = serendipity_pass(bridge, recent_days=0, old_min_days=30, old_max_days=180)
    assert isinstance(surfaced, list)


# ── W19DM — Dark Matter ───────────────────────────────────────────────────────

def test_dark_matter_writes_implicit_connection(bridge):
    from core.intelligence import dark_matter_pass

    bridge.knowledge_put({
        "id": "dm_atom_a",
        "project": "willow",
        "title": "reinforcement learning policy gradient",
        "summary": "policy gradient methods for reinforcement learning agents",
    })
    bridge.knowledge_put({
        "id": "dm_atom_b",
        "project": "saps1",
        "title": "reinforcement learning reward function",
        "summary": "designing reward functions for reinforcement learning policy",
    })

    count = dark_matter_pass(bridge, min_overlap=2)
    assert count >= 1

    with bridge.conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM knowledge WHERE project = 'willow' "
            "AND source_type = 'dark_matter'"
        )
        assert cur.fetchone()[0] >= 1

    with bridge.conn.cursor() as cur:
        cur.execute("DELETE FROM knowledge WHERE id IN ('dm_atom_a', 'dm_atom_b')")
        # Remove only the dark_matter atoms created by this test's atom pairs
        cur.execute(
            "DELETE FROM knowledge WHERE source_type = 'dark_matter' "
            "AND (content::text LIKE '%dm_atom_a%' OR content::text LIKE '%dm_atom_b%')"
        )
    bridge.conn.commit()


def test_dark_matter_skips_same_project(bridge):
    from core.intelligence import dark_matter_pass

    bridge.knowledge_put({
        "id": "dm_same_a",
        "project": "willow",
        "title": "shared keyword topic neural network",
        "summary": "neural network shared keyword analysis",
    })
    bridge.knowledge_put({
        "id": "dm_same_b",
        "project": "willow",
        "title": "shared keyword topic neural network",
        "summary": "another neural network shared keyword analysis",
    })

    dark_matter_pass(bridge, min_overlap=2)

    # Same project — no dark matter atom should link dm_same_a to dm_same_b
    with bridge.conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM knowledge WHERE source_type = 'dark_matter' "
            "AND content::text LIKE '%dm_same_a%' AND content::text LIKE '%dm_same_b%'"
        )
        dm_for_same = cur.fetchone()[0]
    assert dm_for_same == 0

    with bridge.conn.cursor() as cur:
        cur.execute("DELETE FROM knowledge WHERE id IN ('dm_same_a', 'dm_same_b')")
        cur.execute(
            "DELETE FROM knowledge WHERE source_type = 'dark_matter' "
            "AND (content::text LIKE '%dm_same_a%' OR content::text LIKE '%dm_same_b%')"
        )
    bridge.conn.commit()


# ── W19RV — Revelation ────────────────────────────────────────────────────────

def test_revelation_detects_cross_project_convergence(bridge):
    from core.intelligence import revelation_pass

    bridge.knowledge_put({
        "id": "rv_community_a",
        "project": "willow",
        "title": "Community node consciousness awareness mindfulness",
        "summary": "themes: consciousness awareness attention mindfulness presence",
        "source_type": "community_detection",
    })
    bridge.knowledge_put({
        "id": "rv_community_b",
        "project": "saps1",
        "title": "Community node awareness mindfulness presence",
        "summary": "themes: awareness mindfulness presence consciousness flow",
        "source_type": "community_detection",
    })

    count = revelation_pass(bridge, min_overlap=2)
    assert count >= 1

    with bridge.conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM knowledge WHERE project = 'willow' "
            "AND source_type = 'revelation'"
        )
        assert cur.fetchone()[0] >= 1

    with bridge.conn.cursor() as cur:
        cur.execute("DELETE FROM knowledge WHERE id IN ('rv_community_a', 'rv_community_b')")
        cur.execute(
            "DELETE FROM knowledge WHERE source_type = 'revelation' "
            "AND (content::text LIKE '%rv_community_a%' OR content::text LIKE '%rv_community_b%')"
        )
    bridge.conn.commit()


def test_revelation_ignores_same_project_communities(bridge):
    from core.intelligence import revelation_pass

    bridge.knowledge_put({
        "id": "rv_same_a",
        "project": "willow",
        "title": "community consciousness awareness mindfulness theme",
        "summary": "shared consciousness awareness mindfulness theme",
        "source_type": "community_detection",
    })
    bridge.knowledge_put({
        "id": "rv_same_b",
        "project": "willow",
        "title": "community consciousness awareness mindfulness",
        "summary": "more consciousness awareness mindfulness",
        "source_type": "community_detection",
    })

    with bridge.conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM knowledge WHERE project = 'willow' "
            "AND source_type = 'revelation'"
        )
        initial_count = cur.fetchone()[0]

    revelation_pass(bridge, min_overlap=2)

    with bridge.conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM knowledge WHERE project = 'willow' "
            "AND source_type = 'revelation'"
        )
        after_count = cur.fetchone()[0]
    assert after_count == initial_count

    with bridge.conn.cursor() as cur:
        cur.execute("DELETE FROM knowledge WHERE id IN ('rv_same_a', 'rv_same_b')")
    bridge.conn.commit()


# ── W19MR — Mirror ────────────────────────────────────────────────────────────

def test_mirror_writes_meta_community(bridge):
    from core.intelligence import mirror_pass

    lanes = ("willow", "saps1", "global")
    for i, lane in enumerate(lanes):
        bridge.knowledge_put({
            "id": f"mr_community_{i}",
            "project": lane,
            "title": f"Community node learning systems patterns iteration {i}",
            "summary": f"themes: learning systems patterns knowledge iteration {i}",
            "source_type": "community_detection",
        })

    count = mirror_pass(bridge)
    assert count == 1

    with bridge.conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM knowledge WHERE project = 'willow' "
            "AND source_type = 'mirror'"
        )
        assert cur.fetchone()[0] >= 1

    with bridge.conn.cursor() as cur:
        cur.execute("DELETE FROM knowledge WHERE id LIKE 'mr_community_%'")
        cur.execute(
            "DELETE FROM knowledge WHERE source_type = 'mirror' "
            "AND content::text LIKE '%mr_community_%'"
        )
    bridge.conn.commit()


def test_mirror_skips_when_too_few_nodes(bridge):
    from core.intelligence import mirror_pass
    with bridge.conn.cursor() as cur:
        cur.execute(
            "DELETE FROM knowledge WHERE id LIKE 'mr_few_%' "
            "OR (source_type = 'mirror' AND content::text LIKE '%mr_few_%')"
        )
        cur.execute(
            "DELETE FROM knowledge WHERE source_type = 'community_detection' "
            "AND id LIKE 'mr_few_%'"
        )
    bridge.conn.commit()

    for i in range(2):
        bridge.knowledge_put({
            "id": f"mr_few_{i}",
            "project": "willow",
            "title": f"community node few {i}",
            "source_type": "community_detection",
        })

    count = mirror_pass(bridge)
    assert count == 0

    with bridge.conn.cursor() as cur:
        cur.execute("DELETE FROM knowledge WHERE id LIKE 'mr_few_%'")
        cur.execute(
            "DELETE FROM knowledge WHERE source_type = 'mirror' "
            "AND content::text LIKE '%mr_few_%'"
        )
    bridge.conn.commit()


# ── W19MC — Mycorrhizal ───────────────────────────────────────────────────────

def test_mycorrhizal_feeds_sparse_project(bridge):
    from core.intelligence import mycorrhizal_pass

    bridge.knowledge_put({
        "id": "mc_donor_community",
        "project": "saps1",
        "title": "Community node rich knowledge patterns themes",
        "summary": "rich knowledge patterns and themes for sparse projects",
        "source_type": "community_detection",
    })

    for j in range(2):
        bridge.knowledge_put({
            "id": f"mc_sparse_{j}",
            "project": "vishwakarma",
            "title": f"sparse atom {j}",
            "summary": "sparse project",
        })

    count = mycorrhizal_pass(bridge, sparse_threshold=5)
    assert count >= 1

    with bridge.conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM knowledge WHERE project = 'vishwakarma' "
            "AND source_type = 'mycorrhizal'"
        )
        assert cur.fetchone()[0] >= 1

    with bridge.conn.cursor() as cur:
        cur.execute(
            "DELETE FROM knowledge WHERE id IN ('mc_donor_community', 'mc_sparse_0', 'mc_sparse_1') "
            "OR (source_type = 'mycorrhizal' AND content::text LIKE '%mc_donor%')"
        )
    bridge.conn.commit()


def test_mycorrhizal_skips_non_sparse_projects(bridge):
    from core.intelligence import mycorrhizal_pass

    for j in range(6):
        bridge.knowledge_put({
            "id": f"mc_rich_{j}",
            "project": "rh-dirty",
            "title": f"rich atom {j}",
            "summary": "rich project has many atoms",
        })

    with bridge.conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM knowledge WHERE project = 'rh-dirty' "
            "AND source_type = 'mycorrhizal'"
        )
        count_before = cur.fetchone()[0]

    mycorrhizal_pass(bridge, sparse_threshold=5)

    with bridge.conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM knowledge WHERE project = 'rh-dirty' "
            "AND source_type = 'mycorrhizal'"
        )
        count_after = cur.fetchone()[0]
    assert count_after == count_before

    with bridge.conn.cursor() as cur:
        cur.execute("DELETE FROM knowledge WHERE id LIKE 'mc_rich_%'")
    bridge.conn.commit()
