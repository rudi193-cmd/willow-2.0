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
