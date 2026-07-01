"""Tests for core/intelligence.py — Plan 3 intelligence passes.
b17: TINT9  ΔΣ=42
"""
import os
import psycopg2.extras
import pytest
from datetime import datetime, timezone, timedelta

os.environ.setdefault("WILLOW_PG_DB", "willow_20_test")

# Unique tokens — isolate fixtures from the shared willow_20_test corpus.
_SD_MARKER = "xw19sd_uniq_surface_z99"
_RV_CROSS_A = "xrv19cross_aa_token"
_RV_CROSS_B = "xrv19cross_bb_token"
_RV_SAME_MARKER = "xrv19same_only_z88"


def _pg(bridge):
    """Return a live connection (re-acquire from pool when stale)."""
    bridge._ensure_conn()
    return bridge.conn


def _pg_cursor(bridge, **kwargs):
    """Resilient cursor context manager (reconnect on OperationalError)."""
    return bridge.cursor(**kwargs)


def _sparse_canonical_lane(bridge, *, sparse_threshold: int = 5) -> str:
    """Pick a canonical lane that stays sparse after adding two fixture atoms."""
    from core.canonical_lanes import CANONICAL_LANES

    for lane in sorted(CANONICAL_LANES):
        if lane == "global":
            continue
        with _pg_cursor(bridge,) as cur:
            cur.execute(
                "SELECT COUNT(*) FROM knowledge WHERE invalid_at IS NULL AND project = %s",
                (lane,),
            )
            n = cur.fetchone()[0]
        if n + 2 < sparse_threshold:
            return lane
    pytest.skip("no canonical lane sparse enough for mycorrhizal fixture")


@pytest.fixture
def bridge():
    from core.pg_bridge import PgBridge
    b = PgBridge()
    b._ensure_conn()
    try:
        yield b
    finally:
        try:
            if b.conn is not None and not b.conn.closed:
                b.conn.rollback()
        except Exception:
            pass
        b.close()


def _revelation_count_for_ids(bridge, *atom_ids: str) -> int:
    """Revelation atoms whose payload references any of the given node ids."""
    clauses = " OR ".join("content::text LIKE %s" for _ in atom_ids)
    params = tuple(f"%{aid}%" for aid in atom_ids)
    with _pg_cursor(bridge,) as cur:
        cur.execute(
            f"SELECT COUNT(*) FROM knowledge WHERE source_type = 'revelation' "
            f"AND ({clauses})",
            params,
        )
        return cur.fetchone()[0]


def _put_old(bridge, atom_id, project, title, days_old=90):
    """Insert an atom with created_at backdated to days_old days ago."""
    bridge.knowledge_put({
        "id": atom_id,
        "project": project,
        "title": title,
        "summary": f"atom created {days_old} days ago",
    })
    old_ts = datetime.now(timezone.utc) - timedelta(days=days_old)
    with _pg_cursor(bridge,) as cur:
        cur.execute(
            "UPDATE knowledge SET created_at = %s WHERE id = %s",
            (old_ts, atom_id),
        )
    _pg(bridge).commit()


# ── W19DR — Draugr ────────────────────────────────────────────────────────────

def test_draugr_scan_finds_old_uncategorized_atoms(bridge):
    from core.intelligence import draugr_scan
    _put_old(bridge, "dr_test_zombie", "heimdallr", "zombie atom title", days_old=90)

    found = draugr_scan(bridge, days=60)
    assert "dr_test_zombie" in found

    with _pg_cursor(bridge,) as cur:
        cur.execute("DELETE FROM knowledge WHERE id = 'dr_test_zombie'")
    _pg(bridge).commit()


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
    with _pg_cursor(bridge,) as cur:
        cur.execute("UPDATE knowledge SET created_at = %s WHERE id = 'dr_community_skip'", (old_ts,))
    _pg(bridge).commit()

    found = draugr_scan(bridge, days=60)
    assert "dr_community_skip" not in found

    with _pg_cursor(bridge,) as cur:
        cur.execute("DELETE FROM knowledge WHERE id = 'dr_community_skip'")
    _pg(bridge).commit()


def test_draugr_mark_sets_category(bridge):
    from core.intelligence import draugr_mark
    _put_old(bridge, "dr_mark_test", "heimdallr", "mark this zombie", days_old=90)

    count = draugr_mark(bridge, ["dr_mark_test"])
    assert count == 1

    with bridge.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT category FROM knowledge WHERE id = 'dr_mark_test'")
        row = cur.fetchone()
    assert row["category"] == "draugr"

    with _pg_cursor(bridge,) as cur:
        cur.execute("DELETE FROM knowledge WHERE id = 'dr_mark_test'")
    _pg(bridge).commit()


# ── W19SD — Serendipity ───────────────────────────────────────────────────────

def test_serendipity_surfaces_old_overlap_atoms(bridge):
    from core.intelligence import serendipity_pass
    now = datetime.now(timezone.utc)

    with _pg_cursor(bridge,) as cur:
        cur.execute(
            "DELETE FROM knowledge WHERE id IN ('sd_old_atom', 'sd_recent_atom') "
            "OR title = %s OR summary = %s",
            (_SD_MARKER, _SD_MARKER),
        )
    _pg(bridge).commit()

    bridge.knowledge_put({
        "id": "sd_old_atom",
        "project": "willow",
        "title": _SD_MARKER,
        "summary": _SD_MARKER,
    })
    old_ts = now - timedelta(days=60)
    with _pg_cursor(bridge,) as cur:
        cur.execute("UPDATE knowledge SET created_at = %s WHERE id = 'sd_old_atom'", (old_ts,))

    bridge.knowledge_put({
        "id": "sd_recent_atom",
        "project": "willow",
        "title": _SD_MARKER,
        "summary": _SD_MARKER,
    })
    # Stamp sd_recent_atom 60 seconds in the future so it always tops the
    # ORDER BY created_at DESC LIMIT 20 query regardless of how many other
    # test atoms are in the DB.  Still within recent_days=7.
    recent_ts = now + timedelta(seconds=60)
    with _pg_cursor(bridge,) as cur:
        cur.execute("UPDATE knowledge SET created_at = %s WHERE id = 'sd_recent_atom'", (recent_ts,))
    _pg(bridge).commit()

    surfaced = serendipity_pass(
        bridge, recent_days=7, old_min_days=30, old_max_days=180,
        promote_surfaced=False,
    )
    ids = [a["id"] for a in surfaced]
    assert "sd_old_atom" in ids
    assert "sd_recent_atom" not in ids

    with _pg_cursor(bridge,) as cur:
        cur.execute(
            "DELETE FROM knowledge WHERE id IN ('sd_old_atom', 'sd_recent_atom') "
            "OR title = %s OR summary = %s",
            (_SD_MARKER, _SD_MARKER),
        )
    _pg(bridge).commit()


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

    with _pg_cursor(bridge,) as cur:
        cur.execute(
            "SELECT COUNT(*) FROM knowledge WHERE project = 'willow' "
            "AND source_type = 'dark_matter'"
        )
        assert cur.fetchone()[0] >= 1

    with _pg_cursor(bridge,) as cur:
        cur.execute("DELETE FROM knowledge WHERE id IN ('dm_atom_a', 'dm_atom_b')")
        # Remove only the dark_matter atoms created by this test's atom pairs
        cur.execute(
            "DELETE FROM knowledge WHERE source_type = 'dark_matter' "
            "AND (content::text LIKE '%dm_atom_a%' OR content::text LIKE '%dm_atom_b%')"
        )
    _pg(bridge).commit()


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
    with _pg_cursor(bridge,) as cur:
        cur.execute(
            "SELECT COUNT(*) FROM knowledge WHERE source_type = 'dark_matter' "
            "AND content::text LIKE '%dm_same_a%' AND content::text LIKE '%dm_same_b%'"
        )
        dm_for_same = cur.fetchone()[0]
    assert dm_for_same == 0

    with _pg_cursor(bridge,) as cur:
        cur.execute("DELETE FROM knowledge WHERE id IN ('dm_same_a', 'dm_same_b')")
        cur.execute(
            "DELETE FROM knowledge WHERE source_type = 'dark_matter' "
            "AND (content::text LIKE '%dm_same_a%' OR content::text LIKE '%dm_same_b%')"
        )
    _pg(bridge).commit()


# ── W19RV — Revelation ────────────────────────────────────────────────────────

def test_revelation_detects_cross_project_convergence(bridge):
    from core.intelligence import revelation_pass

    with _pg_cursor(bridge,) as cur:
        cur.execute(
            "DELETE FROM knowledge WHERE id IN ('rv_community_a', 'rv_community_b') "
            "OR (source_type = 'revelation' AND (content::text LIKE '%rv_community_a%' "
            "OR content::text LIKE '%rv_community_b%'))"
        )
    _pg(bridge).commit()

    bridge.knowledge_put({
        "id": "rv_community_a",
        "project": "willow",
        "title": f"{_RV_CROSS_A} {_RV_CROSS_B}",
        "summary": f"{_RV_CROSS_A} {_RV_CROSS_B}",
        "source_type": "community_detection",
    })
    bridge.knowledge_put({
        "id": "rv_community_b",
        "project": "saps1",
        "title": f"{_RV_CROSS_A} {_RV_CROSS_B}",
        "summary": f"{_RV_CROSS_A} {_RV_CROSS_B}",
        "source_type": "community_detection",
    })

    count = revelation_pass(bridge, min_overlap=2)
    assert count >= 1
    assert _revelation_count_for_ids(bridge, "rv_community_a", "rv_community_b") >= 1

    with _pg_cursor(bridge,) as cur:
        cur.execute("DELETE FROM knowledge WHERE id IN ('rv_community_a', 'rv_community_b')")
        cur.execute(
            "DELETE FROM knowledge WHERE source_type = 'revelation' "
            "AND (content::text LIKE '%rv_community_a%' OR content::text LIKE '%rv_community_b%')"
        )
    _pg(bridge).commit()


def test_revelation_ignores_same_project_communities(bridge):
    from core.intelligence import revelation_pass

    with _pg_cursor(bridge,) as cur:
        cur.execute("DELETE FROM knowledge WHERE id IN ('rv_same_a', 'rv_same_b')")
    _pg(bridge).commit()

    bridge.knowledge_put({
        "id": "rv_same_a",
        "project": "willow",
        "title": _RV_SAME_MARKER,
        "summary": _RV_SAME_MARKER,
        "source_type": "community_detection",
    })
    bridge.knowledge_put({
        "id": "rv_same_b",
        "project": "willow",
        "title": _RV_SAME_MARKER,
        "summary": _RV_SAME_MARKER,
        "source_type": "community_detection",
    })

    revelation_pass(bridge, min_overlap=2)

    assert _revelation_count_for_ids(bridge, "rv_same_a", "rv_same_b") == 0

    with _pg_cursor(bridge,) as cur:
        cur.execute("DELETE FROM knowledge WHERE id IN ('rv_same_a', 'rv_same_b')")
    _pg(bridge).commit()


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

    with _pg_cursor(bridge,) as cur:
        cur.execute(
            "SELECT COUNT(*) FROM knowledge WHERE project = 'willow' "
            "AND source_type = 'mirror'"
        )
        assert cur.fetchone()[0] >= 1

    with _pg_cursor(bridge,) as cur:
        cur.execute("DELETE FROM knowledge WHERE id LIKE 'mr_community_%'")
        cur.execute(
            "DELETE FROM knowledge WHERE source_type = 'mirror' "
            "AND content::text LIKE '%mr_community_%'"
        )
    _pg(bridge).commit()


def test_mirror_skips_when_too_few_nodes():
    from core.intelligence import _mirror_from_nodes

    nodes = [
        {
            "id": "mr_few_0",
            "project": "willow",
            "title": "community node few 0",
            "summary": "few nodes mirror fixture",
        },
        {
            "id": "mr_few_1",
            "project": "willow",
            "title": "community node few 1",
            "summary": "few nodes mirror fixture",
        },
    ]
    assert _mirror_from_nodes(nodes) is None


# ── W19MC — Mycorrhizal ───────────────────────────────────────────────────────

def test_mycorrhizal_feeds_sparse_project(bridge):
    from core.intelligence import mycorrhizal_pass

    sparse_lane = _sparse_canonical_lane(bridge, sparse_threshold=5)

    with _pg_cursor(bridge,) as cur:
        cur.execute(
            "DELETE FROM knowledge WHERE id IN ('mc_donor_community', 'mc_sparse_0', 'mc_sparse_1') "
            "OR (project = %s AND source_type = 'mycorrhizal' AND id LIKE 'myco_%%')",
            (sparse_lane,),
        )
    _pg(bridge).commit()

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
            "project": sparse_lane,
            "title": f"sparse atom {j}",
            "summary": "sparse project",
        })

    count = mycorrhizal_pass(bridge, sparse_threshold=5)
    assert count >= 1

    with _pg_cursor(bridge,) as cur:
        cur.execute(
            "SELECT COUNT(*) FROM knowledge WHERE project = %s "
            "AND source_type = 'mycorrhizal'",
            (sparse_lane,),
        )
        assert cur.fetchone()[0] >= 1

    with _pg_cursor(bridge,) as cur:
        cur.execute(
            "DELETE FROM knowledge WHERE id IN ('mc_donor_community', 'mc_sparse_0', 'mc_sparse_1') "
            "OR (project = %s AND source_type = 'mycorrhizal' AND id LIKE 'myco_%%')",
            (sparse_lane,),
        )
    _pg(bridge).commit()


def test_mycorrhizal_skips_non_sparse_projects(bridge):
    from core.intelligence import mycorrhizal_pass

    for j in range(6):
        bridge.knowledge_put({
            "id": f"mc_rich_{j}",
            "project": "rh-dirty",
            "title": f"rich atom {j}",
            "summary": "rich project has many atoms",
        })

    with _pg_cursor(bridge,) as cur:
        cur.execute(
            "SELECT COUNT(*) FROM knowledge WHERE project = 'rh-dirty' "
            "AND source_type = 'mycorrhizal'"
        )
        count_before = cur.fetchone()[0]

    mycorrhizal_pass(bridge, sparse_threshold=5)

    with _pg_cursor(bridge,) as cur:
        cur.execute(
            "SELECT COUNT(*) FROM knowledge WHERE project = 'rh-dirty' "
            "AND source_type = 'mycorrhizal'"
        )
        count_after = cur.fetchone()[0]
    assert count_after == count_before

    with _pg_cursor(bridge,) as cur:
        cur.execute("DELETE FROM knowledge WHERE id LIKE 'mc_rich_%'")
    _pg(bridge).commit()
