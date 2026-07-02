"""Tests for core/jeles_sources.py field coercion (#646, #647)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import core.jeles_sources as js
from core.jeles_sources import _result, _text


def test_text_passthrough_and_none():
    assert _text("hello") == "hello"
    assert _text(None) == ""
    assert _text(42) == "42"


def test_text_joins_lists_and_skips_none():
    assert _text(["a", "b"]) == "a b"
    assert _text(["a", None, "b"]) == "a b"
    assert _text([]) == ""
    assert _text([["nested", "list"], "tail"]) == "nested list tail"


def test_result_coerces_list_snippet():
    # 647: Internet Archive returns description as a list sometimes
    r = _result("t", "u", "internet_archive", "IA", snippet=["part one", "part two"])
    assert r["snippet"] == "part one part two"


def test_result_coerces_none_and_list_title():
    r = _result(None, "u", "s", "i", snippet=None)
    assert r["title"] == ""
    assert r["snippet"] == ""
    r = _result(["Title", "Subtitle"], "u", "s", "i")
    assert r["title"] == "Title Subtitle"


def test_search_core_null_journal_title(monkeypatch):
    # 646: CORE journal entries can carry {"title": None}
    payload = {
        "results": [
            {
                "title": "Graffiti and participation",
                "downloadUrl": "https://core.example/1",
                "publisher": "",
                "journals": [{"title": None}],
                "abstract": "abs",
                "yearPublished": 2021,
                "id": 1,
            }
        ]
    }
    monkeypatch.setattr(js, "_get", lambda url: payload)
    results = js.search_core("graffiti public space political participation")
    assert len(results) == 1
    assert results[0]["institution"] == ""


def test_search_internet_archive_list_description(monkeypatch):
    payload = {
        "response": {
            "docs": [
                {
                    "identifier": "rome01",
                    "title": "Ancient Rome",
                    "description": ["Republic era.", "Constitutional history."],
                    "date": "1911",
                }
            ]
        }
    }
    monkeypatch.setattr(js, "_get", lambda url: payload)
    results = js.search_internet_archive("ancient Rome republic constitution")
    assert len(results) == 1
    assert results[0]["snippet"] == "Republic era. Constitutional history."
