"""Jeles routing and SEP parse regression tests."""
from core import jeles_sources as js


def test_route_override_french_revolution():
    q = "What happened during the French Revolution?"
    assert js._route_override(q) == ["gallica", "loc", "internet_archive", "openlibrary"]
    assert js.route_sources(q)[0] == "gallica"


def test_search_sep_parses_redirect_html():
    html = (
        '<a class=l href="https://plato.stanford.edu/search/r?entry=/entries/consciousness/'
        '&page=1&query=consciousness"><b>Consciousness</b></a>'
    )
    import re
    seen: set[str] = set()
    parsed = []
    for m in re.finditer(
        r'entry=(/entries/[^/&"]+/)[^"]*"[^>]*>(?:<b>)?([^<\n]{3,120})',
        html,
    ):
        path, title = m.group(1), re.sub(r"\s+", " ", m.group(2)).strip()
        slug = path.strip("/").split("/")[-1]
        if slug in seen:
            continue
        seen.add(slug)
        parsed.append((slug, title))
    assert parsed == [("consciousness", "Consciousness")]


def test_semantic_scholar_requires_key():
    assert js.SOURCES["semantic_scholar"]["key_required"] is True


def test_rerank_combined_lexical_fallback(monkeypatch):
    """No embedder reachable (e.g. CI) -> lexical-only RRF, not a hard failure."""
    monkeypatch.setattr(js, "_get_embedding", lambda text: [])
    out = {
        "arxiv": [
            {"title": "Climate opinion bias in large language models", "url": "https://a",
             "snippet": "Studies LLM attitudes toward climate policy.", "source": "arxiv",
             "institution": "arXiv", "date": "", "id": "a1"},
        ],
        "openalex": [
            {"title": "Gender bias in German language datasets", "url": "https://b",
             "snippet": "Unrelated NLP fairness dataset.", "source": "openalex",
             "institution": "OpenAlex", "date": "", "id": "b1"},
        ],
    }
    ranked = js._rerank_combined("large language model climate opinion bias", out)
    assert ranked, "expected a non-empty ranked list"
    assert ranked[0]["id"] == "a1", "the lexically-closer hit should rank first"
    assert all("_rrf_score" in r for r in ranked)


def test_rerank_combined_empty_input():
    assert js._rerank_combined("anything", {}) == []


def test_search_routes_by_default_but_explicit_sources_bypass(monkeypatch):
    """sources=None should call route_sources_semantic(); an explicit sources=[...]
    list should skip routing entirely (routed=False, active==sources)."""
    calls = []
    monkeypatch.setattr(js, "route_sources_semantic", lambda q: calls.append(q) or ["arxiv"])
    monkeypatch.setattr(js, "_load_registry", lambda: {
        "arxiv": {"name": "arXiv", "fn_name": "search_arxiv", "key_required": False, "enabled": True},
    })
    monkeypatch.setattr(js, "_resolve_fn", lambda name: (lambda query, limit: []))
    monkeypatch.setattr(js, "_write_cache", lambda *a, **kw: None)

    result = js.search("test query", sources=None)
    assert calls == ["test query"], "default search() must consult route_sources_semantic"
    assert result["routed"] is True
    assert result["sources_queried"] == ["arxiv"]

    calls.clear()
    result2 = js.search("test query", sources=["arxiv"])
    assert calls == [], "explicit sources= must bypass routing"
    assert result2["routed"] is False
    assert result2["sources_queried"] == ["arxiv"]
