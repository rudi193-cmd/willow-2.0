# b17: EBB0F  ΔΣ=42
from datetime import datetime, timezone, timedelta
from core.actr import activation, score_atoms


def test_activation_decreases_with_time():
    a_recent = activation(0.8, recency_seconds=60)
    a_old    = activation(0.8, recency_seconds=86400)
    assert a_recent > a_old


def test_activation_increases_with_importance():
    a_high = activation(1.0, recency_seconds=3600)
    a_low  = activation(0.1, recency_seconds=3600)
    assert a_high > a_low


def test_activation_never_raises():
    # Edge cases: zero recency clamps to 1s, no exception
    a = activation(0.5, recency_seconds=0)
    assert isinstance(a, float)


def test_score_atoms_sorts_ascending():
    now = datetime.now(timezone.utc)
    atoms = [
        {"id": "old",    "importance": 8, "valid_at": (now - timedelta(days=30)).isoformat()},
        {"id": "new",    "importance": 8, "valid_at": (now - timedelta(minutes=5)).isoformat()},
        {"id": "medium", "importance": 5, "valid_at": (now - timedelta(days=7)).isoformat()},
    ]
    ranked = score_atoms(atoms, now=now)
    ids = [a["id"] for a in ranked]
    # newest + highest importance should be last
    assert ids[-1] == "new"
    # oldest should be first (lowest activation)
    assert ids[0] == "old"


def test_score_atoms_adds_activation_key():
    now = datetime.now(timezone.utc)
    atoms = [{"id": "x", "importance": 5, "valid_at": now.isoformat()}]
    ranked = score_atoms(atoms, now=now)
    assert "_activation" in ranked[0]


def test_score_atoms_handles_missing_timestamp():
    now = datetime.now(timezone.utc)
    atoms = [{"id": "no-ts", "importance": 7}]
    ranked = score_atoms(atoms, now=now)
    assert len(ranked) == 1
    assert "_activation" in ranked[0]
