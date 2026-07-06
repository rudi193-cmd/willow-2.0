"""Tests for the nest rules store (seed template + local store, shared engine)."""

import json

import pytest

from sap.core import nest_rules


@pytest.fixture(autouse=True)
def isolated_rules(tmp_path, monkeypatch):
    """Point the local store at tmp and clear the loader cache around each test."""
    monkeypatch.setenv("WILLOW_NEST_RULES", str(tmp_path / "nest_rules.json"))
    nest_rules._reset_cache()
    yield tmp_path / "nest_rules.json"
    nest_rules._reset_cache()


def test_first_use_materializes_local_store(isolated_rules):
    assert not isolated_rules.exists()
    nest_rules.load_rules()
    assert isolated_rules.exists()
    seeded = json.loads(isolated_rules.read_text())
    assert seeded["version"] == "seed-1"
    assert "legal" in seeded["tracks"]


def test_version_reads_from_store(isolated_rules):
    assert nest_rules.version() == "seed-1"


@pytest.mark.parametrize("filename,expected", [
    ("2026-05-13.md",                  "journal"),
    ("earnings_statement_april.pdf",   "legal"),
    ("session_handoff_2026.md",        "handoffs"),
    ("knowledge_extraction_v1.txt",    "knowledge"),
    ("chapter_01_regarding_jane.docx", "narrative"),
    ("architecture_spec.md",           "specs"),
    ("20260513_143000.jpg",            "photos_camera"),
    ("feeld_match.jpg",                "photos_personal"),
    ("screenshot 2026-05-13.png",      "screenshots"),
    ("random_file.xyz",                None),
    # priority order preserved from legacy classifiers
    ("adobe scan mar bankruptcy.pdf",  "legal"),
    ("session_handoff_architecture.md", "handoffs"),
])
def test_classify_parity(filename, expected):
    assert nest_rules.classify(filename) == expected


@pytest.mark.parametrize("filename", [
    "desktop.ini", "thumbs.db", ".DS_Store", ".localized", ".hidden",
])
def test_should_ignore(filename):
    assert nest_rules.should_ignore(filename)
    assert nest_rules.classify(filename) is None


def test_local_store_edit_picked_up_without_restart(isolated_rules):
    """A ratified delta (file edit + version bump) takes effect on next call."""
    assert nest_rules.classify("bank_statement_q2.pdf") is None

    rules = nest_rules.load_rules().copy()
    rules["tracks"]["legal"]["keywords"] = (
        rules["tracks"]["legal"]["keywords"] + ["statement"]
    )
    rules["version"] = "seed-2"
    isolated_rules.write_text(json.dumps(rules))
    # ensure mtime moves even on coarse-grained filesystems
    import os
    st = isolated_rules.stat()
    os.utime(isolated_rules, (st.st_atime, st.st_mtime + 1))

    assert nest_rules.classify("bank_statement_q2.pdf") == "legal"
    assert nest_rules.version() == "seed-2"


def test_delegates_share_one_engine():
    from apps.nest.classify import classify as app_classify
    from sap.core.nest_intake import _classify as intake_classify
    for name in ["earnings_statement_april.pdf", "2026-05-13.md", "random.xyz",
                 "gmail - re_ custody.pdf"]:
        assert app_classify(name) == intake_classify(name) == nest_rules.classify(name)
