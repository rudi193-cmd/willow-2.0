"""
jeles_sources.py — Trusted, citable source registry for Jeles (the Librarian).
b17: JLSS2  ΔΣ=42

Each source function returns list[dict] with standard citation fields:
  title, url, source, institution, snippet, date, id

Wikipedia is explicitly excluded. Every result here can appear in an academic bibliography.
Sources requiring API keys load from credentials.json.

Sources (29 academic/institutional + 1 opt-in):
  Academic:  OpenAlex, CORE, DOAJ, Europe PMC, Semantic Scholar, Crossref, PubMed, arXiv
  Data/Sci:  Zenodo, DataCite, Wikidata, PubChem, USGS, NASA
  Museums:   Met Museum, Cleveland Museum of Art, V&A Museum, Rijksmuseum (key required)
  Libraries: Library of Congress, Open Library, Chronicling America, Internet Archive, DPLA (key required)
  Heritage:  Smithsonian (key required), Europeana (key required)
  Intl:      Gallica (BnF/France), HAL (France), SciELO (Latin America/Iberia), NDL (Japan)
  Opt-in:    Wikipedia (pass sources=["wikipedia"] — general reference, not for academic citation)

Keys go in ~/.willow/secrets/credentials.json:
  RIJKSMUSEUM_API_KEY  — register at data.rijksmuseum.nl
  DPLA_API_KEY         — free instant key at dp.la/info/developers/codex/
  SMITHSONIAN_API_KEY  — register at api.si.edu
  EUROPEANA_API_KEY    — register at apis.europeana.eu
  SEMANTIC_SCHOLAR_API_KEY — free at semanticscholar.org (lifts rate limits)
"""
from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Optional

from willow.fylgja.willow_home import willow_home

log = logging.getLogger("jeles.sources")

_FLEET_HOME = willow_home()
_CREDS_PATH = _FLEET_HOME / "secrets" / "credentials.json"
_CACHE_DIR  = _FLEET_HOME / "jeles_cache"
_TIMEOUT = 15
_UA = "Willow-Jeles/2.0 (academic librarian; mailto:rudi193@gmail.com)"

# Confidence by source tier — primary institutions > peer-reviewed > aggregators
_SOURCE_CONFIDENCE: dict[str, float] = {
    "loc": 0.92, "met": 0.92, "cleveland": 0.92, "vam": 0.92,
    "nasa": 0.92, "ndl": 0.92, "gallica": 0.92, "smithsonian": 0.92,
    "pubmed": 0.90, "arxiv": 0.90, "crossref": 0.90, "europepmc": 0.90,
    "openalex": 0.85, "core": 0.88, "doaj": 0.88, "hal": 0.88,
    "zenodo": 0.65, "datacite": 0.88, "scielo": 0.88, "usgs": 0.90,  # zenodo: open deposit, no peer review — kept in cache, blocked from auto-promotion
    "europeana": 0.88, "rijksmuseum": 0.90,
    "openlibrary": 0.82, "internet_archive": 0.80, "wikidata": 0.80,
    "chronicling_america": 0.85, "dpla": 0.83, "semantic_scholar": 0.87,
    "pubchem": 0.92,
    "wikipedia": 0.60,
    "psychiatric_times": 0.75,  # trade press, not peer-reviewed
    "inspirehep":     0.92,   # CERN/SLAC-backed HEP literature
    "worldbank":      0.92,   # World Bank development indicators (official)
    "openfoodfacts":  0.82,   # community-maintained, well-curated food DB
    "carbon_intensity": 0.92, # official National Grid ESO (UK government)
    "nws":            0.92,   # official US National Weather Service (NOAA)
    "gdelt":          0.65,   # global news index — high recall, lower precision
    "who_gho":        0.95,   # WHO official global health statistics
    "open_meteo":     0.90,   # ECMWF-backed global weather data
    "patentsview":    0.92,   # USPTO full patent database
    "imf":            0.95,   # IMF official macroeconomic indicators
    "osf":            0.80,   # OSF open preprints (social science, psych, medicine)
    "thesportsdb":    0.78,   # TheSportsDB community sports database
    "frankfurter":    0.95,   # ECB official exchange rates
}


def _load_creds() -> dict:
    try:
        return json.loads(_CREDS_PATH.read_text())
    except Exception:
        return {}


def _get(url: str, headers: dict | None = None) -> Optional[dict | list]:
    h = {"User-Agent": _UA, **(headers or {})}
    try:
        import requests as _req
        r = _req.get(url, headers=h, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as _re:
        # urllib fallback
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
                return json.loads(r.read())
        except Exception as e:
            log.warning("GET %s failed: %s", url[:80], e)
            return None


def _get_html(url: str, headers: dict | None = None) -> Optional[str]:
    h = {"User-Agent": _UA, **(headers or {})}
    try:
        import requests as _req
        r = _req.get(url, headers=h, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.text
    except Exception:
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            log.warning("GET html %s failed: %s", url[:80], e)
            return None


def _write_cache(query: str, results: dict[str, list]) -> None:
    """Append search results to daily JSONL cache with annotation fields."""
    import hashlib
    from datetime import datetime, timezone
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cache_file = _CACHE_DIR / f"{today}.jsonl"
        fetched_at = datetime.now(timezone.utc).isoformat()
        query_words = [w.lower() for w in query.split() if len(w) > 3]
        with cache_file.open("a", encoding="utf-8") as fh:
            for source_id, hits in results.items():
                confidence = _SOURCE_CONFIDENCE.get(source_id, 0.80)
                src_cfg = SOURCES.get(source_id, {})
                domain_tags = src_cfg.get("domain", [])
                for hit in hits:
                    url = hit.get("url", "")
                    cache_id = hashlib.md5(url.encode()).hexdigest()[:8] if url else ""
                    keywords = list(dict.fromkeys(query_words + [source_id] + domain_tags))[:10]
                    tags = [source_id, f"query:{hashlib.md5(query.encode()).hexdigest()[:8]}"] + domain_tags
                    record = {
                        **hit,
                        "id": cache_id,
                        "query": query,
                        "keywords": keywords,
                        "tags": tags,
                        "tier": "fetched",
                        "confidence": confidence,
                        "fetched_at": fetched_at,
                        "promoted": False,
                    }
                    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        log.warning("jeles cache write failed: %s", e)


def _result(title: str, url: str, source: str, institution: str,
            snippet: str = "", date: str = "", rid: str = "") -> dict:
    return {
        "title": (title or "").strip(),
        "url": url,
        "source": source,
        "institution": institution,
        "snippet": (snippet or "").strip()[:400],
        "date": date,
        "id": rid,
    }


# ── ACADEMIC ──────────────────────────────────────────────────────────────────

def search_openalex(query: str, limit: int = 5) -> list[dict]:
    """OpenAlex — 200M+ scholarly works. No key required."""
    url = (
        "https://api.openalex.org/works?search="
        + urllib.parse.quote(query)
        + f"&per-page={limit}&mailto=rudi193@gmail.com"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for item in (data.get("results") or [])[:limit]:
        doi = item.get("doi") or ""
        results.append(_result(
            title=item.get("display_name", ""),
            url=doi if doi else item.get("id", ""),
            source="openalex",
            institution=", ".join(
                i.get("display_name", "")
                for a in (item.get("authorships") or [])[:2]
                for i in (a.get("institutions") or [])[:1]
            ),
            snippet=item.get("abstract", "") or "",
            date=str(item.get("publication_year", "")),
            rid=item.get("id", "").split("/")[-1],
        ))
    return results


def search_core(query: str, limit: int = 5) -> list[dict]:
    """CORE — open access full text. No key required."""
    url = (
        "https://api.core.ac.uk/v3/search/works?q="
        + urllib.parse.quote(query)
        + f"&limit={limit}"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for item in (data.get("results") or [])[:limit]:
        results.append(_result(
            title=item.get("title", ""),
            url=item.get("downloadUrl") or item.get("doi") or "",
            source="core",
            institution=item.get("publisher") or ", ".join(
                j.get("title", "") for j in (item.get("journals") or [])[:1]
            ),
            snippet=item.get("abstract", "") or "",
            date=str(item.get("yearPublished", "")),
            rid=str(item.get("id", "")),
        ))
    return results


def search_doaj(query: str, limit: int = 5) -> list[dict]:
    """DOAJ — Directory of Open Access Journals. No key required."""
    url = (
        "https://doaj.org/api/search/articles/"
        + urllib.parse.quote(query)
        + f"?pageSize={limit}"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for item in (data.get("results") or [])[:limit]:
        bib = item.get("bibjson") or {}
        doi = next((i.get("id", "") for i in (bib.get("identifier") or []) if i.get("type") == "doi"), "")
        link = next((item.get("url", "") for item in (bib.get("link") or [])), "")
        results.append(_result(
            title=bib.get("title", ""),
            url=f"https://doi.org/{doi}" if doi else link,
            source="doaj",
            institution=(bib.get("journal") or {}).get("title", ""),
            snippet=bib.get("abstract", "") or "",
            date=f"{bib.get('year', '')}-{bib.get('month', '')}".strip("-"),
            rid=doi,
        ))
    return results


def search_europepmc(query: str, limit: int = 5) -> list[dict]:
    """Europe PMC — life sciences & biomedical. No key required."""
    url = (
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query="
        + urllib.parse.quote(query)
        + f"&format=json&pageSize={limit}"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for item in ((data.get("resultList") or {}).get("result") or [])[:limit]:
        pmid = item.get("pmid", "")
        doi = item.get("doi", "")
        results.append(_result(
            title=item.get("title", ""),
            url=f"https://doi.org/{doi}" if doi else f"https://europepmc.org/article/{item.get('source','')}/{item.get('id','')}",
            source="europepmc",
            institution=item.get("journalTitle", ""),
            snippet=item.get("abstractText", "") or "",
            date=item.get("firstPublicationDate", ""),
            rid=pmid or item.get("id", ""),
        ))
    return results


def search_semantic_scholar(query: str, limit: int = 5) -> list[dict]:
    """Semantic Scholar — AI-powered academic search. Free key recommended (SEMANTIC_SCHOLAR_API_KEY)."""
    key = _load_creds().get("SEMANTIC_SCHOLAR_API_KEY", "")
    headers = {"x-api-key": key} if key else {}
    url = (
        "https://api.semanticscholar.org/graph/v1/paper/search?query="
        + urllib.parse.quote(query)
        + f"&fields=title,year,authors,externalIds,abstract,url&limit={limit}"
    )
    data = _get(url, headers=headers)
    if not data:
        return []
    results = []
    for item in (data.get("data") or [])[:limit]:
        ext = item.get("externalIds") or {}
        doi = ext.get("DOI", "")
        results.append(_result(
            title=item.get("title", ""),
            url=f"https://doi.org/{doi}" if doi else item.get("url", ""),
            source="semantic_scholar",
            institution=", ".join(
                a.get("name", "") for a in (item.get("authors") or [])[:3]
            ),
            snippet=item.get("abstract", "") or "",
            date=str(item.get("year", "")),
            rid=item.get("paperId", ""),
        ))
    return results


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
            snippet=(item.get("abstract") or "")[:400],
            date=date,
            rid=doi,
        ))
    return results


def search_pubmed(query: str, limit: int = 5) -> list[dict]:
    """PubMed biomedical literature. No key required."""
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
            snippet=", ".join(a.get("name", "") for a in (doc.get("authors") or [])[:3]),
            date=doc.get("pubdate", ""),
            rid=pmid,
        ))
    return results


def search_arxiv(query: str, limit: int = 5) -> list[dict]:
    """arXiv preprints — STEM, CS, Math, Physics. No key required."""
    url = (
        "https://export.arxiv.org/api/query?search_query="
        + urllib.parse.quote(f"all:{query}")
        + f"&max_results={limit}&sortBy=relevance"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            raw = r.read()
    except Exception as e:
        log.warning("arXiv failed: %s", e)
        return []
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
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


# ── DATA / SCIENCE ────────────────────────────────────────────────────────────

def search_zenodo(query: str, limit: int = 5) -> list[dict]:
    """Zenodo — CERN open research repository. No key required."""
    url = (
        "https://zenodo.org/api/records?q="
        + urllib.parse.quote(query)
        + f"&size={limit}"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for item in (data.get("hits", {}).get("hits") or [])[:limit]:
        meta = item.get("metadata", {})
        doi = meta.get("doi", "")
        results.append(_result(
            title=meta.get("title", ""),
            url=f"https://doi.org/{doi}" if doi else item.get("links", {}).get("html", ""),
            source="zenodo",
            institution=item.get("owners", [{}])[0] if item.get("owners") else "Zenodo / CERN",
            snippet=meta.get("description", "") or "",
            date=meta.get("publication_date", ""),
            rid=doi or str(item.get("id", "")),
        ))
    return results


def search_datacite(query: str, limit: int = 5) -> list[dict]:
    """DataCite — DOI registry for research data. No key required."""
    url = (
        "https://api.datacite.org/dois?query="
        + urllib.parse.quote(query)
        + f"&page[size]={limit}"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for item in (data.get("data") or [])[:limit]:
        attrs = item.get("attributes", {})
        doi = attrs.get("doi", "")
        titles = attrs.get("titles") or [{}]
        creators = attrs.get("creators") or []
        results.append(_result(
            title=titles[0].get("title", "") if titles else "",
            url=f"https://doi.org/{doi}" if doi else "",
            source="datacite",
            institution=", ".join(c.get("name", "") for c in creators[:2]),
            snippet=", ".join(
                d.get("description", "") for d in (attrs.get("descriptions") or [])[:1]
            ),
            date=(attrs.get("publicationYear") or ""),
            rid=doi,
        ))
    return results


def search_wikidata(query: str, limit: int = 5) -> list[dict]:
    """Wikidata — structured linked open data (NOT Wikipedia). Citable as structured data source."""
    url = (
        "https://www.wikidata.org/w/api.php?action=wbsearchentities"
        "&search=" + urllib.parse.quote(query)
        + f"&language=en&format=json&limit={limit}"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for item in (data.get("search") or [])[:limit]:
        qid = item.get("id", "")
        results.append(_result(
            title=item.get("label", ""),
            url=item.get("concepturi", f"https://www.wikidata.org/wiki/{qid}"),
            source="wikidata",
            institution="Wikidata / Wikimedia Foundation",
            snippet=item.get("description", ""),
            date="",
            rid=qid,
        ))
    return results


def search_pubchem(query: str, limit: int = 5) -> list[dict]:
    """PubChem — NCBI chemistry database. No key required."""
    search_url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
        + urllib.parse.quote(query)
        + "/JSON"
    )
    data = _get(search_url)
    if not data:
        return []
    results = []
    for compound in (data.get("PC_Compounds") or [])[:limit]:
        cid = compound.get("id", {}).get("id", {}).get("cid", "")
        props = {p.get("urn", {}).get("label", ""): p.get("value", {})
                 for p in (compound.get("props") or [])}
        iupac = props.get("IUPAC Name", {}).get("sval", "")
        formula = props.get("Molecular Formula", {}).get("sval", "")
        results.append(_result(
            title=iupac or query,
            url=f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}",
            source="pubchem",
            institution="PubChem / NCBI",
            snippet=f"Formula: {formula}" if formula else "",
            date="",
            rid=str(cid),
        ))
    return results


def search_usgs(query: str, limit: int = 5) -> list[dict]:
    """USGS Publications Warehouse — geology, hydrology, earth science. No key required."""
    url = (
        "https://pubs.er.usgs.gov/pubs-services/publication?q="
        + urllib.parse.quote(query)
        + f"&pageSize={limit}"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for item in (data.get("records") or [])[:limit]:
        doi = item.get("doi", "")
        results.append(_result(
            title=item.get("title", ""),
            url=f"https://doi.org/{doi}" if doi else item.get("links", [{}])[0].get("url", ""),
            source="usgs",
            institution="U.S. Geological Survey",
            snippet=item.get("docAbstract", "") or "",
            date=str(item.get("publicationYear", "")),
            rid=doi or str(item.get("id", "")),
        ))
    return results


def search_nasa(query: str, limit: int = 5) -> list[dict]:
    """NASA Image & Video Library. No key required."""
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
            url=links[0].get("href", "") if links else "",
            source="nasa",
            institution="NASA",
            snippet=data_block.get("description", ""),
            date=data_block.get("date_created", "")[:10],
            rid=data_block.get("nasa_id", ""),
        ))
    return results


# ── MUSEUMS ───────────────────────────────────────────────────────────────────

def search_met(query: str, limit: int = 5) -> list[dict]:
    """Metropolitan Museum of Art — open access collection. No key required."""
    search_url = (
        "https://collectionapi.metmuseum.org/public/collection/v1/search?q="
        + urllib.parse.quote(query)
        + "&hasImages=true"
    )
    data = _get(search_url)
    if not data:
        return []
    object_ids = (data.get("objectIDs") or [])[:limit]
    results = []
    for oid in object_ids:
        obj = _get(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{oid}")
        if not obj:
            continue
        results.append(_result(
            title=obj.get("title", ""),
            url=obj.get("objectURL", ""),
            source="met",
            institution="Metropolitan Museum of Art",
            snippet=f"{obj.get('artistDisplayName', '')} — {obj.get('objectDate', '')} — {obj.get('medium', '')}".strip(" —"),
            date=obj.get("objectDate", ""),
            rid=str(oid),
        ))
    return results


def search_cleveland(query: str, limit: int = 5) -> list[dict]:
    """Cleveland Museum of Art — open access. No key required."""
    url = (
        "https://openaccess-api.clevelandart.org/api/artworks/?q="
        + urllib.parse.quote(query)
        + f"&limit={limit}&has_image=1"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for item in (data.get("data") or [])[:limit]:
        results.append(_result(
            title=item.get("title", ""),
            url=item.get("url", ""),
            source="cleveland",
            institution="Cleveland Museum of Art",
            snippet=f"{', '.join(c.get('description','') for c in (item.get('creators') or [])[:2])} — {item.get('creation_date','')}".strip(" —"),
            date=item.get("creation_date", ""),
            rid=str(item.get("id", "")),
        ))
    return results


def search_vam(query: str, limit: int = 5) -> list[dict]:
    """Victoria & Albert Museum — decorative arts & design. No key required."""
    url = (
        "https://api.vam.ac.uk/v2/objects/search?q="
        + urllib.parse.quote(query)
        + f"&page_size={limit}"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for item in (data.get("records") or [])[:limit]:
        sys_num = item.get("systemNumber", "")
        results.append(_result(
            title=item.get("_primaryTitle", ""),
            url=f"https://collections.vam.ac.uk/item/{sys_num}/",
            source="vam",
            institution="Victoria & Albert Museum",
            snippet=f"{item.get('_primaryMaker',{}).get('name','')} — {item.get('_primaryDate','')}".strip(" —"),
            date=item.get("_primaryDate", ""),
            rid=sys_num,
        ))
    return results


def search_rijksmuseum(query: str, limit: int = 5) -> list[dict]:
    """Rijksmuseum — Dutch art and history. Requires RIJKSMUSEUM_API_KEY in credentials.json."""
    key = _load_creds().get("RIJKSMUSEUM_API_KEY", "")
    if not key:
        log.debug("Rijksmuseum: no API key — skipping")
        return []
    url = (
        "https://www.rijksmuseum.nl/api/en/collection?q="
        + urllib.parse.quote(query)
        + f"&ps={limit}&key={key}&imgonly=True"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for item in (data.get("artObjects") or [])[:limit]:
        results.append(_result(
            title=item.get("title", ""),
            url=item.get("links", {}).get("web", ""),
            source="rijksmuseum",
            institution="Rijksmuseum",
            snippet=item.get("longTitle", ""),
            date=str(item.get("dating", {}).get("sortingDate", "")),
            rid=item.get("objectNumber", ""),
        ))
    return results


# ── INTERNATIONAL ─────────────────────────────────────────────────────────────

def search_gallica(query: str, limit: int = 5) -> list[dict]:
    """Gallica (BnF) — Bibliothèque nationale de France digital collections. No key required."""
    url = (
        "https://gallica.bnf.fr/SRU?operation=searchRetrieve"
        "&query=dc.subject+all+" + urllib.parse.quote(f'"{query}"')
        + f"&maximumRecords={limit}&version=1.2"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            raw = r.read()
    except Exception as e:
        log.warning("Gallica failed: %s", e)
        return []
    ns_dc = "http://purl.org/dc/elements/1.1/"
    ns_srw = "http://www.loc.gov/zing/srw/"
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    results = []
    for record in root.findall(f".//{{{ns_srw}}}recordData"):
        titles = record.findall(f"{{{ns_dc}}}title")
        identifiers = record.findall(f"{{{ns_dc}}}identifier")
        dates = record.findall(f"{{{ns_dc}}}date")
        descriptions = record.findall(f"{{{ns_dc}}}description")
        url_val = next((i.text for i in identifiers if i.text and i.text.startswith("http")), "")
        results.append(_result(
            title=titles[0].text if titles else "",
            url=url_val,
            source="gallica",
            institution="Gallica / Bibliothèque nationale de France",
            snippet=descriptions[0].text if descriptions else "",
            date=dates[0].text if dates else "",
            rid=url_val.split("/")[-1] if url_val else "",
        ))
    return results[:limit]


def search_hal(query: str, limit: int = 5) -> list[dict]:
    """HAL — French open access scientific archive. No key required."""
    url = (
        "https://api.archives-ouvertes.fr/search/?q="
        + urllib.parse.quote(query)
        + f"&rows={limit}&fl=title_s,uri_s,authFullName_s,producedDate_tdate,journalTitle_s&wt=json"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for item in ((data.get("response") or {}).get("docs") or [])[:limit]:
        titles = item.get("title_s") or [""]
        results.append(_result(
            title=titles[0] if titles else "",
            url=item.get("uri_s", ""),
            source="hal",
            institution=item.get("journalTitle_s", "HAL / archives-ouvertes.fr"),
            snippet=", ".join(item.get("authFullName_s") or []),
            date=(item.get("producedDate_tdate") or "")[:10],
            rid=item.get("uri_s", "").split("/")[-1],
        ))
    return results


def search_scielo(query: str, limit: int = 5) -> list[dict]:
    """SciELO — Latin American, Iberian & South African science. OAI-PMH, no key required."""
    # Use ArticleMeta search (JSON) for keyword search
    url = (
        "https://articlemeta.scielo.org/api/v1/article/identifiers/"
        "?collection=scl&limit=" + str(limit)
    )
    data = _get(url)
    if not data:
        return []
    pids = [obj.get("code") for obj in (data.get("objects") or []) if obj.get("code")][:limit]
    results = []
    for pid in pids[:limit]:
        art = _get(f"https://articlemeta.scielo.org/api/v1/article/?code={pid}&collection=scl")
        if not art:
            continue
        # SciELO uses internal ISIS field codes; v977=title, v10=authors, v30=journal
        title = ""
        for section in (art.get("article", {}).get("v977") or []):
            title = section.get("_", "")
            if title:
                break
        results.append(_result(
            title=title,
            url=f"https://www.scielo.br/j/{pid.split('S')[1][:4].lower()}/a/{pid}/",
            source="scielo",
            institution="SciELO / FAPESP",
            snippet="",
            date="",
            rid=pid,
        ))
    return [r for r in results if r["title"]]


def search_ndl(query: str, limit: int = 5) -> list[dict]:
    """National Diet Library (Japan) — largest library in Japan. SRU, no key required."""
    url = (
        "https://iss.ndl.go.jp/api/sru?operation=searchRetrieve"
        "&query=title%3D" + urllib.parse.quote(f'"{query}"')
        + f"&maximumRecords={limit}&recordSchema=dcndl"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            raw = r.read()
    except Exception as e:
        log.warning("NDL failed: %s", e)
        return []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []
    ns_dc = "http://purl.org/dc/elements/1.1/"
    ns_dcterms = "http://purl.org/dc/terms/"
    results = []
    for record in root.findall(".//{http://www.loc.gov/zing/srw/}recordData"):
        titles = record.findall(f".//{{{ns_dcterms}}}title") or record.findall(f".//{{{ns_dc}}}title")
        dates = record.findall(f".//{{{ns_dcterms}}}issued") or record.findall(f".//{{{ns_dc}}}date")
        publishers = record.findall(f".//{{{ns_dcterms}}}publisher") or record.findall(f".//{{{ns_dc}}}publisher")
        ids = record.findall(f".//{{{ns_dc}}}identifier")
        url_val = next((i.text for i in ids if i.text and i.text.startswith("http")), "")
        title_text = titles[0].text if titles else ""
        if not title_text:
            continue
        results.append(_result(
            title=title_text,
            url=url_val,
            source="ndl",
            institution="National Diet Library / Japan",
            snippet=publishers[0].text if publishers else "",
            date=dates[0].text if dates else "",
            rid=url_val.split("/")[-1] if url_val else "",
        ))
    return results[:limit]


# ── LIBRARIES & ARCHIVES ──────────────────────────────────────────────────────

def search_loc(query: str, limit: int = 5) -> list[dict]:
    """Library of Congress digital collections. No key required."""
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
        desc = item.get("description", "")
        results.append(_result(
            title=item.get("title", ""),
            url=item.get("url", ""),
            source="loc",
            institution="Library of Congress",
            snippet=desc[0] if isinstance(desc, list) else desc,
            date=item.get("date", ""),
            rid=item.get("id", ""),
        ))
    return results


def search_openlibrary(query: str, limit: int = 5) -> list[dict]:
    """Open Library — books and historical texts. No key required."""
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


def search_chronicling_america(query: str, limit: int = 5) -> list[dict]:
    """Chronicling America — historic US newspapers 1770-1963. No key required."""
    url = (
        "https://chroniclingamerica.loc.gov/search/pages/results/?andtext="
        + urllib.parse.quote(query)
        + f"&format=json&rows={limit}"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for item in (data.get("items") or [])[:limit]:
        results.append(_result(
            title=item.get("title", ""),
            url="https://chroniclingamerica.loc.gov" + (item.get("id") or ""),
            source="chronicling_america",
            institution=f"Chronicling America — {item.get('title_normal', '')}",
            snippet=item.get("ocr_eng", "")[:300] or "",
            date=item.get("date", ""),
            rid=item.get("id", ""),
        ))
    return results


def search_dpla(query: str, limit: int = 5) -> list[dict]:
    """DPLA — aggregates US libraries, archives, museums. Requires DPLA_API_KEY in credentials.json (free, instant)."""
    key = _load_creds().get("DPLA_API_KEY", "")
    if not key:
        log.debug("DPLA: no API key — skipping")
        return []
    url = (
        "https://api.dp.la/v2/items?q="
        + urllib.parse.quote(query)
        + f"&page_size={limit}&api_key={key}"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for item in (data.get("docs") or [])[:limit]:
        src = item.get("sourceResource", {})
        results.append(_result(
            title=(src.get("title") or [""])[0] if isinstance(src.get("title"), list) else src.get("title", ""),
            url=item.get("isShownAt", ""),
            source="dpla",
            institution=item.get("dataProvider", ""),
            snippet=(src.get("description") or [""])[0] if isinstance(src.get("description"), list) else src.get("description", ""),
            date=(src.get("date") or {}).get("displayDate", "") if isinstance(src.get("date"), dict) else "",
            rid=item.get("id", ""),
        ))
    return results


def search_internet_archive(query: str, limit: int = 5) -> list[dict]:
    """Internet Archive — books, films, audio, web. No key required."""
    url = (
        "https://archive.org/advancedsearch.php?q="
        + urllib.parse.quote(query)
        + f"&fl[]=identifier,title,description,date,creator&rows={limit}&output=json"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for doc in ((data.get("response") or {}).get("docs") or [])[:limit]:
        identifier = doc.get("identifier", "")
        results.append(_result(
            title=doc.get("title", ""),
            url=f"https://archive.org/details/{identifier}" if identifier else "",
            source="internet_archive",
            institution="Internet Archive",
            snippet=doc.get("description", "") or "",
            date=str(doc.get("date", "")),
            rid=identifier,
        ))
    return results


# ── HERITAGE ──────────────────────────────────────────────────────────────────

def search_smithsonian(query: str, limit: int = 5) -> list[dict]:
    """Smithsonian Open Access. Requires SMITHSONIAN_API_KEY in credentials.json."""
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
            snippet="",
            date=row.get("content", {}).get("indexedStructured", {}).get("date", [""])[0],
            rid=row.get("id", ""),
        ))
    return results


def search_wikipedia(query: str, limit: int = 3) -> list[dict]:
    """Wikipedia REST API — quick entity lookups. General reference only; not for academic citation."""
    import urllib.parse as _up
    encoded = _up.quote(query, safe="")
    data = _get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}")
    if data and data.get("type") not in ("disambiguation", "no-extract", None):
        return [_result(
            title=data.get("title", ""),
            url=(data.get("content_urls") or {}).get("desktop", {}).get("page", ""),
            source="wikipedia",
            institution="Wikimedia Foundation",
            snippet=data.get("extract", "")[:400],
            rid=data.get("pageid", ""),
        )]
    # Fallback: search API
    search_data = _get(
        f"https://en.wikipedia.org/w/api.php?action=query&list=search"
        f"&srsearch={encoded}&format=json&srlimit={limit}"
    )
    if not search_data:
        return []
    items = (search_data.get("query") or {}).get("search", [])
    results = []
    for item in items[:limit]:
        title = item.get("title", "")
        snippet = item.get("snippet", "").replace("<span class=\"searchmatch\">", "").replace("</span>", "")
        enc_title = _up.quote(title, safe="")
        results.append(_result(
            title=title,
            url=f"https://en.wikipedia.org/wiki/{enc_title}",
            source="wikipedia",
            institution="Wikimedia Foundation",
            snippet=snippet,
            rid=str(item.get("pageid", "")),
        ))
    return results


def search_sep(query: str, limit: int = 5) -> list[dict]:
    """Stanford Encyclopedia of Philosophy — peer-reviewed philosophical entries. No key required."""
    url = (
        "https://plato.stanford.edu/search/searcher.py?query="
        + urllib.parse.quote(query)
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            html = r.read().decode("utf-8", errors="replace")
    except Exception:
        return []
    results = []
    import re as _re
    seen: set[str] = set()
    # SEP search HTML (2024+): entry=/entries/slug/ in redirect URLs, title often in <b>.
    for m in _re.finditer(
        r'entry=(/entries/[^/&"]+/)[^"]*"[^>]*>(?:<b>)?([^<\n]{3,120})',
        html,
    ):
        path, title = m.group(1), _re.sub(r"\s+", " ", m.group(2)).strip()
        if not title or title.lower().startswith("stanford"):
            continue
        slug = path.strip("/").split("/")[-1]
        if slug in seen:
            continue
        seen.add(slug)
        results.append(_result(
            title=title,
            url=f"https://plato.stanford.edu{path}",
            source="sep",
            institution="Stanford Encyclopedia of Philosophy",
            snippet="",
            date="",
            rid=slug,
        ))
        if len(results) >= limit:
            break
    return results


def search_gutenberg(query: str, limit: int = 5) -> list[dict]:
    """Project Gutenberg — public domain books via Gutendex API. No key required."""
    url = (
        "https://gutendex.com/books/?search="
        + urllib.parse.quote(query)
        + f"&page_size={limit}"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for book in (data.get("results") or [])[:limit]:
        title = book.get("title", "")
        authors = ", ".join(a.get("name", "") for a in (book.get("authors") or []))
        bid = book.get("id", "")
        subjects = "; ".join((book.get("subjects") or [])[:3])
        results.append(_result(
            title=title,
            url=f"https://www.gutenberg.org/ebooks/{bid}" if bid else "",
            source="gutenberg",
            institution="Project Gutenberg",
            snippet=f"{authors} — {subjects}".strip(" —") if (authors or subjects) else "",
            date=str(book.get("copyright") or ""),
            rid=str(bid),
        ))
    return results


def search_bhl(query: str, limit: int = 5) -> list[dict]:
    """Biodiversity Heritage Library — natural history, taxonomy, ecology literature. API key required."""
    import os
    api_key = os.environ.get("BHL_API_KEY", "")
    if not api_key:
        return []
    url = (
        "https://www.biodiversitylibrary.org/api3?op=PublicationSearch"
        "&searchtype=F&searchterm="
        + urllib.parse.quote(query)
        + f"&page=1&pageSize={limit}&format=json&apikey={api_key}"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for item in (data.get("Result") or [])[:limit]:
        bid = item.get("BibliographyID") or item.get("TitleID", "")
        results.append(_result(
            title=item.get("FullTitle") or item.get("Title", ""),
            url=f"https://www.biodiversitylibrary.org/bibliography/{bid}" if bid else "",
            source="bhl",
            institution="Biodiversity Heritage Library",
            snippet=(item.get("Note") or "")[:200],
            date=str(item.get("PublicationDate") or item.get("Date", "")),
            rid=str(bid),
        ))
    return results


def search_courtlistener(query: str, limit: int = 5) -> list[dict]:
    """CourtListener — US federal and state case law. No key required (throttled)."""
    url = (
        "https://www.courtlistener.com/api/rest/v4/search/?q="
        + urllib.parse.quote(query)
        + f"&type=o&order_by=score+desc&format=json&page_size={limit}"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for item in (data.get("results") or [])[:limit]:
        case_name = item.get("caseName") or item.get("case_name", "")
        court = item.get("court_id", "")
        date = (item.get("dateFiled") or "")[:10]
        abs_url = item.get("absolute_url", "")
        snippet = (item.get("snippet") or "")[:200]
        results.append(_result(
            title=case_name,
            url=f"https://www.courtlistener.com{abs_url}" if abs_url else "",
            source="courtlistener",
            institution="CourtListener",
            snippet=f"{court} — {snippet}".strip(" —") if (court or snippet) else "",
            date=date,
            rid=str(item.get("id", "")),
        ))
    return results


def search_base(query: str, limit: int = 5) -> list[dict]:
    """BASE (Bielefeld Academic Search Engine) — 350M+ open access documents. No key required."""
    url = (
        "https://api.base-search.net/cgi-bin/BaseHttpSearchInterface.fcgi"
        "?func=PerformSearch&query="
        + urllib.parse.quote(query)
        + f"&hits={limit}&format=json"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for item in ((data.get("response") or {}).get("docs") or [])[:limit]:
        title = item.get("dctitle", "") or ""
        if isinstance(title, list):
            title = title[0] if title else ""
        creator = item.get("dccreator", "") or ""
        if isinstance(creator, list):
            creator = "; ".join(creator[:2])
        link = item.get("dclink") or item.get("dcidentifier", "")
        if isinstance(link, list):
            link = link[0] if link else ""
        date = str(item.get("dcyear", "") or "")
        desc = item.get("dcdescription", "") or ""
        if isinstance(desc, list):
            desc = desc[0] if desc else ""
        results.append(_result(
            title=title,
            url=link,
            source="base",
            institution="BASE / Bielefeld University",
            snippet=f"{creator} — {str(desc)[:150]}".strip(" —") if (creator or desc) else "",
            date=date,
            rid=item.get("dcidentifier", [""])[0] if isinstance(item.get("dcidentifier"), list) else item.get("dcidentifier", ""),
        ))
    return results


def search_dblp(query: str, limit: int = 5) -> list[dict]:
    """DBLP — computer science bibliography. No key required."""
    url = (
        "https://dblp.org/search/publ/api?q="
        + urllib.parse.quote(query)
        + f"&format=json&h={limit}"
    )
    data = _get(url)
    if not data:
        return []
    hits = (data.get("result") or {}).get("hits") or {}
    results = []
    for item in (hits.get("hit") or [])[:limit]:
        info = item.get("info") or {}
        authors = info.get("authors") or {}
        author_list = authors.get("author", [])
        if isinstance(author_list, dict):
            author_list = [author_list]
        author_str = ", ".join(
            (a.get("text") or a) if isinstance(a, dict) else str(a)
            for a in author_list[:3]
        )
        results.append(_result(
            title=info.get("title", ""),
            url=info.get("url", ""),
            source="dblp",
            institution="DBLP",
            snippet=f"{author_str} — {info.get('venue', '')}".strip(" —") if (author_str or info.get("venue")) else "",
            date=str(info.get("year", "")),
            rid=item.get("@id", ""),
        ))
    return results


def search_openfda(query: str, limit: int = 5) -> list[dict]:
    """OpenFDA — drug labels, adverse events, food/device safety. No key required."""
    url = (
        "https://api.fda.gov/drug/label.json?search="
        + urllib.parse.quote(f'description:"{query}" OR indications_and_usage:"{query}"')
        + f"&limit={limit}"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for item in (data.get("results") or [])[:limit]:
        openfda = item.get("openfda") or {}
        brand = (openfda.get("brand_name") or [""])[0]
        generic = (openfda.get("generic_name") or [""])[0]
        title = brand or generic or "Drug Label"
        manuf = (openfda.get("manufacturer_name") or [""])[0]
        indications = (item.get("indications_and_usage") or [""])[0][:200]
        app_num = (openfda.get("application_number") or [""])[0]
        results.append(_result(
            title=title,
            url=f"https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo={app_num.replace('NDA', '').replace('ANDA', '').strip()}" if app_num else "",
            source="openfda",
            institution="U.S. FDA",
            snippet=f"{manuf} — {indications}".strip(" —") if (manuf or indications) else "",
            date="",
            rid=app_num,
        ))
    return results


def search_eol(query: str, limit: int = 5) -> list[dict]:
    """Encyclopedia of Life — species taxonomy and ecology. No key required."""
    url = (
        "https://eol.org/api/search/1.0.json?q="
        + urllib.parse.quote(query)
        + "&page=1"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for item in (data.get("results") or [])[:limit]:
        eid = item.get("id", "")
        title = item.get("title", "")
        content = item.get("content", "")
        results.append(_result(
            title=title,
            url=f"https://eol.org/pages/{eid}" if eid else "",
            source="eol",
            institution="Encyclopedia of Life",
            snippet=content[:200] if content else "",
            date="",
            rid=str(eid),
        ))
    return results


def search_gbif(query: str, limit: int = 5) -> list[dict]:
    """GBIF (Global Biodiversity Information Facility) — occurrence records. No key required."""
    url = (
        "https://api.gbif.org/v1/species/search?q="
        + urllib.parse.quote(query)
        + f"&limit={limit}"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for item in (data.get("results") or [])[:limit]:
        key = item.get("key") or item.get("nubKey", "")
        sci_name = item.get("scientificName", "")
        canonical = item.get("canonicalName", "")
        rank = item.get("rank", "")
        kingdom = item.get("kingdom", "")
        snippet = f"{rank} — Kingdom: {kingdom}".strip(" —") if (rank or kingdom) else ""
        results.append(_result(
            title=sci_name or canonical,
            url=f"https://www.gbif.org/species/{key}" if key else "",
            source="gbif",
            institution="GBIF",
            snippet=snippet,
            date="",
            rid=str(key),
        ))
    return results


def search_nominatim(query: str, limit: int = 5) -> list[dict]:
    """OpenStreetMap Nominatim — geographic place search. No key, 1 req/sec limit."""
    url = (
        "https://nominatim.openstreetmap.org/search?q="
        + urllib.parse.quote(query)
        + f"&format=json&limit={limit}&addressdetails=1"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept-Language": "en"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            items = json.loads(r.read())
    except Exception:
        return []
    results = []
    for item in (items or [])[:limit]:
        osm_id = item.get("osm_id", "")
        osm_type = item.get("osm_type", "")
        addr = item.get("address") or {}
        country = addr.get("country", "")
        place_type = item.get("type", "") or item.get("class", "")
        snippet = f"{place_type} — {country}".strip(" —") if (place_type or country) else ""
        results.append(_result(
            title=item.get("display_name", ""),
            url=f"https://www.openstreetmap.org/{osm_type}/{osm_id}" if osm_id else "",
            source="nominatim",
            institution="OpenStreetMap",
            snippet=snippet,
            date="",
            rid=str(osm_id),
        ))
    return results


def search_openaire(query: str, limit: int = 5) -> list[dict]:
    """OpenAIRE — European open research publications. No key required."""
    url = (
        "https://api.openaire.eu/search/publications?title="
        + urllib.parse.quote(query)
        + f"&format=json&page=1&size={limit}"
    )
    data = _get(url)
    if not data:
        return []
    try:
        results_raw = (
            data.get("response", {})
                .get("results", {})
                .get("result") or []
        )
    except Exception:
        return []
    results = []
    for item in (results_raw or [])[:limit]:
        metadata = (item.get("metadata") or {}).get("oaf:entity", {}).get("oaf:result", {})
        if not metadata:
            continue
        title_obj = metadata.get("title") or {}
        title = title_obj.get("$") if isinstance(title_obj, dict) else (title_obj[0].get("$") if isinstance(title_obj, list) and title_obj else "")
        pid_list = metadata.get("pid") or []
        if isinstance(pid_list, dict):
            pid_list = [pid_list]
        doi = next((p.get("$") for p in pid_list if isinstance(p, dict) and p.get("@classid") == "doi"), "")
        date = (metadata.get("dateofacceptance") or {}).get("$", "")[:10] if isinstance(metadata.get("dateofacceptance"), dict) else ""
        results.append(_result(
            title=title or "",
            url=f"https://doi.org/{doi}" if doi else "",
            source="openaire",
            institution="OpenAIRE",
            snippet="",
            date=date,
            rid=doi,
        ))
    return results


def search_inaturalist(query: str, limit: int = 5) -> list[dict]:
    """iNaturalist — citizen science species observations. No key required for search."""
    url = (
        "https://api.inaturalist.org/v1/taxa?q="
        + urllib.parse.quote(query)
        + f"&per_page={limit}&order_by=observations_count"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for item in (data.get("results") or [])[:limit]:
        taxon_id = item.get("id", "")
        name = item.get("name", "")
        preferred = item.get("preferred_common_name", "")
        rank = item.get("rank", "")
        obs_count = item.get("observations_count", 0)
        title = f"{preferred} ({name})" if preferred else name
        snippet = f"{rank.capitalize()} — {obs_count:,} observations" if rank else ""
        results.append(_result(
            title=title,
            url=f"https://www.inaturalist.org/taxa/{taxon_id}" if taxon_id else "",
            source="inaturalist",
            institution="iNaturalist",
            snippet=snippet,
            date="",
            rid=str(taxon_id),
        ))
    return results


def search_federal_register(query: str, limit: int = 5) -> list[dict]:
    """Federal Register (US) — federal rulemaking, executive orders, notices. No key required."""
    url = (
        "https://www.federalregister.gov/api/v1/documents.json"
        "?conditions%5Bterm%5D=" + urllib.parse.quote(query)
        + f"&per_page={limit}&order=relevance"
        "&fields%5B%5D=title&fields%5B%5D=document_number&fields%5B%5D=type"
        "&fields%5B%5D=publication_date&fields%5B%5D=abstract"
        "&fields%5B%5D=html_url&fields%5B%5D=agency_names"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for item in (data.get("results") or [])[:limit]:
        agencies = ", ".join((item.get("agency_names") or [])[:2])
        doc_type = item.get("type", "")
        snippet = f"{doc_type} — {agencies} — {(item.get('abstract') or '')[:150]}".strip(" —")
        results.append(_result(
            title=item.get("title", ""),
            url=item.get("html_url", ""),
            source="federal_register",
            institution="U.S. Federal Register",
            snippet=snippet,
            date=(item.get("publication_date") or "")[:10],
            rid=item.get("document_number", ""),
        ))
    return results


def search_datagov(query: str, limit: int = 5) -> list[dict]:
    """data.gov — US government open datasets (CKAN). No key required."""
    # Use safe query encoding — keep only alnum+spaces, collapse spaces
    safe_q = urllib.parse.quote_plus(" ".join(query.split()[:8]))
    url = f"https://catalog.data.gov/api/3/action/package_search?q={safe_q}&rows={limit}"
    data = _get(url)
    if not data:
        return []
    results = []
    for item in ((data.get("result") or {}).get("results") or [])[:limit]:
        org = (item.get("organization") or {}).get("title", "")
        notes = (item.get("notes") or "")[:200]
        results.append(_result(
            title=item.get("title", ""),
            url=f"https://catalog.data.gov/dataset/{item.get('name', '')}",
            source="datagov",
            institution="data.gov (U.S. Government)",
            snippet=f"{org} — {notes}".strip(" —") if (org or notes) else "",
            date=(item.get("metadata_modified") or "")[:10],
            rid=item.get("id", ""),
        ))
    return results


def search_uk_legislation(query: str, limit: int = 5) -> list[dict]:
    """legislation.gov.uk — UK Acts of Parliament, statutory instruments. No key required."""
    url = (
        "https://www.legislation.gov.uk/search?title="
        + urllib.parse.quote(query)
        + "&format=json"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            data = json.loads(r.read())
    except Exception:
        return []
    results = []
    for item in (data.get("items") or [])[:limit]:
        leg_type = item.get("type", {})
        if isinstance(leg_type, dict):
            leg_type = leg_type.get("value", "")
        year = str(item.get("year", ""))
        title = item.get("title", "")
        href = item.get("href", "")
        results.append(_result(
            title=title,
            url=f"https://www.legislation.gov.uk{href}" if href and not href.startswith("http") else href,
            source="uk_legislation",
            institution="legislation.gov.uk",
            snippet=f"{leg_type} {year}".strip(),
            date=year,
            rid=href,
        ))
    return results


def search_eu_data(query: str, limit: int = 5) -> list[dict]:
    """data.europa.eu — EU open data portal (CKAN). No key required."""
    url = (
        "https://data.europa.eu/api/hub/search/datasets?query="
        + urllib.parse.quote(query)
        + f"&limit={limit}&facets=false"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for item in (data.get("result", {}).get("results", []) or [])[:limit]:
        pub = (item.get("publisher") or {}).get("name", "")
        desc = (item.get("description") or {})
        if isinstance(desc, dict):
            desc = desc.get("en", "") or next(iter(desc.values()), "")
        results.append(_result(
            title=(item.get("title") or {}).get("en", "") or item.get("title", "") if isinstance(item.get("title"), dict) else item.get("title", ""),
            url=item.get("landingPage", ""),
            source="eu_data",
            institution="data.europa.eu (EU)",
            snippet=f"{pub} — {str(desc)[:150]}".strip(" —") if (pub or desc) else "",
            date=(item.get("modified") or "")[:10],
            rid=item.get("id", ""),
        ))
    return results


def search_musicbrainz(query: str, limit: int = 5) -> list[dict]:
    """MusicBrainz — open music encyclopedia. Artists, recordings, albums. No key required.
    Searches release-groups (albums/singles) first; falls back to recordings for track queries."""
    q_lower = query.lower()
    use_releases = any(w in q_lower for w in ["album", "release", "discography", "ep", "lp", "record"])

    if use_releases:
        # Strip the type word to get artist name, then use Lucene artist: syntax
        artist_name = re.sub(
            r"\b(albums?|discography|ep|lp|records?|singles?|releases?)\b", "", query, flags=re.IGNORECASE
        ).strip()
        # Filter to Albums only when query is album/discography context
        type_filter = " AND primarytype:Album" if any(
            w in q_lower for w in ["album", "discography", "lp"]
        ) else ""
        mb_query = f'artist:"{artist_name}"{type_filter}' if artist_name else query
        url = (
            "https://musicbrainz.org/ws/2/release-group?query="
            + urllib.parse.quote(mb_query)
            + f"&limit={limit}&fmt=json"
        )
        data = _get(url)
        items = (data or {}).get("release-groups") or []
        results = []
        for item in items[:limit]:
            artist = ", ".join(
                c.get("artist", {}).get("name", "")
                for c in (item.get("artist-credit") or [])
                if isinstance(c, dict)
            )
            mbid = item.get("id", "")
            rtype = item.get("primary-type", "")
            results.append(_result(
                title=item.get("title", ""),
                url=f"https://musicbrainz.org/release-group/{mbid}" if mbid else "",
                source="musicbrainz",
                institution="MusicBrainz",
                snippet=f"{artist} — {rtype}".strip(" —") if (artist or rtype) else "",
                date=(item.get("first-release-date") or "")[:10],
                rid=mbid,
            ))
        if results:
            return results

    # Fall through to recording search
    url = (
        "https://musicbrainz.org/ws/2/recording?query="
        + urllib.parse.quote(query)
        + f"&limit={limit}&fmt=json"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for item in (data.get("recordings") or [])[:limit]:
        artist = ", ".join(
            c.get("artist", {}).get("name", "")
            for c in (item.get("artist-credit") or [])
            if isinstance(c, dict)
        )
        releases = item.get("releases") or []
        release_title = releases[0].get("title", "") if releases else ""
        date = (releases[0].get("date", "") if releases else "") or item.get("first-release-date", "")
        mbid = item.get("id", "")
        results.append(_result(
            title=item.get("title", ""),
            url=f"https://musicbrainz.org/recording/{mbid}" if mbid else "",
            source="musicbrainz",
            institution="MusicBrainz",
            snippet=f"{artist} — {release_title}".strip(" —"),
            date=date[:10] if date else "",
            rid=mbid,
        ))
    return results


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


# ── Plugin sources ─────────────────────────────────────────────────────────────
# Functions only. Registration lives in jeles_sources + jeles_domain_routes DB.
# To add a source: write search_X() here, then INSERT into the DB tables.

def search_omdb(query: str, limit: int = 5) -> list[dict]:
    """OMDb — Open Movie Database. Movies, B-movies, horror, cult cinema. Key required."""
    import os
    api_key = os.environ.get("OMDB_API_KEY", "")
    if not api_key:
        return []
    url = (
        "http://www.omdbapi.com/?s=" + urllib.parse.quote(query)
        + f"&type=movie&apikey={api_key}"
    )
    data = _get(url)
    if not data:
        return []
    results = []
    for item in (data.get("Search") or [])[:limit]:
        imdb_id = item.get("imdbID", "")
        results.append(_result(
            title=item.get("Title", ""),
            url=f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else "",
            source="omdb",
            institution="OMDb / IMDb",
            snippet=f"{item.get('Type','').title()} · {item.get('Year','')}",
            date=item.get("Year", ""),
            rid=imdb_id,
        ))
    return results


def search_isfdb(query: str, limit: int = 5) -> list[dict]:
    """ISFDB — Internet Speculative Fiction Database. Sci-fi, horror, fantasy, pulp."""
    import re
    url = (
        "http://www.isfdb.org/cgi-bin/se.cgi?arg="
        + urllib.parse.quote(query)
        + "&type=Fiction+Titles"
    )
    html = _get_html(url)
    if not html:
        return []
    results = []
    title_re  = re.compile(r'title\.cgi\?(\d+)">([^<]{3,120})</a>')
    author_re = re.compile(r'author\.cgi\?[^"]+">([^<]+)</a>')
    year_re   = re.compile(r'<td[^>]*class="[^"]*year[^"]*"[^>]*>(\d{4})</td>')
    titles  = title_re.findall(html)
    authors = author_re.findall(html)
    years   = year_re.findall(html)
    for i, (tid, title) in enumerate(titles[:limit]):
        author  = authors[i] if i < len(authors) else ""
        year    = years[i]   if i < len(years)   else ""
        results.append(_result(
            title=title.strip(),
            url=f"http://www.isfdb.org/cgi-bin/title.cgi?{tid}",
            source="isfdb",
            institution="Internet Speculative Fiction Database",
            snippet=author,
            date=year,
            rid=tid,
        ))
    return results


def search_fbi_vault(query: str, limit: int = 5) -> list[dict]:
    """FBI Records Vault — declassified FBI files on persons, events, organizations."""
    import re
    # Try Plone JSON API first
    url = (
        "https://vault.fbi.gov/@search?SearchableText="
        + urllib.parse.quote(query)
        + f"&portal_type:list=File&b_size={limit}"
    )
    data = _get(url)
    items = []
    if isinstance(data, dict):
        items = data.get("items") or data.get("@components", {}).get("items", [])
    elif isinstance(data, list):
        items = data
    results = []
    for item in items[:limit]:
        results.append(_result(
            title=item.get("title", ""),
            url=item.get("@id", ""),
            source="fbi_vault",
            institution="FBI Records Vault (Declassified)",
            snippet=(item.get("description") or "")[:200],
            date=(item.get("effective") or "")[:10],
            rid=item.get("@id", ""),
        ))
    if results:
        return results
    # HTML fallback
    html = _get_html(
        "https://vault.fbi.gov/search?SearchableText=" + urllib.parse.quote(query)
    )
    if not html:
        return []
    links = re.findall(r'href="(https://vault\.fbi\.gov/[^"#]{5,200})"[^>]*>([^<]{5,120})</a>', html)
    for url_found, title in links[:limit]:
        results.append(_result(
            title=title.strip(),
            url=url_found,
            source="fbi_vault",
            institution="FBI Records Vault (Declassified)",
            snippet="",
            date="",
            rid=url_found,
        ))
    return results


def search_ig_nobel(query: str, limit: int = 5) -> list[dict]:
    """Ig Nobel Prize archive — unusual research that makes you laugh then think."""
    import re
    url = "https://www.improbable.com/?s=" + urllib.parse.quote(query)
    html = _get_html(url)
    if not html:
        return []
    title_re   = re.compile(r'class="entry-title[^"]*">\s*<a href="([^"]+)"[^>]*>([^<]+)</a>', re.S)
    excerpt_re = re.compile(r'class="entry-summary[^"]*">\s*<p>([^<]{10,400})</p>', re.S)
    titles   = title_re.findall(html)
    excerpts = [e.strip() for e in excerpt_re.findall(html)]
    results  = []
    for i, (link, title) in enumerate(titles[:limit]):
        results.append(_result(
            title=title.strip(),
            url=link,
            source="ig_nobel",
            institution="Improbable Research (Ig Nobel)",
            snippet=excerpts[i] if i < len(excerpts) else "",
            date="",
            rid=link,
        ))
    return results


def search_psychiatric_times(query: str, limit: int = 5) -> list[dict]:
    """Psychiatric Times — clinical psychiatry news, case reports, and review articles.
    HTML scraper (no API key). Press tier — trade press, not peer-reviewed."""
    import re as _re
    url = (
        "https://www.psychiatrictimes.com/search#q="
        + urllib.parse.quote(query)
        + "&t=All"
    )
    html = _get_html(url)
    if not html:
        return []

    results: list[dict] = []
    # Article links under /view/ path
    link_re = _re.compile(
        r'href="(/view/[a-z0-9-]{5,120})"[^>]*>\s*([^<]{10,200})\s*</a>',
        _re.S,
    )
    date_re = _re.compile(
        r'\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4})\b'
    )
    seen: set[str] = set()
    for m in link_re.finditer(html):
        path = m.group(1)
        title = _re.sub(r'\s+', ' ', m.group(2)).strip()
        if path in seen or not title:
            continue
        seen.add(path)
        nearby = html[max(0, m.start() - 200): m.start() + 400]
        date_m = date_re.search(nearby)
        date = date_m.group(1) if date_m else ""
        results.append(_result(
            title=title,
            url=f"https://www.psychiatrictimes.com{path}",
            source="psychiatric_times",
            institution="Psychiatric Times",
            snippet="",
            date=date,
            rid=path,
        ))
        if len(results) >= limit:
            break
    return results


# ── HIGH-ENERGY PHYSICS ───────────────────────────────────────────────────────

def search_inspirehep(query: str, limit: int = 5) -> list[dict]:
    """InspireHEP — CERN/SLAC high-energy physics literature. No key required."""
    url = (
        "https://inspirehep.net/api/literature?q="
        + urllib.parse.quote(query)
        + f"&sort=mostrecent&size={limit}"
        + "&fields=titles,abstracts,dois,arxiv_eprints,publication_info,authors"
    )
    data = _get(url)
    if not data:
        return []
    hits = (data.get("hits") or {}).get("hits") or []
    results = []
    for item in hits[:limit]:
        meta = item.get("metadata") or {}
        title = ((meta.get("titles") or [{}])[0]).get("title", "")
        abstract = ((meta.get("abstracts") or [{}])[0]).get("value", "")
        doi = ((meta.get("dois") or [{}])[0]).get("value", "")
        arxiv = ((meta.get("arxiv_eprints") or [{}])[0]).get("value", "")
        pub = (meta.get("publication_info") or [{}])[0]
        year = str(pub.get("year", ""))
        link = f"https://doi.org/{doi}" if doi else (f"https://arxiv.org/abs/{arxiv}" if arxiv else "")
        results.append(_result(
            title=title,
            url=link,
            source="inspirehep",
            institution="INSPIRE-HEP (CERN)",
            snippet=abstract,
            date=year,
            rid=doi or arxiv,
        ))
    return results


# ── ECONOMICS ─────────────────────────────────────────────────────────────────

def search_worldbank(query: str, limit: int = 5) -> list[dict]:
    """World Bank Open Data — global development indicators (WDI). No key required.
    The v2 /indicator endpoint has no free-text search (the `q=` param is ignored and
    returns indicators alphabetically), so fetch the WDI indicator list and rank
    client-side by whole-word relevance — title weighted over description."""
    url = "https://api.worldbank.org/v2/indicator?format=json&per_page=2000&source=2"
    data = _get(url)
    if not data or not isinstance(data, list) or len(data) < 2:
        return []
    indicators = data[1] or []
    q_terms = [t for t in query.lower().split() if len(t) > 2]
    def _words(s: str) -> set:
        return {w for w in "".join(c if c.isalnum() else " " for c in (s or "").lower()).split()}
    if q_terms:
        # Whole-word match (so "product" does not hit "production"), ranked by
        # relevance — alphabetical order otherwise buries the real match under AG.*.
        scored = []
        for item in indicators:
            name_w = _words(item.get("name"))
            note_w = _words(item.get("sourceNote"))
            score = sum((3 if t in name_w else 0) + (1 if t in note_w else 0) for t in q_terms)
            if score > 0:
                scored.append((score, item))
        scored.sort(key=lambda x: -x[0])
        matches = [item for _, item in scored[:limit]]
    else:
        matches = indicators[:limit]
    results = []
    for item in matches:
        iid = item.get("id", "")
        name = item.get("name", "")
        source = (item.get("sourceNote") or "")[:300]
        topic = ", ".join(t.get("value", "") for t in (item.get("topics") or []) if t.get("value"))
        results.append(_result(
            title=name,
            url=f"https://data.worldbank.org/indicator/{iid}" if iid else "https://data.worldbank.org",
            source="worldbank",
            institution="World Bank Open Data",
            snippet=source or topic,
            date="",
            rid=iid,
        ))
    return results


# ── FOOD & NUTRITION ──────────────────────────────────────────────────────────

def search_openfoodfacts(query: str, limit: int = 5) -> list[dict]:
    """Open Food Facts — global food product & nutrient database. No key required."""
    url = (
        "https://world.openfoodfacts.org/cgi/search.pl?search_terms="
        + urllib.parse.quote(query)
        + f"&search_simple=1&action=process&json=1&page_size={limit}"
    )
    data = _get(url)
    if not data:
        return []
    products = (data.get("products") or [])[:limit]
    results = []
    for p in products:
        name = p.get("product_name", "").strip()
        if not name:
            continue
        categories = (p.get("categories") or "").split(",")[0].strip()
        brand = p.get("brands", "").split(",")[0].strip()
        quantity = p.get("quantity", "")
        nut = p.get("nutriments") or {}
        kcal = nut.get("energy-kcal_100g", "")
        snippet_parts = [x for x in [brand, categories, (f"{kcal} kcal/100g" if kcal else "")] if x]
        pid = p.get("_id") or p.get("id", "")
        results.append(_result(
            title=f"{name}{' (' + quantity + ')' if quantity else ''}",
            url=p.get("url") or (f"https://world.openfoodfacts.org/product/{pid}" if pid else "https://world.openfoodfacts.org"),
            source="openfoodfacts",
            institution="Open Food Facts",
            snippet=", ".join(snippet_parts),
            date="",
            rid=pid,
        ))
    return results


# ── ENVIRONMENT ───────────────────────────────────────────────────────────────

def search_carbon_intensity(query: str, limit: int = 5) -> list[dict]:
    """UK Carbon Intensity API — official National Grid ESO data. No key required.
    Returns current carbon intensity and generation fuel mix regardless of query."""
    intensity_data = _get("https://api.carbonintensity.org.uk/intensity")
    generation_data = _get("https://api.carbonintensity.org.uk/generation")
    results = []
    if intensity_data:
        entry = ((intensity_data.get("data") or [{}])[0])
        intensity = entry.get("intensity") or {}
        actual   = intensity.get("actual")
        forecast = intensity.get("forecast")
        index    = intensity.get("index", "")
        from_ts  = entry.get("from", "")[:10]
        snippet = (
            f"Actual: {actual} gCO₂/kWh · Forecast: {forecast} gCO₂/kWh · Index: {index}"
        ).strip(" ·")
        results.append(_result(
            title="UK Grid Carbon Intensity — current",
            url="https://carbonintensity.org.uk",
            source="carbon_intensity",
            institution="National Grid ESO (UK Government)",
            snippet=snippet,
            date=from_ts,
            rid="intensity-current",
        ))
    if generation_data:
        gen_entry = generation_data.get("data") or {}
        gen_mix = gen_entry.get("generationmix") or []
        fuels = ", ".join(
            f"{g['fuel']} {g['perc']:.1f}%" for g in gen_mix if g.get("perc", 0) > 1
        )
        from_ts = gen_entry.get("from", "")[:10]
        results.append(_result(
            title="UK Grid Generation Mix — current",
            url="https://carbonintensity.org.uk",
            source="carbon_intensity",
            institution="National Grid ESO (UK Government)",
            snippet=fuels,
            date=from_ts,
            rid="generation-current",
        ))
    return results[:limit]


# ── WEATHER ───────────────────────────────────────────────────────────────────

def search_nws(query: str, limit: int = 5) -> list[dict]:
    """US National Weather Service — active alerts and official forecasts. No key required."""
    url = "https://api.weather.gov/alerts/active?status=actual&message_type=alert"
    data = _get(url)
    if not data:
        return []
    features = data.get("features") or []
    query_lower = query.lower()
    query_words = [w for w in query_lower.split() if len(w) > 3]
    scored = []
    for f in features:
        props = f.get("properties") or {}
        event    = props.get("event", "") or ""
        headline = props.get("headline", "") or ""
        area     = props.get("areaDesc", "") or ""
        combined = f"{event} {headline} {area}".lower()
        score = sum(1 for w in query_words if w in combined)
        scored.append((score, f))
    scored.sort(key=lambda x: -x[0])
    results = []
    for _, f in scored[:limit]:
        props = f.get("properties") or {}
        event    = props.get("event", "")
        headline = props.get("headline", "")
        area     = props.get("areaDesc", "")
        effective = (props.get("effective") or "")[:10]
        fid  = props.get("id", "")
        url_link = "https://www.weather.gov"
        results.append(_result(
            title=f"{event} — {area}" if area else event,
            url=url_link,
            source="nws",
            institution="U.S. National Weather Service (NOAA)",
            snippet=headline,
            date=effective,
            rid=fid,
        ))
    return results


# ── NEWS ──────────────────────────────────────────────────────────────────────

def search_gdelt(query: str, limit: int = 5) -> list[dict]:
    """GDELT — global news event stream, 100+ languages indexed. No key required."""
    url = (
        "https://api.gdeltproject.org/api/v2/doc/doc?query="
        + urllib.parse.quote(query)
        + f"&mode=artlist&maxrecords={limit}&format=json&sourcelang=english"
    )
    data = _get(url)
    if not data:
        return []
    articles = (data.get("articles") or [])[:limit]
    results = []
    for a in articles:
        title = (a.get("title") or "").strip()
        url_ = a.get("url", "")
        domain = a.get("domain", "")
        raw_date = (a.get("seendate") or "")[:8]
        date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}" if len(raw_date) == 8 else ""
        results.append(_result(
            title=title or domain,
            url=url_,
            source="gdelt",
            institution=f"GDELT ({domain})",
            snippet=domain,
            date=date,
            rid=url_,
        ))
    return results


# ── PUBLIC HEALTH ──────────────────────────────────────────────────────────────

def search_who_gho(query: str, limit: int = 5) -> list[dict]:
    """WHO Global Health Observatory — official global health statistics. No key required."""
    url = (
        "https://ghoapi.azureedge.net/api/Indicator?$filter=contains(IndicatorName,"
        + f"'{urllib.parse.quote(query)}')"
        + f"&$top={limit}"
    )
    data = _get(url)
    if not data:
        return []
    indicators = (data.get("value") or [])[:limit]
    results = []
    for ind in indicators:
        code = ind.get("IndicatorCode", "")
        name = ind.get("IndicatorName", "")
        results.append(_result(
            title=name,
            url=f"https://www.who.int/data/gho/data/indicators/indicator-details/GHO/{code}",
            source="who_gho",
            institution="World Health Organization (WHO)",
            snippet=code,
            date="",
            rid=code,
        ))
    return results


# ── CLIMATE / WEATHER (global) ─────────────────────────────────────────────────

def search_open_meteo(query: str, limit: int = 5) -> list[dict]:
    """Open-Meteo — global weather and climate data via ECMWF. No key required.
    Geocodes the location in the query then returns current conditions + 3-day forecast."""
    _WEATHER_STOP = {"weather","forecast","climate","temperature","rain","snow","wind","humidity","today","now","current"}
    geo_term = " ".join(w for w in query.split() if w.lower() not in _WEATHER_STOP) or query
    geo_url = (
        "https://geocoding-api.open-meteo.com/v1/search?name="
        + urllib.parse.quote(geo_term)
        + "&count=1&language=en&format=json"
    )
    geo = _get(geo_url)
    if not geo or not geo.get("results"):
        return []
    loc = geo["results"][0]
    lat, lon = loc["latitude"], loc["longitude"]
    name = loc.get("name", query)
    country = loc.get("country", "")
    tz = loc.get("timezone", "UTC")
    wx_url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,wind_speed_10m"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
        f"&timezone={urllib.parse.quote(tz)}&forecast_days=3"
    )
    wx = _get(wx_url)
    if not wx:
        return []
    current = wx.get("current") or {}
    daily = wx.get("daily") or {}
    temp = current.get("temperature_2m", "")
    humid = current.get("relative_humidity_2m", "")
    wind = current.get("wind_speed_10m", "")
    days = list(zip(
        (daily.get("time") or [])[:3],
        (daily.get("temperature_2m_max") or [])[:3],
        (daily.get("temperature_2m_min") or [])[:3],
    ))
    forecast = " | ".join(f"{d}: {hi}/{lo}°C" for d, hi, lo in days)
    snippet = f"Current: {temp}°C, humidity {humid}%, wind {wind} km/h | Forecast: {forecast}"
    return [_result(
        title=f"{name}, {country} — weather",
        url="https://open-meteo.com",
        source="open_meteo",
        institution="Open-Meteo (ECMWF data)",
        snippet=snippet,
        date=(current.get("time") or "")[:10],
        rid=f"{lat},{lon}",
    )]


# ── PATENTS ───────────────────────────────────────────────────────────────────

def search_patentsview(query: str, limit: int = 5) -> list[dict]:
    """USPTO PatentsView — full US patent database. No key required."""
    import json as _json
    q = _json.dumps({"_text_any": {"patent_title": query, "patent_abstract": query}})
    f = _json.dumps(["patent_id", "patent_title", "patent_abstract", "patent_date"])
    o = _json.dumps({"per_page": limit, "sort": {"patent_date": "desc"}})
    url = (
        "https://search.patentsview.org/api/v1/patent?q="
        + urllib.parse.quote(q)
        + "&f=" + urllib.parse.quote(f)
        + "&o=" + urllib.parse.quote(o)
    )
    data = _get(url)
    if not data:
        return []
    patents = (data.get("patents") or [])[:limit]
    results = []
    for p in patents:
        pid = p.get("patent_id", "")
        title = p.get("patent_title", "")
        abstract = (p.get("patent_abstract") or "")[:300]
        date = (p.get("patent_date") or "")[:10]
        results.append(_result(
            title=title,
            url=f"https://patents.google.com/patent/US{pid}",
            source="patentsview",
            institution="USPTO PatentsView",
            snippet=abstract,
            date=date,
            rid=pid,
        ))
    return results


# ── MACROECONOMICS ────────────────────────────────────────────────────────────

def search_imf(query: str, limit: int = 5) -> list[dict]:
    """IMF DataMapper — 132 global macroeconomic indicators. No key required."""
    data = _get("https://www.imf.org/external/datamapper/api/v1/indicators")
    if not data:
        return []
    indicators = data.get("indicators") or {}
    q_terms = [t for t in query.lower().split() if len(t) > 2]
    def _matches(v: dict) -> bool:
        text = ((v.get("label") or "") + " " + (v.get("description") or "")).lower()
        return any(t in text for t in q_terms)
    matches = [(k, v) for k, v in indicators.items() if _matches(v)][:limit]
    results = []
    for code, meta in matches:
        label = meta.get("label", code)
        desc = (meta.get("description") or "")[:280]
        unit = meta.get("unit", "")
        results.append(_result(
            title=f"{label} ({unit})" if unit else label,
            url=f"https://www.imf.org/external/datamapper/{code}",
            source="imf",
            institution="International Monetary Fund (IMF)",
            snippet=desc,
            date="",
            rid=code,
        ))
    return results


# ── SOCIAL SCIENCE PREPRINTS ───────────────────────────────────────────────────

def search_osf(query: str, limit: int = 5) -> list[dict]:
    """OSF Preprints — open social science, psychology, medicine preprints. No key required."""
    url = (
        "https://api.osf.io/v2/preprints/?filter[title]="
        + urllib.parse.quote(query)
        + f"&page[size]={limit}&filter[is_published]=true"
    )
    data = _get(url, headers={"Accept": "application/vnd.api+json"})
    if not data:
        return []
    items = (data.get("data") or [])[:limit]
    results = []
    for item in items:
        attrs = item.get("attributes") or {}
        links = item.get("links") or {}
        title = attrs.get("title", "").strip()
        desc = (attrs.get("description") or "")[:280]
        doi = attrs.get("doi") or ""
        date = (attrs.get("date_published") or attrs.get("date_created") or "")[:10]
        url_ = links.get("html") or links.get("iri") or ""
        results.append(_result(
            title=title,
            url=url_,
            source="osf",
            institution="Open Science Framework (OSF)",
            snippet=desc or doi,
            date=date,
            rid=item.get("id", ""),
        ))
    return results


# ── SPORTS ───────────────────────────────────────────────────────────────────

def search_thesportsdb(query: str, limit: int = 5) -> list[dict]:
    """TheSportsDB — teams, players, leagues, and events. No key required (demo tier)."""
    results = []
    for kind, key, endpoint in [
        ("teams",   "teams",   f"https://www.thesportsdb.com/api/v1/json/3/searchteams.php?t={urllib.parse.quote(query)}"),
        ("players", "players", f"https://www.thesportsdb.com/api/v1/json/3/searchplayers.php?p={urllib.parse.quote(query)}"),
    ]:
        if len(results) >= limit:
            break
        data = _get(endpoint)
        if not data or not data.get(kind):
            continue
        for item in (data[kind] or [])[:limit - len(results)]:
            if kind == "teams":
                name = item.get("strTeam", "")
                sport = item.get("strSport", "")
                league = item.get("strLeague", "")
                desc = (item.get("strDescriptionEN") or "")[:280]
                url_ = f"https://www.thesportsdb.com/team/{item.get('idTeam','')}"
                snippet = f"{sport} · {league}" if sport else league
            else:
                name = item.get("strPlayer", "")
                sport = item.get("strSport", "")
                nation = item.get("strNationality", "")
                desc = (item.get("strDescriptionEN") or "")[:280]
                url_ = f"https://www.thesportsdb.com/player/{item.get('idPlayer','')}"
                snippet = f"{sport} · {nation}" if sport else nation
            results.append(_result(
                title=name,
                url=url_,
                source="thesportsdb",
                institution="TheSportsDB",
                snippet=snippet + (f" — {desc[:200]}" if desc else ""),
                date="",
                rid=item.get("idTeam") or item.get("idPlayer", ""),
            ))
    return results[:limit]


# ── FINANCE / FX ─────────────────────────────────────────────────────────────

def search_frankfurter(query: str, limit: int = 5) -> list[dict]:
    """Frankfurter — ECB official exchange rates. No key required."""
    # Determine base currency from query; default EUR
    q_upper = query.upper()
    known = {"USD","EUR","GBP","JPY","CHF","AUD","CAD","CNY","SEK","NOK","DKK","NZD","SGD","HKD","KRW","INR","BRL","MXN","ZAR","TRY"}
    base = next((tok for tok in q_upper.split() if tok in known), "EUR")
    url = f"https://api.frankfurter.app/latest?from={base}"
    data = _get(url)
    if not data or "rates" not in data:
        return []
    rates = data["rates"]
    date = data.get("date", "")
    results = []
    # Score currencies by query relevance (mentioned first, otherwise alphabetical)
    scored = sorted(rates.items(), key=lambda kv: (0 if kv[0] in q_upper else 1, kv[0]))
    for currency, rate in scored[:limit]:
        results.append(_result(
            title=f"1 {base} = {rate} {currency}",
            url="https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/",
            source="frankfurter",
            institution="European Central Bank (ECB) via Frankfurter",
            snippet=f"Base: {base} · As of {date}",
            date=date,
            rid=f"{base}/{currency}",
        ))
    return results


# ── Source registry ────────────────────────────────────────────────────────────

SOURCES: dict[str, dict] = {
    # Academic
    "openalex":         {"name": "OpenAlex",                "domain": ["academic", "science", "humanities"], "key_required": False},
    "core":             {"name": "CORE",                    "domain": ["academic", "science"],             "key_required": False},
    "doaj":             {"name": "DOAJ",                    "domain": ["academic", "open_access"],           "key_required": False},
    "europepmc":        {"name": "Europe PMC",              "domain": ["biology", "medicine", "health"],     "key_required": False},
    "semantic_scholar": {"name": "Semantic Scholar",        "domain": ["academic", "cs", "science"],         "key_required": True},
    "crossref":         {"name": "Crossref",                "domain": ["academic", "general"],               "key_required": False},
    "pubmed":           {"name": "PubMed",                  "domain": ["biology", "medicine"],               "key_required": False},
    "arxiv":            {"name": "arXiv",                   "domain": ["science", "cs", "math", "physics"],  "key_required": False},
    # Data / Science
    "zenodo":           {"name": "Zenodo",                  "domain": ["science", "data", "general"],        "key_required": False},
    "datacite":         {"name": "DataCite",                "domain": ["science", "data"],                   "key_required": False},
    "wikidata":         {"name": "Wikidata",                "domain": ["general", "reference"],              "key_required": False},
    "pubchem":          {"name": "PubChem",                 "domain": ["chemistry", "science"],              "key_required": False},
    "usgs":             {"name": "USGS Publications",       "domain": ["geology", "earth_science"],          "key_required": False},
    "nasa":             {"name": "NASA",                    "domain": ["space", "science"],                  "key_required": False},
    # Museums
    "met":              {"name": "Met Museum",              "domain": ["art", "culture", "history"],         "key_required": False},
    "cleveland":        {"name": "Cleveland Museum of Art", "domain": ["art", "culture"],                    "key_required": False},
    "vam":              {"name": "V&A Museum",              "domain": ["art", "design", "culture"],          "key_required": False},
    "rijksmuseum":      {"name": "Rijksmuseum",             "domain": ["art", "history"],                    "key_required": True},
    # Libraries & Archives
    "loc":              {"name": "Library of Congress",     "domain": ["humanities", "history", "general"],  "key_required": False},
    "openlibrary":      {"name": "Open Library",            "domain": ["books", "humanities"],               "key_required": False},
    "chronicling_america": {"name": "Chronicling America", "domain": ["history", "journalism"],             "key_required": False},
    "internet_archive": {"name": "Internet Archive",        "domain": ["general", "books", "media"],         "key_required": False},
    "dpla":             {"name": "DPLA",                    "domain": ["humanities", "history", "general"],  "key_required": True},
    # Heritage
    "smithsonian":      {"name": "Smithsonian",             "domain": ["art", "history", "science"],         "key_required": True},
    "europeana":        {"name": "Europeana",               "domain": ["art", "culture", "history"],         "key_required": True},
    # International
    "gallica":          {"name": "Gallica (BnF)",           "domain": ["humanities", "history", "france"],   "key_required": False},
    "hal":              {"name": "HAL Open Access",         "domain": ["academic", "science", "france"],     "key_required": False},
    "scielo":           {"name": "SciELO",                  "domain": ["science", "latin_america", "iberia"],"key_required": False},
    "ndl":              {"name": "National Diet Library",   "domain": ["general", "japan", "asia"],          "key_required": False},
    # Music
    "musicbrainz":      {"name": "MusicBrainz",             "domain": ["music", "art", "culture"],           "key_required": False},
    # Philosophy & humanities
    "sep":              {"name": "Stanford Encyclopedia of Philosophy", "domain": ["philosophy", "humanities"], "key_required": False},
    # Literature — public domain
    "gutenberg":        {"name": "Project Gutenberg",       "domain": ["literature", "books", "humanities"], "key_required": False},
    # Natural history
    "bhl":              {"name": "Biodiversity Heritage Library", "domain": ["biology", "ecology", "natural_history"], "key_required": True},
    # Law
    "courtlistener":    {"name": "CourtListener",           "domain": ["law", "legal"],                      "key_required": False},
    # Broad academic open access
    "base":             {"name": "BASE (Bielefeld)",         "domain": ["academic", "general", "open_access"],"key_required": False},
    # Computer science
    "dblp":             {"name": "DBLP",                    "domain": ["computer_science", "academic"],      "key_required": False},
    # Drug / medical safety
    "openfda":          {"name": "OpenFDA",                 "domain": ["medicine", "drug", "safety"],        "key_required": False},
    # Species / ecology
    "eol":              {"name": "Encyclopedia of Life",    "domain": ["biology", "ecology", "species"],     "key_required": False},
    "gbif":             {"name": "GBIF",                    "domain": ["biology", "ecology", "biodiversity"],"key_required": False},
    "inaturalist":      {"name": "iNaturalist",             "domain": ["biology", "ecology", "species"],     "key_required": False},
    # Geography
    "nominatim":        {"name": "OpenStreetMap Nominatim", "domain": ["geography", "places"],               "key_required": False},
    # European open research
    "openaire":         {"name": "OpenAIRE",                "domain": ["academic", "europe", "open_access"], "key_required": False},
    # Government open data
    "federal_register": {"name": "U.S. Federal Register",  "domain": ["law", "government", "us"],           "key_required": False},
    "datagov":          {"name": "data.gov",                "domain": ["government", "data", "us"],          "key_required": False},
    "uk_legislation":   {"name": "legislation.gov.uk",      "domain": ["law", "government", "uk"],           "key_required": False},
    "eu_data":          {"name": "data.europa.eu",          "domain": ["government", "data", "europe"],      "key_required": False},
    # Clinical trade press
    "psychiatric_times": {"name": "Psychiatric Times",      "domain": ["psychiatry", "mental_health", "medicine"], "key_required": False},
    # High-energy physics
    "inspirehep":       {"name": "INSPIRE-HEP",             "domain": ["physics", "high_energy_physics", "science"], "key_required": False},
    # Economics / macroeconomics
    "worldbank":        {"name": "World Bank Open Data",    "domain": ["economics", "finance", "government"],  "key_required": False},
    # Food & nutrition
    "openfoodfacts":    {"name": "Open Food Facts",         "domain": ["food", "nutrition", "science"],        "key_required": False},
    # Environment / energy
    "carbon_intensity": {"name": "UK Carbon Intensity",     "domain": ["environment", "energy", "climate"],    "key_required": False},
    # Weather
    "nws":              {"name": "National Weather Service", "domain": ["weather", "government", "science"],    "key_required": False},
    # News
    "gdelt":            {"name": "GDELT",                   "domain": ["news", "current_events"],               "key_required": False},
    # Public health
    "who_gho":          {"name": "WHO Global Health Observatory", "domain": ["public_health", "medicine"],      "key_required": False},
    # Global weather/climate
    "open_meteo":       {"name": "Open-Meteo",              "domain": ["climate", "weather"],                   "key_required": False},
    # Patents
    "patentsview":      {"name": "USPTO PatentsView",       "domain": ["patents", "technology", "science"],     "key_required": False},
    # Macroeconomics
    "imf":              {"name": "IMF DataMapper",          "domain": ["macroeconomics", "economics"],          "key_required": False},
    # Social science preprints
    "osf":              {"name": "Open Science Framework",  "domain": ["social_science", "psychology", "medicine"], "key_required": False},
    # Sports
    "thesportsdb":      {"name": "TheSportsDB",             "domain": ["sports"],                               "key_required": False},
    # Finance / FX
    "frankfurter":      {"name": "ECB via Frankfurter",     "domain": ["finance", "economics"],                 "key_required": False},
    # Opt-in only — general reference, not suitable for academic citation
    "wikipedia":        {"name": "Wikipedia",               "domain": ["general", "reference"],              "fn_name": "search_wikipedia",        "key_required": False, "opt_in": True},
}

# ── DB-backed source registry ─────────────────────────────────────────────────
# jeles_sources table is canonical. SOURCES above is fallback only.
# Dispatch resolves fn_name strings via getattr — no function pointers needed.

import concurrent.futures as _cf
import sys as _sys
import time as _time

_REGISTRY_CACHE: dict[str, dict] = {}
_REGISTRY_LOADED_AT: float = 0.0
_REGISTRY_TTL: float = 300.0  # 5-minute cache

# Shared executor for concurrent source dispatch — avoids spawning N×12 threads
# when the MCP server calls search() concurrently from multiple requests.
_SEARCH_EXECUTOR = _cf.ThreadPoolExecutor(max_workers=16, thread_name_prefix="jeles-src")

_ROUTES_CACHE: list[tuple[list[str], list[str]]] = []
_ROUTES_LOADED_AT: float = 0.0


def _load_registry() -> dict[str, dict]:
    """Load {source_id: {name, fn_name, key_required, opt_in}} from Postgres.
    Falls back to SOURCES if DB unavailable."""
    global _REGISTRY_CACHE, _REGISTRY_LOADED_AT
    now = _time.monotonic()
    if _REGISTRY_CACHE and now - _REGISTRY_LOADED_AT < _REGISTRY_TTL:
        return _REGISTRY_CACHE
    try:
        from core.pg_bridge import PgBridge
        bridge = PgBridge()
        cur = bridge.conn.cursor()
        cur.execute("""
            SELECT id, name, fn_name, key_required, opt_in, enabled
            FROM   jeles_sources
            WHERE  fn_name IS NOT NULL
        """)
        rows = cur.fetchall()
        cur.close()
        bridge.conn.close()
        if rows:
            _REGISTRY_CACHE = {
                row[0]: {
                    "name":         row[1],
                    "fn_name":      row[2],
                    "key_required": row[3],
                    "opt_in":       row[4],
                    "enabled":      row[5],
                }
                for row in rows
            }
            _REGISTRY_LOADED_AT = now
            return _REGISTRY_CACHE
    except Exception as e:
        log.warning("Registry DB load failed, using Python fallback: %s", e)
    # Fallback: convert SOURCES fn pointers to fn_name strings
    fallback = {}
    for sid, cfg in SOURCES.items():
        fallback[sid] = {
            "name":         cfg.get("name", sid),
            "fn_name":      cfg.get("fn_name") or (cfg.get("fn") and cfg["fn"].__name__) or f"search_{sid}",
            "key_required": cfg.get("key_required", False),
            "opt_in":       cfg.get("opt_in", False),
            "enabled":      True,
        }
    return fallback


def _load_routes() -> list[tuple[list[str], list[str]]]:
    """Load keyword routes from jeles_domain_routes. Falls back to _DOMAIN_ROUTES."""
    global _ROUTES_CACHE, _ROUTES_LOADED_AT
    now = _time.monotonic()
    if _ROUTES_CACHE and now - _ROUTES_LOADED_AT < _REGISTRY_TTL:
        return _ROUTES_CACHE
    try:
        from core.pg_bridge import PgBridge
        bridge = PgBridge()
        cur = bridge.conn.cursor()
        cur.execute("""
            SELECT keywords, source_ids
            FROM   jeles_domain_routes
            WHERE  keywords IS NOT NULL AND source_ids IS NOT NULL
            ORDER BY domain
        """)
        rows = cur.fetchall()
        cur.close()
        bridge.conn.close()
        if rows:
            _ROUTES_CACHE = [(list(row[0]), list(row[1])) for row in rows if row[0] and row[1]]
            _ROUTES_LOADED_AT = now
            return _ROUTES_CACHE
    except Exception as e:
        log.warning("Routes DB load failed, using Python fallback: %s", e)
    return _DOMAIN_ROUTES


def _resolve_fn(fn_name: str):
    """Resolve a search function by name from this module."""
    return getattr(_sys.modules[__name__], fn_name, None)

# ── Domain routing ────────────────────────────────────────────────────────────
# Each entry: (keyword_list, source_ids). First match wins.

# High-priority history queries — checked before broad government/policy keywords.
_HISTORY_QUERY_OVERRIDES: list[tuple[list[str], list[str]]] = [
    (["french revolution", "revolution of 1789", "bastille", "reign of terror",
      "napoleonic wars", "louis xvi"],
     ["gallica", "loc", "internet_archive", "openlibrary"]),
]

_DOMAIN_ROUTES: list[tuple[list[str], list[str]]] = [
    *_HISTORY_QUERY_OVERRIDES,
    (["law", "legal", "court", "case law", "statute", "legislation", "judicial",
      "ruling", "verdict", "judge", "attorney", "plaintiff", "defendant",
      "precedent", "supreme court", "amendment", "regulation", "act of congress",
      "bill passed", "federal law", "constitution"],
     ["courtlistener", "federal_register", "openalex"]),

    (["government", "policy", "federal", "parliament", "senate", "congress",
      "ministry", "department of", "executive order", "public sector",
      "cabinet", "prime minister", "president policy", "uk law", "eu law",
      "european union regulation", "government data", "open data"],
     ["federal_register", "datagov", "uk_legislation", "eu_data"]),

    (["species", "animal", "bird", "fish", "insect", "plant", "mammal",
      "reptile", "amphibian", "fungus", "microbe", "bacteria", "wildlife",
      "observed in the wild", "sighting", "habitat", "endangered", "iucn"],
     ["inaturalist", "gbif", "eol", "bhl"]),

    (["geography", "country", "city", "capital", "river", "mountain", "continent",
      "population density", "location of", "where is", "coordinates", "region",
      "territory", "border between", "nation", "province", "county", "lake",
      "ocean", "sea", "bay", "peninsula", "island"],
     ["nominatim", "wikidata", "openalex"]),

    (["music", "song", "album", "band", "artist", "musician", "rapper", "hip hop",
      "hip-hop", "jazz", "blues", "rock", "pop", "genre", "record", "track",
      "lyrics", "singer", "producer", "discography", "discogs", "recording"],
     ["musicbrainz", "openlibrary"]),

    (["ship", "vessel", "hull", "marine", "nautical", "barnacle", "antifouling",
      "corrosion", "rust", "copper", "boat", "submarine", "naval", "dock",
      "buoyancy", "ballast", "keel"],
     ["pubchem", "crossref", "openalex"]),

    (["paint", "artwork", "sculpture", "portrait", "drawing", "exhibition",
      "canvas", "fresco", "engraving", "watercolor", "print", "photograph",
      "illustration", "tapestry", "mosaic", "rembrandt", "vermeer", "picasso",
      "van gogh", "monet", "museum collection", "art history"],
     ["met", "cleveland", "vam", "wikidata", "europeana"]),

    (["psychiatry", "psychiatric", "mental health", "mental illness", "depression",
      "anxiety", "bipolar", "schizophrenia", "psychosis", "ptsd", "adhd",
      "autism", "ocd", "personality disorder", "substance use", "addiction",
      "suicide", "self-harm", "antidepressant", "antipsychotic", "ssri", "snri",
      "benzodiazepine", "therapy", "psychotherapy", "cbt", "dbt", "dsm",
      "psychiatric medication", "mental disorder"],
     ["psychiatric_times", "pubmed", "europepmc"]),

    (["disease", "drug", "medicine", "treatment", "syndrome", "virus", "bacteria",
      "health", "clinical", "therapy", "gene", "protein", "vaccine", "cancer",
      "surgery", "diagnosis", "pharmacology"],
     ["pubmed", "europepmc", "pubchem"]),

    (["chemical", "compound", "molecule", "element", "reaction", "formula", "acid",
      "polymer", "catalyst", "synthesis", "isotope"],
     ["pubchem", "crossref", "arxiv"]),

    (["physics", "quantum", "algorithm", "machine learning", "neural network",
      "mathematics", "theorem", "computer science", "programming", "deep learning",
      "artificial intelligence", "ai", "cryptography", "compiler"],
     ["arxiv", "semantic_scholar", "openalex"]),

    (["space", "nasa", "planet", "star", "galaxy", "asteroid", "orbit", "telescope",
      "astronomy", "cosmos", "lunar", "solar system", "comet", "exoplanet"],
     ["nasa", "arxiv", "openalex"]),

    (["geology", "earthquake", "volcano", "mineral", "hydrology", "fossil",
      "sediment", "tectonic", "seismic", "groundwater"],
     ["usgs", "openalex", "zenodo"]),

    (["history", "historical", "century", "war", "revolution", "colonial", "ancient",
      "newspaper", "archive", "president", "congress", "empire", "dynasty",
      "civil war", "world war", "medieval", "renaissance"],
     ["loc", "chronicling_america", "internet_archive", "openlibrary"]),

    (["philosophy", "ethics", "epistemology", "metaphysics", "kant", "aristotle",
      "plato", "hegel", "nietzsche", "descartes", "hume", "wittgenstein", "locke",
      "moral", "ontology", "phenomenology", "consciousness", "free will", "logic",
      "categorical imperative", "utilitarianism", "existentialism"],
     ["sep", "openalex", "crossref"]),

    (["natural history", "species", "taxonomy", "ecology", "evolution", "darwin",
      "botany", "zoology", "entomology", "ornithology", "flora", "fauna",
      "biodiversity", "specimen", "genus", "phylum", "habitat"],
     ["bhl", "openalex", "crossref"]),

    (["book", "novel", "author", "literature", "poem", "fiction", "publish", "writer",
      "text", "manuscript", "edition", "play", "essay", "anthology"],
     ["gutenberg", "openlibrary", "loc"]),

    (["france", "french", "paris", "napoleon", "versailles", "de gaulle",
      "alsace", "bretagne"],
     ["gallica", "hal", "europeana"]),

    (["japan", "japanese", "tokyo", "kyoto", "manga", "samurai", "meiji"],
     ["ndl", "openalex"]),
]

_DEFAULT_SOURCES = ["base", "openalex", "crossref", "wikidata"]
_MAX_ROUTE_SOURCES = 6


def _route_override(query: str) -> list[str] | None:
    q = query.lower()
    for keywords, sources in _HISTORY_QUERY_OVERRIDES:
        if any(kw in q for kw in keywords):
            return sources[:_MAX_ROUTE_SOURCES]
    return None


def route_sources(query: str) -> list[str]:
    """Select sources for a query based on domain keyword matching.
    DB-first: reads routes from jeles_domain_routes. Falls back to _DOMAIN_ROUTES.
    Fast — no HTTP, no LLM."""
    override = _route_override(query)
    if override:
        return override
    q = query.lower()
    for keywords, sources in _load_routes():
        if any(kw in q for kw in keywords):
            return sources[:_MAX_ROUTE_SOURCES]
    return _DEFAULT_SOURCES


# ── Semantic routing ──────────────────────────────────────────────────────────
# nomic-embed-text (local Ollama) embeds the query intent; cosine sim against
# pre-computed domain centroids picks the source group. Handles trivia framing
# that keyword matching misses.

_OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
_CENTROIDS_PATH = willow_home() / "jeles_centroids.json"

# Representative sentences per domain — averaged into a centroid embedding.
_DOMAIN_SEEDS: dict[str, list[str]] = {
    "music": [
        "What albums did this band release?",
        "Who are the members of this music group?",
        "What genre of music does this artist play?",
        "Name the songs on this album.",
        "When did this musician release their debut record?",
    ],
    "art": [
        "Who painted this famous artwork?",
        "What museum holds this sculpture?",
        "Describe the style of this Renaissance painting.",
        "When was this portrait created?",
        "What materials were used in this mosaic?",
    ],
    "medicine": [
        "What are the symptoms of this disease?",
        "How does this drug treat the condition?",
        "What vaccine prevents this virus?",
        "What is the clinical trial outcome for this therapy?",
        "How is this syndrome diagnosed?",
    ],
    "chemistry": [
        "What compounds are used in this industrial coating process?",
        "What is the molecular formula of this substance?",
        "How does this catalyst work in organic synthesis?",
        "What chemicals prevent biofouling on submerged surfaces?",
        "What polymer compound is used in this protective paint?",
    ],
    "physics": [
        "How does quantum entanglement work?",
        "What is the theory of general relativity?",
        "How does nuclear fission generate energy?",
        "What is the Higgs boson?",
        "How does superconductivity occur at low temperatures?",
    ],
    "space": [
        "What is the International Space Station and who operates it?",
        "What NASA missions have explored Mars?",
        "What is the distance to this planet?",
        "How was this galaxy discovered?",
        "What spacecraft are currently orbiting Earth?",
        "What rocket launched this satellite into orbit?",
        "What is the Hubble Space Telescope?",
        "When did humans first land on the Moon?",
        "What is the orbital period of this asteroid?",
        "What are the atmospheric conditions on this exoplanet?",
    ],
    "geology": [
        "What caused this earthquake?",
        "What type of rock is found in this formation?",
        "How deep is this groundwater aquifer?",
        "What minerals are found in this sediment layer?",
        "When did this volcano last erupt?",
    ],
    "history": [
        "What caused this war?",
        "Who was the president during this era?",
        "What happened during this revolution?",
        "When did this empire fall?",
        "What was the significance of this battle?",
    ],
    "literature": [
        "Who wrote this novel?",
        "What is the plot of this book?",
        "When was this poem published?",
        "What themes appear in this play?",
        "Who is the author of this manuscript?",
    ],
    "marine": [
        "What compounds prevent corrosion on ship hulls?",
        "How do antifouling coatings work on vessels?",
        "What causes barnacle growth on boat surfaces?",
        "How is hull material resistant to saltwater degradation?",
        "What chemicals are in marine antifouling paint?",
    ],
    "france": [
        "What happened during the French Revolution?",
        "Who was Napoleon Bonaparte?",
        "What is the history of Paris?",
        "What did de Gaulle accomplish as French leader?",
        "Describe French colonial history and overseas territories.",
    ],
    "japan": [
        "What is the history of the Meiji Restoration?",
        "Who were the samurai in Japanese history?",
        "What manga and anime series originated in Japan?",
        "What is traditional Japanese culture and customs?",
        "When was Tokyo established as the capital?",
    ],
    "law": [
        "What is the legal precedent for this court ruling?",
        "What did the Supreme Court decide in this landmark case?",
        "Is this action protected or prohibited under the Constitution?",
        "What legislation governs this regulatory area?",
        "What is the judicial standard for this type of civil case?",
    ],
    "government": [
        "What does the federal government regulate in this area?",
        "What executive orders govern this policy?",
        "What does UK parliament say about this legislation?",
        "What EU regulation applies to this industry?",
        "Where can I find official government data on this topic?",
    ],
    "species": [
        "What species of bird is native to this region?",
        "How many observations of this animal exist worldwide?",
        "What is the conservation status of this mammal?",
        "What does this insect eat and where does it live?",
        "What genus does this plant belong to?",
    ],
    "geography": [
        "Where is this city located in the world?",
        "What country does this region belong to?",
        "What is the capital city of this nation?",
        "Where does this major river flow?",
        "What are the geographic borders of this territory?",
    ],
    "philosophy": [
        "What did Kant mean by the categorical imperative?",
        "What is the difference between empiricism and rationalism?",
        "How does Aristotle define virtue ethics?",
        "What is Descartes' argument for the existence of the mind?",
        "What did Wittgenstein mean by language games?",
    ],
    "natural_history": [
        "What is the taxonomy of this species?",
        "How did Darwin explain natural selection?",
        "What is the ecological role of this organism?",
        "Describe the habitat and range of this bird species.",
        "What genus does this plant belong to?",
    ],
    "literature_texts": [
        "Where can I read the full text of this public domain novel?",
        "What books did this nineteenth century author write?",
        "Find the original text of this classic poem.",
        "What are the works of Shakespeare available in full text?",
        "Which Dickens novels are available as free ebooks?",
    ],
    "high_energy_physics": [
        "What is the Standard Model of particle physics?",
        "How does the Higgs boson give particles mass?",
        "What are the results of the LHC experiment on dark matter?",
        "What is supersymmetry in theoretical physics?",
        "What papers describe the discovery of the top quark?",
    ],
    "economics": [
        "What is the current inflation rate?",
        "How does GDP growth compare across countries?",
        "What is the unemployment rate in this country?",
        "How have interest rates changed over the past decade?",
        "What is the trade balance for this economy?",
    ],
    "food": [
        "What are the nutritional facts for this food product?",
        "How many calories are in this product?",
        "What ingredients are in this packaged food?",
        "What are the allergens in this product?",
        "What is the nutritional profile of this food?",
    ],
    "environment": [
        "What is the current carbon intensity of the UK electricity grid?",
        "What percentage of UK electricity comes from renewables?",
        "What is the carbon footprint of electricity generation?",
        "How clean is the UK power grid right now?",
        "What is the generation fuel mix for UK electricity?",
    ],
    "weather": [
        "What are the active weather warnings in the US?",
        "Is there a tornado warning in effect?",
        "What hurricane advisories are currently active?",
        "What severe weather alerts are issued today?",
        "Are there any flood warnings currently active?",
    ],
    "news": [
        "What is happening in the news today?",
        "What are the latest headlines about this topic?",
        "What did the media report about this event?",
        "What are the current news stories about climate change?",
        "What is the latest news from this country?",
    ],
    "current_events": [
        "What is happening in the world right now?",
        "What were the major events this week?",
        "What is the current political situation in this country?",
        "What happened recently with this conflict or election?",
        "What are the breaking news stories today?",
    ],
    "public_health": [
        "What is the global life expectancy rate?",
        "How many people die from malaria each year?",
        "What is the WHO's data on childhood vaccination rates?",
        "What are the leading causes of death globally?",
        "What does the WHO say about this disease?",
    ],
    "climate": [
        "What is the global average temperature anomaly?",
        "How hot will it be in Paris next week?",
        "What is the current weather in Tokyo?",
        "How does this country's climate compare to global averages?",
        "What are the temperature trends for this region?",
    ],
    "patents": [
        "Is there a patent for this invention?",
        "Who holds the patent on this technology?",
        "What patents exist for electric vehicle batteries?",
        "When was this technology first patented?",
        "What companies have patents in this field?",
    ],
    "macroeconomics": [
        "What is the GDP growth rate for this country?",
        "What does the IMF forecast for inflation?",
        "What is the current account balance for the eurozone?",
        "How does the IMF measure purchasing power parity?",
        "What are the IMF's economic projections for next year?",
    ],
    "social_science": [
        "What does recent research say about social media and mental health?",
        "Are there preprints on this psychological phenomenon?",
        "What do open access studies show about this behavioral pattern?",
        "What is the replication status of this social science finding?",
        "What recent preprints exist on voting behavior or political psychology?",
    ],
    "sports": [
        "What is the history of Manchester United?",
        "How many World Cup titles has Brazil won?",
        "Who are the top players in the NBA?",
        "What league does this team play in?",
        "What are the statistics for this athlete?",
    ],
    "finance": [
        "What is the current EUR to USD exchange rate?",
        "How many dollars is one pound sterling?",
        "What is the exchange rate between yen and euro?",
        "What is the current value of the Swiss franc?",
        "What are today's foreign exchange rates?",
    ],
}

# Domain → source IDs (mirrors _DOMAIN_ROUTES structure)
_DOMAIN_SOURCES: dict[str, list[str]] = {
    "music":      ["musicbrainz", "openlibrary"],
    "art":        ["met", "cleveland", "vam", "wikidata", "europeana"],
    "medicine":   ["pubmed", "europepmc", "pubchem"],
    "psychiatry": ["psychiatric_times", "pubmed", "europepmc"],
    "chemistry":  ["pubchem", "crossref", "arxiv"],
    "physics":    ["arxiv", "semantic_scholar", "openalex"],
    "space":      ["nasa", "arxiv", "openalex"],
    "geology":    ["usgs", "openalex", "zenodo"],
    "history":    ["loc", "chronicling_america", "internet_archive", "openlibrary", "gallica"],
    "literature": ["openlibrary", "loc", "internet_archive"],
    "marine":          ["pubchem", "crossref", "openalex"],
    "france":          ["gallica", "hal", "europeana"],
    "japan":           ["ndl", "openalex"],
    "philosophy":       ["sep", "openalex", "crossref"],
    "natural_history":  ["bhl", "openalex", "crossref"],
    "literature_texts": ["gutenberg", "openlibrary", "loc"],
    "law":              ["courtlistener", "federal_register", "openalex"],
    "government":          ["federal_register", "datagov", "uk_legislation", "eu_data", "nws"],
    "species":             ["inaturalist", "gbif", "eol", "bhl"],
    "geography":           ["nominatim", "wikidata", "openalex"],
    "high_energy_physics": ["inspirehep", "arxiv", "openalex"],
    "economics":           ["worldbank", "federal_register", "datagov", "openalex"],
    "food":                ["openfoodfacts", "wikidata"],
    "environment":         ["carbon_intensity", "usgs", "openalex"],
    "weather":             ["nws", "open_meteo", "wikidata"],
    "news":                ["gdelt"],
    "current_events":      ["gdelt"],
    "public_health":       ["who_gho", "pubmed", "europepmc"],
    "climate":             ["open_meteo", "carbon_intensity", "usgs", "openalex"],
    "patents":             ["patentsview"],
    "macroeconomics":      ["imf", "worldbank"],
    "social_science":      ["osf", "openalex", "crossref"],
    "sports":              ["thesportsdb"],
    "finance":             ["frankfurter", "worldbank"],
}

_SEMANTIC_THRESHOLD = 0.30  # min cosine similarity to trust a domain match
_PERSPECTIVE_FLOOR  = 0.26  # min relevance for a *secondary* perspective (below the primary)
_PERSPECTIVE_LAMBDA = 0.5   # MMR trade-off: relevance vs. diversity when picking perspectives


def _get_embedding(text: str) -> list[float]:
    """Call Ollama nomic-embed-text. Returns empty list on failure."""
    try:
        body = json.dumps({"model": "nomic-embed-text", "prompt": text}).encode()
        req = urllib.request.Request(
            _OLLAMA_EMBED_URL,
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r).get("embedding", [])
    except Exception:
        return []


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    return dot / (na * nb + 1e-9)


def _avg_vectors(vecs: list[list[float]]) -> list[float]:
    if not vecs:
        return []
    n = len(vecs)
    return [sum(v[i] for v in vecs) / n for i in range(len(vecs[0]))]


def build_centroids(force: bool = False) -> dict[str, list[float]]:
    """Compute and cache domain centroid embeddings.
    Calls Ollama nomic-embed-text for each seed sentence. Takes ~30-60s on first run.
    Writes to ~/.willow/jeles_centroids.json AND to jeles_domain_routes in Postgres."""
    if not force and _CENTROIDS_PATH.exists():
        try:
            return json.loads(_CENTROIDS_PATH.read_text())
        except Exception:
            pass

    centroids: dict[str, list[float]] = {}
    # Use DB seeds if available, fall back to static _DOMAIN_SEEDS
    domain_seeds = _load_db_seeds() or _DOMAIN_SEEDS
    for domain, seeds in domain_seeds.items():
        vecs = [v for s in seeds if (v := _get_embedding(s))]
        if vecs:
            centroids[domain] = _avg_vectors(vecs)

    if centroids:
        _CENTROIDS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CENTROIDS_PATH.write_text(json.dumps(centroids))
        _write_centroids_to_pg(centroids)

    return centroids


def _load_db_seeds() -> dict[str, list[str]] | None:
    """Load seed sentences from jeles_domain_routes in Postgres. Returns None if unavailable."""
    try:
        from core.pg_bridge import PgBridge
        bridge = PgBridge()
        cur = bridge.conn.cursor()
        cur.execute("SELECT domain, seed_sentences FROM jeles_domain_routes WHERE seed_sentences != '{}'")
        rows = cur.fetchall()
        cur.close()
        bridge.conn.close()
        if rows:
            return {row[0]: list(row[1]) for row in rows if row[1]}
    except Exception:
        pass
    return None


def _write_centroids_to_pg(centroids: dict[str, list[float]]) -> None:
    """Write computed centroids into jeles_domain_routes.centroid (pgvector)."""
    try:
        from core.pg_bridge import PgBridge
        bridge = PgBridge()
        cur = bridge.conn.cursor()
        for domain, vec in centroids.items():
            vec_str = "[" + ",".join(str(x) for x in vec) + "]"
            cur.execute("""
                UPDATE jeles_domain_routes
                SET    centroid   = %s::vector,
                       updated_at = now()
                WHERE  domain = %s
            """, (vec_str, domain))
        bridge.conn.commit()
        cur.close()
        bridge.conn.close()
    except Exception:
        pass


def _load_centroids() -> dict[str, list[float]]:
    """Load centroids from cache, building if missing."""
    if _CENTROIDS_PATH.exists():
        try:
            return json.loads(_CENTROIDS_PATH.read_text())
        except Exception:
            pass
    return build_centroids()


def _route_via_pg(q_vec: list[float]) -> list[str] | None:
    """ANN query against jeles_domain_routes.centroid in Postgres.
    Returns merged source_ids for the top-3 domains within 0.08 of the best score."""
    try:
        from core.pg_bridge import PgBridge
        bridge = PgBridge()
        cur = bridge.conn.cursor()
        vec_str = "[" + ",".join(str(x) for x in q_vec) + "]"
        cur.execute("""
            SELECT domain, source_ids,
                   1 - (centroid <=> %s::vector) AS similarity
            FROM   jeles_domain_routes
            WHERE  centroid IS NOT NULL
            ORDER BY centroid <=> %s::vector
            LIMIT  5
        """, (vec_str, vec_str))
        rows = cur.fetchall()
        cur.close()
        bridge.conn.close()
        if not rows or rows[0][2] < _SEMANTIC_THRESHOLD:
            return None
        best_score = rows[0][2]
        in_window = [
            (domain, source_ids, score) for domain, source_ids, score in rows
            if score >= _SEMANTIC_THRESHOLD and best_score - score <= 0.08
        ]
        # Subject-matter domains before regional/language domains
        in_window.sort(key=lambda r: r[2], reverse=True)
        seen: set[str] = set()
        merged: list[str] = []
        for domain, source_ids, score in in_window:
            for sid in (source_ids or []):
                if sid not in seen:
                    seen.add(sid)
                    merged.append(sid)
            if len(merged) >= _MAX_ROUTE_SOURCES:
                break
        return merged[:_MAX_ROUTE_SOURCES] if merged else None
    except Exception:
        pass
    return None


def route_sources_semantic(query: str) -> list[str]:
    """Semantic source routing via embedding similarity.
    Primary: ANN query against jeles_domain_routes in Postgres (pgvector).
    Fallback: Python cosine loop against cached centroids JSON.
    Final fallback: keyword routing."""
    override = _route_override(query)
    if override:
        return override
    q_vec = _get_embedding(query)
    if not q_vec:
        return route_sources(query)

    # Try DB-backed ANN first
    pg_result = _route_via_pg(q_vec)
    if pg_result:
        return pg_result

    # Python cosine fallback (uses ~/.willow/jeles_centroids.json)
    centroids = _load_centroids()
    if centroids:
        scores = sorted(
            [(d, _cosine(q_vec, v)) for d, v in centroids.items()],
            key=lambda x: x[1], reverse=True,
        )
        if scores and scores[0][1] >= _SEMANTIC_THRESHOLD:
            best_score = scores[0][1]
            in_window = [
                (d, s) for d, s in scores
                if s >= _SEMANTIC_THRESHOLD and best_score - s <= 0.08
            ]
            in_window.sort(key=lambda x: x[1], reverse=True)
            seen: set[str] = set()
            merged: list[str] = []
            for domain, score in in_window:
                for sid in _DOMAIN_SOURCES.get(domain, []):
                    if sid not in seen:
                        seen.add(sid)
                        merged.append(sid)
                if len(merged) >= _MAX_ROUTE_SOURCES:
                    break
            if merged:
                return merged[:_MAX_ROUTE_SOURCES]

    return _DEFAULT_SOURCES


def route_perspectives_semantic(query: str, k: int = 3) -> list[tuple[str, list[str]]]:
    """Route a query to up to `k` *deliberately diverse* domain perspectives.

    Unlike route_sources_semantic (which flattens the nearest-neighbour cluster into
    one source list), this picks domains that are each relevant to the query but far
    apart from one another in centroid space — so a query lands on, e.g., physics AND
    philosophy rather than physics AND high-energy-physics. Selection is Maximal
    Marginal Relevance: start from the most relevant domain, then repeatedly add the
    candidate that maximises lambda*relevance - (1-lambda)*max_similarity_to_picked.

    Returns a list of (domain, source_ids) groups, grouping preserved so the caller
    can retrieve and synthesise per perspective. Falls back to a single ("general",
    route_sources_semantic(query)) group when embeddings/centroids are unavailable or
    the query is off-domain (top relevance below _SEMANTIC_THRESHOLD)."""
    if k < 1:
        k = 1
    q_vec = _get_embedding(query)
    centroids = _load_centroids() if q_vec else {}
    if not q_vec or not centroids:
        return [("general", route_sources_semantic(query))]

    # Relevance of every domain that actually has sources wired up.
    rel = {
        d: _cosine(q_vec, v)
        for d, v in centroids.items()
        if _DOMAIN_SOURCES.get(d)
    }
    if not rel:
        return [("general", route_sources_semantic(query))]

    ranked = sorted(rel.items(), key=lambda x: x[1], reverse=True)
    # Off-domain query: behave like the normal router (single best-cluster group).
    if ranked[0][1] < _SEMANTIC_THRESHOLD:
        return [("general", route_sources_semantic(query))]

    selected: list[str] = [ranked[0][0]]
    candidates = [d for d, _ in ranked[1:] if rel[d] >= _PERSPECTIVE_FLOOR]
    while len(selected) < k and candidates:
        best_d, best_score = None, None
        for d in candidates:
            diversity = max(_cosine(centroids[d], centroids[s]) for s in selected)
            mmr = _PERSPECTIVE_LAMBDA * rel[d] - (1 - _PERSPECTIVE_LAMBDA) * diversity
            if best_score is None or mmr > best_score:
                best_d, best_score = d, mmr
        selected.append(best_d)
        candidates.remove(best_d)

    return [(d, _DOMAIN_SOURCES.get(d, [])) for d in selected if _DOMAIN_SOURCES.get(d)]


def question_to_intent(question: str) -> str:
    """Extract the factual core from a natural-language question via fast LLM call.
    Converts trivia framing into a clean search phrase for routing and retrieval."""
    try:
        from core.llm_edge import respond
        system = (
            "Extract the core factual query from this question as a search phrase. "
            "Output ONLY 4-8 domain-specific keywords — NO filler words like "
            "'description', 'information', 'facts', 'overview', 'details', 'history'. "
            "Keep proper nouns, technical terms, and subject-matter context. "
            "No punctuation. No explanation. Examples:\n"
            "Q: Why do ships painted red on the bottom last longer? "
            "→ antifouling copper paint ship hull protection\n"
            "Q: What albums did The Streets release? "
            "→ The Streets discography albums UK rap\n"
            "Q: Who invented the telephone? "
            "→ telephone invention Bell Gray patent\n"
            "Q: What is the International Space Station? "
            "→ International Space Station NASA orbital laboratory crew\n"
            "Q: What is habeas corpus? "
            "→ habeas corpus writ legal custody court"
        )
        result = respond(system, [], question)
        return result.strip()[:200] or question
    except Exception:
        return question


NO_WIKIPEDIA_NOTE = (
    "Wikipedia is excluded — results are from primary institutions "
    "and peer-reviewed sources suitable for academic citation."
)


_QUESTION_WORDS = re.compile(
    r"^(what|who|when|where|why|how|which|tell me about|find|look up|search for|"
    r"can you find|give me|show me)\s+",
    re.IGNORECASE,
)
_FILLER_WORDS = re.compile(
    r"\b(did|was|were|is|are|has|have|had|do|does|a|an|and|or|of|in|on|at|by|"
    r"for|with|about|release|released|make|made|create|created|write|wrote|publish|"
    r"published|appear|appeared|come|came|from|to|into)\b",
    re.IGNORECASE,
)
# "the" stripped separately — only remove standalone "the" not preceding a capital (proper noun)
_LONE_THE = re.compile(r"\bthe\b(?!\s+[A-Z])", re.IGNORECASE)


def question_to_query(question: str) -> str:
    """Derive a search-friendly query from a natural language question.
    Strips question words and common fillers; preserves proper nouns and key terms."""
    import re as _re
    q = question.strip().rstrip("?").rstrip(".")
    q = _QUESTION_WORDS.sub("", q)
    q = _FILLER_WORDS.sub(" ", q)
    q = _LONE_THE.sub(" ", q)
    q = _re.sub(r"\s+", " ", q).strip()
    return q or question.rstrip("?")


def list_sources() -> list[dict]:
    """Return source registry metadata from DB (canonical) or Python fallback."""
    registry = _load_registry()
    return [
        {"id": sid, "name": cfg["name"], "fn_name": cfg["fn_name"],
         "key_required": cfg["key_required"], "opt_in": cfg.get("opt_in", False)}
        for sid, cfg in registry.items()
    ]


def _rerank_combined(query: str, out: dict[str, list], top_n: int = 15) -> list[dict]:
    """Cross-source rerank of jeles hits via the same RRF fusion the main KB uses
    (willow/ranking/hybrid.py._rrf_fuse, k=60) — a lexical BM25 leg plus a cosine
    leg over the local embedding model, fused rather than sorted by cosine alone.
    Degrades to lexical-only when the embedder is unreachable (same graceful-degrade
    pattern hybrid.py already uses for KB search)."""
    from willow.ranking.hybrid import _tokenize, _build_bm25, _rrf_fuse

    flat: list[dict] = []
    for sid, hits in out.items():
        for hit in hits:
            row = dict(hit)
            row["source"] = row.get("source") or sid
            row["id"] = row.get("id") or f"{sid}:{hash((row.get('url'), row.get('title')))}"
            flat.append(row)
    if not flat:
        return []

    # Shape as {"title", "summary"} so hybrid.py's _row_text/_build_bm25 apply unmodified.
    bm25_rows = [{"title": r.get("title", ""), "summary": r.get("snippet", "")} for r in flat]
    bm25 = _build_bm25(bm25_rows)
    query_tokens = _tokenize(query)
    lexical_scores = bm25.get_scores(query_tokens)
    lexical_ranked = [flat[i] for i in sorted(
        range(len(flat)), key=lambda i: lexical_scores[i], reverse=True,
    )]

    ranked_lists = [lexical_ranked]
    q_vec = _get_embedding(query)
    if q_vec:
        cosine_ranked = []
        for row in flat:
            v = _get_embedding(f"{row.get('title', '')} {row.get('snippet', '')}")
            sim = _cosine(q_vec, v) if v else 0.0
            cosine_ranked.append({**row, "_cosine_sim": sim})
        cosine_ranked.sort(key=lambda r: -r["_cosine_sim"])
        ranked_lists.append(cosine_ranked)

    fused = _rrf_fuse(ranked_lists, weight_col=False)
    return fused[:top_n]


def search(
    query: str,
    sources: list[str] | None = None,
    limit_per_source: int = 3,
    wall_clock_limit: float = 20.0,
) -> dict:
    """Search across trusted sources. DB-registry dispatch via fn_name strings.
    sources=None → auto-routed via route_sources_semantic() to the ~6 sources
    whose domain best matches the query (falls back to all non-opt-in sources
    only if routing is unavailable). Pass a list to target specific ones and
    bypass routing entirely.

    Concurrent: up to 16 sources run in parallel via _SEARCH_EXECUTOR (module-level,
    shared across MCP calls). wall_clock_limit caps total wait time; per-source urllib
    timeout (_TIMEOUT) handles individual hangs. Sources not done within
    wall_clock_limit are dropped.

    Results carry a cross-source `ranked` list (RRF-fused, see _rerank_combined)
    in addition to the per-source `results` dict."""
    registry = _load_registry()
    if sources:
        active = sources
        routed = False
    else:
        # route_sources_semantic() always returns a non-empty list (falls back to
        # _DEFAULT_SOURCES as its own last resort), so this always narrows the fan-out.
        active = route_sources_semantic(query)
        routed = True

    resolved: list[tuple[str, object]] = []
    for sid in active:
        cfg = registry.get(sid)
        if not cfg:
            log.warning("Unknown source: %s", sid)
            continue
        fn = _resolve_fn(cfg["fn_name"])
        if not fn:
            log.warning("No function found for source %s (fn_name=%s)", sid, cfg["fn_name"])
            continue
        resolved.append((sid, fn))

    out: dict[str, list] = {}

    def _call(sid: str, fn) -> tuple[str, list]:
        try:
            return sid, fn(query, limit_per_source)
        except Exception as e:
            log.warning("Source %s failed: %s", sid, e)
            return sid, []

    futures = {_SEARCH_EXECUTOR.submit(_call, sid, fn): sid for sid, fn in resolved}
    try:
        for fut in _cf.as_completed(futures, timeout=wall_clock_limit):
            try:
                sid, hits = fut.result()
                if hits:
                    out[sid] = hits
            except Exception as e:
                log.warning("Source %s result error: %s", futures[fut], e)
    except _cf.TimeoutError:
        pending = sum(1 for f in futures if not f.done())
        log.warning(
            "jeles.search wall-clock limit %.1fs reached — %d source(s) still pending",
            wall_clock_limit, pending,
        )

    total = sum(len(v) for v in out.values())
    ranked = _rerank_combined(query, out) if out else []
    if out:
        _write_cache(query, out)
    return {
        "query": query,
        "sources_queried": active,
        "routed": routed,
        "total": total,
        "results": out,
        "ranked": ranked,
        "note": NO_WIKIPEDIA_NOTE,
    }
