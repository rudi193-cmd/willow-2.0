"""
jeles_sources.py — Trusted, citable source registry for Jeles (the Librarian).
b17: JLSS1  ΔΣ=42

Each source function returns list[dict] with standard citation fields:
  title, url, source, institution, snippet, date, id

Wikipedia is explicitly excluded. Every result here can appear in an academic bibliography.
Sources are grouped by domain. Sources requiring API keys load from credentials.json.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

log = logging.getLogger("jeles.sources")

_CREDS_PATH = Path.home() / ".willow" / "secrets" / "credentials.json"
_TIMEOUT = 15


def _load_creds() -> dict:
    try:
        return json.loads(_CREDS_PATH.read_text())
    except Exception:
        return {}


def _get(url: str, headers: dict | None = None) -> Optional[dict | list]:
    try:
        req = urllib.request.Request(url, headers=headers or {
            "User-Agent": "Willow-Jeles/1.0 (academic librarian; mailto:rudi193@gmail.com)"
        })
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            return json.loads(r.read())
    except Exception as e:
        log.warning("GET %s failed: %s", url[:80], e)
        return None


def _result(title: str, url: str, source: str, institution: str,
            snippet: str = "", date: str = "", rid: str = "") -> dict:
    return {
        "title": title,
        "url": url,
        "source": source,
        "institution": institution,
        "snippet": snippet[:400] if snippet else "",
        "date": date,
        "id": rid,
    }


# ── Library of Congress ────────────────────────────────────────────────────────

def search_loc(query: str, limit: int = 5) -> list[dict]:
    """Library of Congress digital collections. No API key required."""
    url = (
        "https://www.loc.gov/search/?q="
        + urllib.parse.quote(query)
        + f"&fo=json&c={limit}"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for item in (data.get("results") or [])[:limit]:
        results.append(_result(
            title=item.get("title", ""),
            url=item.get("url", ""),
            source="loc",
            institution="Library of Congress",
            snippet=item.get("description", [""])[0] if isinstance(item.get("description"), list) else item.get("description", ""),
            date=item.get("date", ""),
            rid=item.get("id", ""),
        ))
    return results


# ── arXiv ─────────────────────────────────────────────────────────────────────

def search_arxiv(query: str, limit: int = 5) -> list[dict]:
    """arXiv preprint server (STEM, CS, Math, Physics, etc.). No API key required."""
    url = (
        "https://export.arxiv.org/api/query?search_query="
        + urllib.parse.quote(f"all:{query}")
        + f"&max_results={limit}&sortBy=relevance"
    )
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Willow-Jeles/1.0 (academic librarian)"
        })
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            raw = r.read()
    except Exception as e:
        log.warning("arXiv request failed: %s", e)
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        log.warning("arXiv XML parse failed: %s", e)
        return []

    results = []
    for entry in root.findall("atom:entry", ns)[:limit]:
        arxiv_id = (entry.findtext("atom:id", "", ns) or "").split("/abs/")[-1]
        results.append(_result(
            title=(entry.findtext("atom:title", "", ns) or "").strip(),
            url=entry.findtext("atom:id", "", ns) or "",
            source="arxiv",
            institution="arXiv / Cornell University",
            snippet=(entry.findtext("atom:summary", "", ns) or "").strip(),
            date=entry.findtext("atom:published", "", ns) or "",
            rid=arxiv_id,
        ))
    return results


# ── PubMed / NCBI ─────────────────────────────────────────────────────────────

def search_pubmed(query: str, limit: int = 5) -> list[dict]:
    """PubMed biomedical literature. No API key required (rate-limited)."""
    search_url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        "?db=pubmed&retmode=json&retmax=" + str(limit)
        + "&term=" + urllib.parse.quote(query)
        + "&tool=willow-jeles&email=rudi193@gmail.com"
    )
    search = _get(search_url)
    if not search:
        return []
    ids = (search.get("esearchresult") or {}).get("idlist") or []
    if not ids:
        return []

    summary_url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        "?db=pubmed&retmode=json&id=" + ",".join(ids)
        + "&tool=willow-jeles&email=rudi193@gmail.com"
    )
    summary = _get(summary_url)
    if not summary:
        return []

    results = []
    for pmid in ids:
        doc = (summary.get("result") or {}).get(pmid) or {}
        if not doc or pmid == "uids":
            continue
        results.append(_result(
            title=doc.get("title", ""),
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            source="pubmed",
            institution="PubMed / National Library of Medicine",
            snippet=", ".join(doc.get("authors", [{}])[:3] and
                              [a.get("name", "") for a in doc.get("authors", [])[:3]]),
            date=doc.get("pubdate", ""),
            rid=pmid,
        ))
    return results


# ── Crossref ──────────────────────────────────────────────────────────────────

def search_crossref(query: str, limit: int = 5) -> list[dict]:
    """Crossref DOI registry — journals, books, conference papers. No key required."""
    url = (
        "https://api.crossref.org/works?rows=" + str(limit)
        + "&query=" + urllib.parse.quote(query)
        + "&mailto=rudi193@gmail.com"
    )
    data = _get(url)
    if not data:
        return []
    items = (data.get("message") or {}).get("items") or []
    results = []
    for item in items[:limit]:
        doi = item.get("DOI", "")
        titles = item.get("title") or [""]
        date_parts = ((item.get("published") or item.get("issued") or {})
                      .get("date-parts") or [[]])[0]
        date = "-".join(str(p) for p in date_parts) if date_parts else ""
        results.append(_result(
            title=titles[0] if titles else "",
            url=f"https://doi.org/{doi}" if doi else "",
            source="crossref",
            institution=item.get("publisher", ""),
            snippet=item.get("abstract", "")[:400],
            date=date,
            rid=doi,
        ))
    return results


# ── Open Library (Internet Archive) ───────────────────────────────────────────

def search_openlibrary(query: str, limit: int = 5) -> list[dict]:
    """Open Library — books and historical texts. No API key required."""
    url = (
        "https://openlibrary.org/search.json?q="
        + urllib.parse.quote(query)
        + f"&limit={limit}&fields=title,author_name,first_publish_year,key,edition_count"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for doc in (data.get("docs") or [])[:limit]:
        key = doc.get("key", "")
        results.append(_result(
            title=doc.get("title", ""),
            url=f"https://openlibrary.org{key}" if key else "",
            source="openlibrary",
            institution="Open Library / Internet Archive",
            snippet=", ".join(doc.get("author_name") or []),
            date=str(doc.get("first_publish_year", "")),
            rid=key,
        ))
    return results


# ── NASA Image & Video Library ────────────────────────────────────────────────

def search_nasa(query: str, limit: int = 5) -> list[dict]:
    """NASA Image & Video Library. No API key required."""
    url = (
        "https://images-api.nasa.gov/search?q="
        + urllib.parse.quote(query)
        + f"&page_size={limit}"
    )
    data = _get(url)
    if not data:
        return []
    items = (data.get("collection") or {}).get("items") or []
    results = []
    for item in items[:limit]:
        data_block = (item.get("data") or [{}])[0]
        links = item.get("links") or [{}]
        results.append(_result(
            title=data_block.get("title", ""),
            url=(links[0].get("href", "") if links else ""),
            source="nasa",
            institution="NASA",
            snippet=data_block.get("description", ""),
            date=data_block.get("date_created", "")[:10],
            rid=data_block.get("nasa_id", ""),
        ))
    return results


# ── Smithsonian Open Access ────────────────────────────────────────────────────

def search_smithsonian(query: str, limit: int = 5) -> list[dict]:
    """Smithsonian Institution collections. Requires SMITHSONIAN_API_KEY in credentials.json."""
    key = _load_creds().get("SMITHSONIAN_API_KEY", "")
    if not key:
        log.debug("Smithsonian: no API key — skipping")
        return []
    url = (
        "https://api.si.edu/openaccess/api/v1.0/search?q="
        + urllib.parse.quote(query)
        + f"&rows={limit}&api_key={key}"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for row in ((data.get("response") or {}).get("rows") or [])[:limit]:
        desc = row.get("content", {}).get("descriptiveNonRepeating", {})
        results.append(_result(
            title=row.get("title", ""),
            url=desc.get("record_link", ""),
            source="smithsonian",
            institution="Smithsonian Institution",
            snippet=desc.get("notes", {}).get("label", ""),
            date=row.get("content", {}).get("indexedStructured", {}).get("date", [""])[0],
            rid=row.get("id", ""),
        ))
    return results


# ── Europeana ─────────────────────────────────────────────────────────────────

def search_europeana(query: str, limit: int = 5) -> list[dict]:
    """Europeana — European cultural heritage. Requires EUROPEANA_API_KEY in credentials.json."""
    key = _load_creds().get("EUROPEANA_API_KEY", "")
    if not key:
        log.debug("Europeana: no API key — skipping")
        return []
    url = (
        "https://api.europeana.eu/record/v2/search.json?wskey="
        + key
        + "&query=" + urllib.parse.quote(query)
        + f"&rows={limit}&profile=rich"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for item in (data.get("items") or [])[:limit]:
        results.append(_result(
            title=(item.get("title") or [""])[0],
            url=item.get("guid", ""),
            source="europeana",
            institution=(item.get("dataProvider") or ["Europeana"])[0],
            snippet=(item.get("dcDescription") or [""])[0],
            date=(item.get("year") or [""])[0],
            rid=item.get("id", ""),
        ))
    return results


# ── Source registry ────────────────────────────────────────────────────────────

SOURCES: dict[str, dict] = {
    "loc": {
        "name": "Library of Congress",
        "domain": ["humanities", "history", "government", "general"],
        "fn": search_loc,
        "key_required": False,
    },
    "arxiv": {
        "name": "arXiv",
        "domain": ["science", "math", "cs", "physics", "engineering"],
        "fn": search_arxiv,
        "key_required": False,
    },
    "pubmed": {
        "name": "PubMed",
        "domain": ["biology", "medicine", "health", "science"],
        "fn": search_pubmed,
        "key_required": False,
    },
    "crossref": {
        "name": "Crossref",
        "domain": ["general", "academic", "humanities", "science"],
        "fn": search_crossref,
        "key_required": False,
    },
    "openlibrary": {
        "name": "Open Library",
        "domain": ["books", "humanities", "history", "general"],
        "fn": search_openlibrary,
        "key_required": False,
    },
    "nasa": {
        "name": "NASA Image & Video Library",
        "domain": ["space", "science", "engineering"],
        "fn": search_nasa,
        "key_required": False,
    },
    "smithsonian": {
        "name": "Smithsonian Institution",
        "domain": ["art", "history", "science", "culture"],
        "fn": search_smithsonian,
        "key_required": True,
    },
    "europeana": {
        "name": "Europeana",
        "domain": ["art", "culture", "history", "humanities"],
        "fn": search_europeana,
        "key_required": True,
    },
}

NO_WIKIPEDIA_NOTE = (
    "Wikipedia is excluded — results are from primary institutions "
    "and peer-reviewed sources suitable for academic citation."
)


def search(
    query: str,
    sources: list[str] | None = None,
    limit_per_source: int = 3,
) -> dict:
    """
    Search across trusted sources. Returns {source_id: [results]} plus a citation note.
    sources=None → all sources. Pass a list to target specific ones.
    """
    active = sources if sources else list(SOURCES.keys())
    out: dict[str, list] = {}
    for sid in active:
        cfg = SOURCES.get(sid)
        if not cfg:
            log.warning("Unknown source: %s", sid)
            continue
        try:
            hits = cfg["fn"](query, limit_per_source)
            if hits:
                out[sid] = hits
        except Exception as e:
            log.warning("Source %s failed: %s", sid, e)

    total = sum(len(v) for v in out.values())
    return {
        "query": query,
        "sources_queried": active,
        "total": total,
        "results": out,
        "note": NO_WIKIPEDIA_NOTE,
    }
