"""General web search — DuckDuckGo HTML scrape + navigational map handoffs."""

from __future__ import annotations

import html
import logging
import os
import re
from typing import Any, Protocol, runtime_checkable
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import requests

log = logging.getLogger("willow.web")

_USER_AGENT = "Mozilla/5.0 (compatible; Willow/2.0; +https://github.com/rudi193-cmd/willow-2.0)"
_DDG_URL = "https://html.duckduckgo.com/html/"
_LINK_RE = re.compile(
    r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_SNIP_RE = re.compile(
    r'class="result__snippet"[^>]*>(.*?)</(?:a|td|span|div)>',
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")

# Hostname suffixes for trusted-source filtering.
# Covers all sources registered in core/jeles_sources.py SOURCES dict.
_TRUSTED_SUFFIXES = (
    # Broad TLD catches (.gov, .edu, .museum, .go.jp for NDL, .ac.uk for CORE)
    "gov", "edu", "museum", "go.jp", "ac.uk",
    # Already-present institutions
    "si.edu", "loc.gov", "archive.org", "louvre.fr", "nasa.gov", "nih.gov",
    "unesco.org", "europeana.eu", "metmuseum.org", "vam.ac.uk", "britishmuseum.org",
    "nature.com", "jstor.org", "wikipedia.org", "stanford.edu", "britannica.com",
    # Academic / open-access repositories
    "openalex.org", "crossref.org", "europepmc.org", "semanticscholar.org",
    "arxiv.org", "zenodo.org", "datacite.org", "doaj.org", "openaire.eu",
    "base-search.net", "dblp.org",
    # Reference / encyclopedic
    "wikidata.org", "eol.org",
    # Museums / cultural heritage
    "clevelandart.org", "rijksmuseum.nl",
    # Libraries / archives
    "openlibrary.org", "gutenberg.org", "biodiversitylibrary.org",
    "dp.la", "bnf.fr", "archives-ouvertes.fr", "hal.science",
    # International
    "scielo.org", "europa.eu",
    # Music
    "musicbrainz.org",
    # Species / ecology / geography
    "gbif.org", "inaturalist.org", "openstreetmap.org",
    # Law
    "courtlistener.com",
    # Clinical trade press / science misc
    "psychiatrictimes.com", "improbable.com",
)


def _hostname(url: str) -> str:
    try:
        return urlparse(url).netloc or "web"
    except Exception:
        return "web"


def _strip_tags(text: str) -> str:
    return html.unescape(_TAG_RE.sub("", text or "")).strip()


def _unwrap_ddg(href: str) -> str:
    href = (href or "").strip()
    if not href:
        return ""
    if href.startswith("//"):
        href = "https:" + href
    if "uddg=" in href:
        try:
            qs = parse_qs(urlparse(href).query)
            if qs.get("uddg"):
                return unquote(qs["uddg"][0])
        except Exception:
            pass
    return href


def _trusted_host(hostname: str) -> bool:
    host = (hostname or "").lower().lstrip("www.")
    if not host:
        return False
    for suffix in _TRUSTED_SUFFIXES:
        if host == suffix or host.endswith("." + suffix) or host.endswith(suffix):
            return True
    return False


def navigational_handoffs(query: str) -> list[dict[str, Any]]:
    """Synthetic map/search URLs for local/navigational queries."""
    q = query.strip()
    if not q:
        return []
    enc = quote_plus(q)
    return [
        {
            "title": f"OpenStreetMap: {q}",
            "url": f"https://www.openstreetmap.org/search?query={enc}",
            "snippet": "Search OpenStreetMap for places matching your query.",
            "source": "OpenStreetMap",
            "source_id": "maps_osm",
            "date": "",
            "hostname": "openstreetmap.org",
        },
        {
            "title": f"Google Maps: {q}",
            "url": f"https://www.google.com/maps/search/{enc}",
            "snippet": "Open Google Maps with this search.",
            "source": "Google Maps",
            "source_id": "maps_google",
            "date": "",
            "hostname": "google.com",
        },
        {
            "title": f"Web search: {q}",
            "url": f"https://duckduckgo.com/?q={enc}",
            "snippet": "Full DuckDuckGo results in your browser.",
            "source": "DuckDuckGo",
            "source_id": "web_ddg",
            "date": "",
            "hostname": "duckduckgo.com",
        },
    ]


def ddg_html_search(query: str, max_results: int = 8) -> list[dict[str, Any]]:
    """Fetch DuckDuckGo HTML results (no API key)."""
    q = query.strip()
    if not q:
        return []
    try:
        resp = requests.post(
            _DDG_URL,
            data={"q": q, "b": "", "kl": "us-en"},
            headers={"User-Agent": _USER_AGENT},
            timeout=12,
        )
        resp.raise_for_status()
    except Exception as exc:
        log.warning("ddg search failed: %s", exc)
        return []

    links = _LINK_RE.findall(resp.text)
    snippets = _SNIP_RE.findall(resp.text)
    hits: list[dict[str, Any]] = []
    for idx, (href, title_html) in enumerate(links[: max_results + 4]):
        url = _unwrap_ddg(href)
        if not url or "duckduckgo.com" in url:
            continue
        title = _strip_tags(title_html) or url
        snippet = _strip_tags(snippets[idx]) if idx < len(snippets) else ""
        host = _hostname(url)
        hits.append(
            {
                "title": title[:200],
                "url": url,
                "snippet": snippet[:400],
                "source": host,
                "source_id": "web",
                "date": "",
                "hostname": host,
            }
        )
        if len(hits) >= max_results:
            break
    return hits


# --------------------------------------------------------------------------- #
# Provider seam
#
# `search_web()` historically conflated "search" with "DuckDuckGo HTML scrape."
# The seam below separates the two without changing default behavior: the
# default provider chain is `[DDGHtmlProvider]`, so an unconfigured call returns
# exactly what `ddg_html_search()` returned before. Additional providers
# (Brave/Bing/SerpAPI) slot in via `WILLOW_SEARCH_PROVIDER_ORDER` once their
# implementations land — DDG stays the default and last-resort fallback.
# --------------------------------------------------------------------------- #


@runtime_checkable
class SearchProvider(Protocol):
    """A pluggable search backend returning Willow's standard result dicts."""

    name: str

    def available(self) -> bool:
        """Cheap readiness/credential check — False means skip without calling."""
        ...

    def search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        """Return result dicts (title/url/snippet/source/source_id/date/hostname)."""
        ...


class DDGHtmlProvider:
    """Current implementation — DuckDuckGo HTML scrape, no API key required.

    Default primary provider and the last-resort fallback for the chain.
    """

    name = "ddg_html"

    def available(self) -> bool:
        return True

    def search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        return ddg_html_search(query, max_results=max_results)


class BraveSearchProvider:
    """Brave Search JSON API provider — key-gated seam stub.

    Phase 1 ships the seam only: the class is present and discoverable but is
    not in the default chain, and `available()` stays False until both an API
    key is configured and the real call is implemented in a follow-up. Wiring
    it early (setting BRAVE_API_KEY) cannot change behavior because `available()`
    gates on `_IMPLEMENTED` as well.
    """

    name = "brave"
    _IMPLEMENTED = False

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.getenv("BRAVE_API_KEY", "")

    def available(self) -> bool:
        return self._IMPLEMENTED and bool(self._api_key)

    def search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        # Real Brave call lands in the provider-implementation follow-up.
        log.debug("brave provider not yet implemented — returning []")
        return []


# Registry of constructable providers by name. Factories are nullary so the
# chain can be (re)built per call without shared mutable state.
_PROVIDER_FACTORY: dict[str, Any] = {
    "ddg_html": DDGHtmlProvider,
    "brave": BraveSearchProvider,
}

_DEFAULT_PROVIDER_ORDER = "ddg_html"


def _provider_order() -> list[str]:
    """Provider chain from env (`WILLOW_SEARCH_PROVIDER_ORDER`), DDG by default."""
    raw = os.getenv("WILLOW_SEARCH_PROVIDER_ORDER", _DEFAULT_PROVIDER_ORDER)
    return [name.strip() for name in raw.split(",") if name.strip()]


def build_providers(order: list[str] | None = None) -> list[SearchProvider]:
    """Construct the provider chain in priority order, skipping unknown names."""
    providers: list[SearchProvider] = []
    for name in order or _provider_order():
        factory = _PROVIDER_FACTORY.get(name)
        if factory is None:
            log.warning("unknown search provider %r — skipping", name)
            continue
        providers.append(factory())
    return providers


def _search_providers(
    query: str,
    max_results: int,
    providers: list[SearchProvider] | None = None,
) -> list[dict[str, Any]]:
    """Run the provider chain, advancing on unavailable/empty/error.

    The chain resets per query. Each advance is logged with a reason. Returns
    the first non-empty result set, or [] if every provider is exhausted.
    """
    chain = build_providers() if providers is None else providers
    for provider in chain:
        try:
            if not provider.available():
                log.debug("provider %s unavailable — advancing", provider.name)
                continue
            results = provider.search(query, max_results)
        except Exception as exc:
            log.warning("provider %s failed: %s — advancing", provider.name, exc)
            continue
        if results:
            return results
        log.info("provider %s returned 0 results — advancing", provider.name)
    return []


def search_web(
    query: str,
    *,
    max_results: int = 8,
    trusted_only: bool = False,
    include_handoffs: bool = False,
    providers: list[SearchProvider] | None = None,
) -> list[dict[str, Any]]:
    """
    General open web search for Willow.

    trusted_only: filter to verified institutional domain suffixes.
    include_handoffs: prepend map/search URLs for navigational queries.
    providers: explicit provider chain (default: built from
        WILLOW_SEARCH_PROVIDER_ORDER, falling back to DDG HTML).
    """
    hits: list[dict[str, Any]] = []
    if include_handoffs:
        hits.extend(navigational_handoffs(query))

    raw = _search_providers(query, max_results, providers)
    if trusted_only:
        raw = [h for h in raw if _trusted_host(h.get("hostname", ""))]

    seen = {h["url"] for h in hits if h.get("url")}
    for hit in raw:
        url = hit.get("url") or ""
        if url and url not in seen:
            seen.add(url)
            hits.append(hit)
    return hits[: max_results + (3 if include_handoffs else 0)]
