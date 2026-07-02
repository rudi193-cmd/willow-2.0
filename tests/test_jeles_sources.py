"""Tests for core/jeles_sources.py field coercion (#646, #647) and
search() failure reporting (#654)."""

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


# ── search() failure reporting (#654) ─────────────────────────────────────────

_FAKE_FNS = {}


def _wire_search(monkeypatch, sources):
    """Point search() at a fake registry of {source_id: callable}."""
    _FAKE_FNS.clear()
    _FAKE_FNS.update(sources)
    registry = {sid: {"fn_name": sid} for sid in sources}
    monkeypatch.setattr(js, "_load_registry", lambda: registry)
    monkeypatch.setattr(js, "_resolve_fn", lambda name: _FAKE_FNS.get(name))
    monkeypatch.setattr(js, "_write_cache", lambda query, results: None)
    monkeypatch.setattr(js, "_rerank_combined", lambda query, out, top_n=15: [])


def test_note_failure_noop_when_unarmed():
    # outside a search() worker thread the channel is dark — must not raise
    js._FAILURES.list = None
    js._note_failure("stray")


def test_search_reports_source_exception(monkeypatch):
    def boom(query, limit):
        raise RuntimeError("HTTP Error 503: Service Unavailable")

    _wire_search(monkeypatch, {"boom": boom})
    out = js.search("q", sources=["boom"])
    assert out["results"] == {}
    assert len(out["failures"]) == 1
    f = out["failures"][0]
    assert f["source"] == "boom"
    assert "503" in f["error"]
    assert f["query"] == "q"


def test_search_reports_swallowed_get_failures(monkeypatch):
    # a source whose _get failed internally returns [] but noted the failure
    def quiet_failure(query, limit):
        js._note_failure("GET https://api.example.org/x: HTTP Error 429")
        return []

    _wire_search(monkeypatch, {"quiet": quiet_failure})
    out = js.search("q", sources=["quiet"])
    assert out["results"] == {}
    assert [f["error"] for f in out["failures"]] == [
        "GET https://api.example.org/x: HTTP Error 429"
    ]


def test_search_reports_unknown_source(monkeypatch):
    _wire_search(monkeypatch, {})
    out = js.search("q", sources=["ghost"])
    assert out["failures"][0]["source"] == "ghost"
    assert "unknown source" in out["failures"][0]["error"]


def test_search_success_has_empty_failures(monkeypatch):
    hit = js._result("t", "u", "ok", "inst")

    def good(query, limit):
        return [hit]

    _wire_search(monkeypatch, {"ok": good})
    out = js.search("q", sources=["ok"])
    assert out["results"] == {"ok": [hit]}
    assert out["failures"] == []
    # channel must be reset so later non-search calls don't leak into it
    assert getattr(js._FAILURES, "list", None) is None
