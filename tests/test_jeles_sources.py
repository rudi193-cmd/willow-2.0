"""Tests for core/jeles_sources.py field coercion (#646, #647),
search() failure reporting (#654), and fetch resilience (#648-#668)."""

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


def test_is_prose_threshold():
    assert js._is_prose("constitutional rights of sentient cheese republic") is True
    assert js._is_prose("aspirin") is False
    assert js._is_prose("USD EUR exchange rate") is False


def test_search_gates_prose_from_structured_sources(monkeypatch):
    calls = []

    def pubchem_fn(query, limit):
        calls.append(query)
        return []

    def prose_ok_fn(query, limit):
        return [js._result("t", "u", "arxiv", "i")]

    _wire_search(monkeypatch, {"pubchem": pubchem_fn, "arxiv": prose_ok_fn})
    out = js.search(
        "constitutional rights of sentient cheese republic democracy",
        sources=["pubchem", "arxiv"],
    )
    assert calls == []  # pubchem never dispatched
    assert list(out["results"]) == ["arxiv"]
    assert out["skipped"] == [
        {"source": "pubchem", "reason": "prose query vs structured-only source (#650)"}
    ]
    assert out["failures"] == []  # a gate skip is not a failure


def test_search_short_query_reaches_structured_sources(monkeypatch):
    calls = []

    def pubchem_fn(query, limit):
        calls.append(query)
        return []

    _wire_search(monkeypatch, {"pubchem": pubchem_fn})
    out = js.search("aspirin", sources=["pubchem"])
    assert calls == ["aspirin"]
    assert out["skipped"] == []


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


# ── fetch resilience: retry + circuit breaker (#648-#668) ─────────────────────

import pytest


@pytest.fixture(autouse=True)
def _reset_breaker():
    js._breaker.clear()
    yield
    js._breaker.clear()


def _no_sleep(monkeypatch):
    import time
    monkeypatch.setattr(time, "sleep", lambda s: None)


def test_get_retries_once_on_503(monkeypatch):
    _no_sleep(monkeypatch)
    calls = []

    def flaky(url, headers, timeout, as_json):
        calls.append(url)
        if len(calls) == 1:
            raise RuntimeError("HTTP Error 503: Service Unavailable")
        return {"ok": True}

    monkeypatch.setattr(js, "_fetch_once", flaky)
    assert js._get("https://api.example.org/x") == {"ok": True}
    assert len(calls) == 2


def test_get_does_not_retry_on_404(monkeypatch):
    _no_sleep(monkeypatch)
    calls = []

    def dead(url, headers, timeout, as_json):
        calls.append(url)
        raise RuntimeError("HTTP Error 404: Not Found")

    monkeypatch.setattr(js, "_fetch_once", dead)
    assert js._get("https://api.example.org/x") is None
    assert len(calls) == 1


def test_breaker_opens_after_threshold(monkeypatch):
    _no_sleep(monkeypatch)
    calls = []

    def dead(url, headers, timeout, as_json):
        calls.append(url)
        raise RuntimeError("HTTP Error 404: Not Found")

    monkeypatch.setattr(js, "_fetch_once", dead)
    for _ in range(js._BREAKER_THRESHOLD):
        js._get("https://down.example.org/x")
    n = len(calls)
    assert js._get("https://down.example.org/x") is None  # circuit open
    assert len(calls) == n  # no fetch attempted
    # a different host is unaffected
    assert js._get("https://alive.example.org/x") is None
    assert len(calls) == n + 1


def test_breaker_resets_on_success(monkeypatch):
    _no_sleep(monkeypatch)
    state = {"fail": True}

    def sometimes(url, headers, timeout, as_json):
        if state["fail"]:
            raise RuntimeError("HTTP Error 404: Not Found")
        return {"ok": True}

    monkeypatch.setattr(js, "_fetch_once", sometimes)
    js._get("https://x.example.org/a")
    js._get("https://x.example.org/a")
    state["fail"] = False
    assert js._get("https://x.example.org/a") == {"ok": True}
    assert "x.example.org" not in js._breaker


# ── per-source fixes ──────────────────────────────────────────────────────────

def test_dblp_truncates_long_prose_query(monkeypatch):
    seen = {}
    monkeypatch.setattr(js, "_get", lambda url, **kw: seen.update(url=url) or None)
    js.search_dblp("constitutional rights of sentient cheese republic democracy political participation graffiti")
    from urllib.parse import unquote
    q = unquote(seen["url"].split("?q=")[1].split("&")[0])
    assert len(q.split()) == 8


def test_gdelt_uses_extended_timeout(monkeypatch):
    seen = {}

    def fake_get(url, headers=None, timeout=None):
        seen["timeout"] = timeout
        return None

    monkeypatch.setattr(js, "_get", fake_get)
    js.search_gdelt("liberty")
    assert seen["timeout"] == 30


def test_chronicling_america_new_endpoint(monkeypatch):
    seen = {}
    payload = {
        "results": [
            {
                "title": "Image 1 of Grainger County news, October 3",
                "url": "https://www.loc.gov/resource/sn99065781/1918-10-03/ed-1/?sp=1",
                "id": "http://www.loc.gov/resource/sn99065781/1918-10-03/ed-1/?sp=1",
                "date": "1918-10-03",
                "description": ["County News", "DEVOTED TO GRAINGER COUNTY"],
            }
        ]
    }

    def fake_get(url, headers=None, timeout=None):
        seen["url"] = url
        return payload

    monkeypatch.setattr(js, "_get", fake_get)
    results = js.search_chronicling_america("liberty")
    assert "loc.gov/collections/chronicling-america" in seen["url"]
    assert len(results) == 1
    assert results[0]["snippet"] == "County News DEVOTED TO GRAINGER COUNTY"
    assert results[0]["url"].startswith("https://www.loc.gov/resource/")
