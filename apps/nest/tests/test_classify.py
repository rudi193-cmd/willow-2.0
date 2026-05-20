# b17: 1284BC7D  ΔΣ=42
"""Tests for apps.nest.classify."""
import pytest
from apps.nest.classify import classify, should_ignore


@pytest.mark.parametrize("filename,expected", [
    ("2026-05-13.md",                          "journal"),
    ("earnings_statement_april.pdf",            "legal"),
    ("session_handoff_2026.md",                 "handoffs"),
    ("knowledge_extraction_v1.txt",             "knowledge"),
    ("chapter_01_regarding_jane.docx",          "narrative"),
    ("architecture_spec.md",                    "specs"),
    ("20260513_143000.jpg",                     "photos_camera"),
    ("feeld_match.jpg",                         "photos_personal"),
    ("screenshot 2026-05-13.png",               "screenshots"),
    ("random_file.xyz",                         None),
])
def test_classify(filename, expected):
    assert classify(filename) == expected


@pytest.mark.parametrize("filename", [
    "desktop.ini", "thumbs.db", ".DS_Store", ".localized", ".hidden",
])
def test_should_ignore(filename):
    assert should_ignore(filename)
    assert classify(filename) is None


def test_legal_beats_narrative():
    assert classify("adobe scan mar bankruptcy.pdf") == "legal"


def test_handoffs_beat_specs():
    assert classify("session_handoff_architecture.md") == "handoffs"
