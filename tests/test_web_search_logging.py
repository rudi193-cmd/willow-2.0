"""Tests for the web_search structured logging (Phase 5).

Every search outcome emits one privacy-safe `web_search` JSON record on the
`willow.web` logger: a cache hit, a successful provider call (with attempt
count + result_count), an empty advance, and a provider error. The raw query
text must never appear — only its hash.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest

from core import web_search
from core.web_search import TransientSearchError


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    web_search.reset_circuit_breakers()
    web_search.reset_search_cache()
    monkeypatch.setenv("WILLOW_SEARCH_MAX_ATTEMPTS", "1")
    monkeypatch.delenv("WILLOW_SEARCH_PROVIDER_ORDER", raising=False)
    monkeypatch.delenv("WILLOW_SEARCH_CACHE", raising=False)
    yield
    web_search.reset_circuit_breakers()
    web_search.reset_search_cache()


def _hit(url: str) -> dict[str, Any]:
    host = url.split("//")[-1].split("/")[0]
    return {"title": "t", "url": url, "snippet": "s", "source": host,
            "source_id": "web", "date": "", "hostname": host}


class _Provider:
    def __init__(self, name="p", results=None, exc=None, available=True):
        self.name = name
        self._results = results or []
        self._exc = exc
        self._available = available
        self.calls = 0

    def available(self) -> bool:
        return self._available

    def search(self, query: str, max_results: int):
        self.calls += 1
        if self._exc is not None:
            raise self._exc
        return list(self._results)


def _events(caplog) -> list[dict[str, Any]]:
    """Parse the structured web_search records out of captured log lines."""
    out = []
    for rec in caplog.records:
        msg = rec.getMessage()
        if msg.startswith("web_search {"):
            out.append(json.loads(msg[len("web_search "):]))
    return out


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def test_query_hash_normalizes_and_is_short():
    assert web_search._query_hash("  Hello   World ") == web_search._query_hash("hello world")
    assert len(web_search._query_hash("anything")) == 16


# --------------------------------------------------------------------------- #
# emit points
# --------------------------------------------------------------------------- #


def test_provider_success_logs_record(caplog):
    p = _Provider(results=[_hit("https://a.test"), _hit("https://b.test")])
    with caplog.at_level(logging.INFO, logger="willow.web"):
        web_search.search_web("rome aqueducts", providers=[p])
    events = _events(caplog)
    assert len(events) == 1
    ev = events[0]
    assert ev["event"] == "web_search"
    assert ev["provider"] == "p"
    assert ev["status"] == "ok"
    assert ev["result_count"] == 2
    assert ev["cache_hit"] is False
    assert ev["attempt"] == 1
    assert "latency_ms" in ev


def test_raw_query_never_logged(caplog):
    p = _Provider(results=[_hit("https://a.test")])
    secret = "my-very-distinctive-private-query"
    with caplog.at_level(logging.INFO, logger="willow.web"):
        web_search.search_web(secret, providers=[p])
    for ev in _events(caplog):
        assert secret not in json.dumps(ev)
        assert ev["query_hash"] == web_search._query_hash(secret)


def test_cache_hit_logs_cache_record(caplog):
    p = _Provider(results=[_hit("https://a.test")])
    with caplog.at_level(logging.INFO, logger="willow.web"):
        web_search.search_web("rome aqueducts", providers=[p])  # miss -> provider
        web_search.search_web("rome aqueducts", providers=[p])  # hit -> cache
    events = _events(caplog)
    assert [e["provider"] for e in events] == ["p", "cache"]
    hit = events[1]
    assert hit["cache_hit"] is True
    assert hit["status"] == "ok"
    assert hit["attempt"] == 0
    assert hit["result_count"] == 1


def test_empty_provider_logs_empty_status(caplog):
    p = _Provider(results=[])
    with caplog.at_level(logging.INFO, logger="willow.web"):
        web_search.search_web("rome aqueducts", providers=[p])
    events = _events(caplog)
    assert len(events) == 1
    assert events[0]["status"] == "empty"
    assert events[0]["result_count"] == 0


def test_provider_error_logs_error_status(caplog):
    p = _Provider(exc=TransientSearchError("boom"))
    with caplog.at_level(logging.INFO, logger="willow.web"):
        web_search.search_web("rome aqueducts", providers=[p])
    events = _events(caplog)
    assert len(events) == 1
    assert events[0]["status"] == "error"
    assert events[0]["provider"] == "p"
    assert events[0]["attempt"] >= 1


def test_attempt_count_reflects_retries(caplog, monkeypatch):
    monkeypatch.setenv("WILLOW_SEARCH_MAX_ATTEMPTS", "3")

    class _FlakyProvider:
        name = "flaky"
        calls = 0

        def available(self):
            return True

        def search(self, query, max_results):
            self.__class__.calls += 1
            if self.__class__.calls < 3:
                raise TransientSearchError("flaky")
            return [_hit("https://a.test")]

    monkeypatch.setattr(web_search.time, "sleep", lambda *_: None)
    with caplog.at_level(logging.INFO, logger="willow.web"):
        web_search.search_web("rome", providers=[_FlakyProvider()])
    events = _events(caplog)
    assert events[0]["status"] == "ok"
    assert events[0]["attempt"] == 3
