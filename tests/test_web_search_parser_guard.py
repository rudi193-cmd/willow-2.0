"""Tests for the DDG parser-miss detection (Phase 6).

Detection only: when DDG returns a 200-OK results-style page that the regex
parser turns into 0 links, `_ddg_fetch` emits a structured `parser_miss`
warning (likely HTML structure drift) and still returns []. A small/empty page
or a page that genuinely parses results must NOT trip the alert.
"""

from __future__ import annotations

import json
import logging

import pytest

from core import web_search


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    web_search.reset_circuit_breakers()
    web_search.reset_search_cache()
    yield
    web_search.reset_circuit_breakers()
    web_search.reset_search_cache()


class _FakeResp:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


def _parser_miss_events(caplog):
    out = []
    for rec in caplog.records:
        msg = rec.getMessage()
        if msg.startswith("web_search {"):
            ev = json.loads(msg[len("web_search "):])
            if ev.get("status") == "parser_miss":
                out.append(ev)
    return out


# A real results page is large and mentions the results scaffold, but here the
# markup has drifted so _LINK_RE matches nothing.
_DRIFTED_PAGE = "<html><body>" + ("<div class='web-result'>x</div>" * 200) + "</body></html>"


# --------------------------------------------------------------------------- #
# heuristic unit
# --------------------------------------------------------------------------- #


def test_looks_like_results_page_true():
    assert web_search._looks_like_results_page(_DRIFTED_PAGE) is True


def test_looks_like_results_page_small_body_false():
    assert web_search._looks_like_results_page("<html>result</html>") is False


def test_looks_like_results_page_no_marker_false():
    big = "<html><body>" + ("<p>nothing here</p>" * 300) + "</body></html>"
    assert web_search._looks_like_results_page(big) is False


# --------------------------------------------------------------------------- #
# integration via _ddg_fetch
# --------------------------------------------------------------------------- #


def test_parser_miss_logs_event_on_drifted_page(monkeypatch, caplog):
    monkeypatch.setattr(web_search.requests, "post",
                        lambda *a, **k: _FakeResp(200, _DRIFTED_PAGE))
    with caplog.at_level(logging.INFO, logger="willow.web"):
        out = web_search._ddg_fetch("rome aqueducts")
    assert out == []  # detection only — still returns empty
    events = _parser_miss_events(caplog)
    assert len(events) == 1
    assert events[0]["provider"] == "ddg_html"
    assert events[0]["body_bytes"] == len(_DRIFTED_PAGE)
    # privacy: raw query never logged
    assert "rome aqueducts" not in json.dumps(events[0])


def test_no_parser_miss_when_results_parse(monkeypatch, caplog):
    good = (
        '<a class="result__a" href="https://a.test/x">Title A</a>'
        '<a class="result__snippet">snip</a>'
    ) * 60  # large + parses real links
    monkeypatch.setattr(web_search.requests, "post",
                        lambda *a, **k: _FakeResp(200, good))
    with caplog.at_level(logging.INFO, logger="willow.web"):
        out = web_search._ddg_fetch("rome aqueducts")
    assert out  # got real hits
    assert _parser_miss_events(caplog) == []


def test_no_parser_miss_on_small_empty_page(monkeypatch, caplog):
    monkeypatch.setattr(web_search.requests, "post",
                        lambda *a, **k: _FakeResp(200, "<html>no results</html>"))
    with caplog.at_level(logging.INFO, logger="willow.web"):
        out = web_search._ddg_fetch("rome aqueducts")
    assert out == []
    assert _parser_miss_events(caplog) == []  # too small to be drift
