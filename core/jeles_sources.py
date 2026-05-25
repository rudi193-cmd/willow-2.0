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
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

log = logging.getLogger("jeles.sources")

_CREDS_PATH = Path.home() / ".willow" / "secrets" / "credentials.json"
_CACHE_DIR  = Path.home() / ".willow" / "jeles_cache"
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
}


def _load_creds() -> dict:
    try:
        return json.loads(_CREDS_PATH.read_text())
    except Exception:
        return {}


def _get(url: str, headers: dict | None = None) -> Optional[dict | list]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA, **(headers or {})})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            return json.loads(r.read())
    except Exception as e:
        log.warning("GET %s failed: %s", url[:80], e)
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
        link = next((l.get("url", "") for l in (bib.get("link") or [])), "")
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
    # Academic
    "openalex":         {"name": "OpenAlex",                "domain": ["academic", "science", "humanities"], "fn": search_openalex,         "key_required": False},
    "core":             {"name": "CORE",                    "domain": ["academic", "science"],               "fn": search_core,             "key_required": False},
    "doaj":             {"name": "DOAJ",                    "domain": ["academic", "open_access"],           "fn": search_doaj,             "key_required": False},
    "europepmc":        {"name": "Europe PMC",              "domain": ["biology", "medicine", "health"],     "fn": search_europepmc,        "key_required": False},
    "semantic_scholar": {"name": "Semantic Scholar",        "domain": ["academic", "cs", "science"],         "fn": search_semantic_scholar,  "key_required": False},
    "crossref":         {"name": "Crossref",                "domain": ["academic", "general"],               "fn": search_crossref,         "key_required": False},
    "pubmed":           {"name": "PubMed",                  "domain": ["biology", "medicine"],               "fn": search_pubmed,           "key_required": False},
    "arxiv":            {"name": "arXiv",                   "domain": ["science", "cs", "math", "physics"],  "fn": search_arxiv,            "key_required": False},
    # Data / Science
    "zenodo":           {"name": "Zenodo",                  "domain": ["science", "data", "general"],        "fn": search_zenodo,           "key_required": False},
    "datacite":         {"name": "DataCite",                "domain": ["science", "data"],                   "fn": search_datacite,         "key_required": False},
    "wikidata":         {"name": "Wikidata",                "domain": ["general", "reference"],              "fn": search_wikidata,         "key_required": False},
    "pubchem":          {"name": "PubChem",                 "domain": ["chemistry", "science"],              "fn": search_pubchem,          "key_required": False},
    "usgs":             {"name": "USGS Publications",       "domain": ["geology", "earth_science"],          "fn": search_usgs,             "key_required": False},
    "nasa":             {"name": "NASA",                    "domain": ["space", "science"],                  "fn": search_nasa,             "key_required": False},
    # Museums
    "met":              {"name": "Met Museum",              "domain": ["art", "culture", "history"],         "fn": search_met,              "key_required": False},
    "cleveland":        {"name": "Cleveland Museum of Art", "domain": ["art", "culture"],                    "fn": search_cleveland,        "key_required": False},
    "vam":              {"name": "V&A Museum",              "domain": ["art", "design", "culture"],          "fn": search_vam,              "key_required": False},
    "rijksmuseum":      {"name": "Rijksmuseum",             "domain": ["art", "history"],                    "fn": search_rijksmuseum,      "key_required": True},
    # Libraries & Archives
    "loc":              {"name": "Library of Congress",     "domain": ["humanities", "history", "general"],  "fn": search_loc,              "key_required": False},
    "openlibrary":      {"name": "Open Library",            "domain": ["books", "humanities"],               "fn": search_openlibrary,      "key_required": False},
    "chronicling_america": {"name": "Chronicling America", "domain": ["history", "journalism"],             "fn": search_chronicling_america, "key_required": False},
    "internet_archive": {"name": "Internet Archive",        "domain": ["general", "books", "media"],         "fn": search_internet_archive, "key_required": False},
    "dpla":             {"name": "DPLA",                    "domain": ["humanities", "history", "general"],  "fn": search_dpla,             "key_required": True},
    # Heritage
    "smithsonian":      {"name": "Smithsonian",             "domain": ["art", "history", "science"],         "fn": search_smithsonian,      "key_required": True},
    "europeana":        {"name": "Europeana",               "domain": ["art", "culture", "history"],         "fn": search_europeana,        "key_required": True},
    # International
    "gallica":          {"name": "Gallica (BnF)",           "domain": ["humanities", "history", "france"],   "fn": search_gallica,          "key_required": False},
    "hal":              {"name": "HAL Open Access",         "domain": ["academic", "science", "france"],     "fn": search_hal,              "key_required": False},
    "scielo":           {"name": "SciELO",                  "domain": ["science", "latin_america", "iberia"],"fn": search_scielo,           "key_required": False},
    "ndl":              {"name": "National Diet Library",   "domain": ["general", "japan", "asia"],          "fn": search_ndl,              "key_required": False},
    # Opt-in only — general reference, not suitable for academic citation
    "wikipedia":        {"name": "Wikipedia",               "domain": ["general", "reference"],              "fn": search_wikipedia,        "key_required": False, "opt_in": True},
}

NO_WIKIPEDIA_NOTE = (
    "Wikipedia is excluded — results are from primary institutions "
    "and peer-reviewed sources suitable for academic citation."
)


def list_sources() -> list[dict]:
    """Return source registry metadata (no search functions)."""
    return [
        {
            "id": sid,
            "name": cfg["name"],
            "domain": cfg["domain"],
            "key_required": cfg["key_required"],
        }
        for sid, cfg in SOURCES.items()
    ]


def search(
    query: str,
    sources: list[str] | None = None,
    limit_per_source: int = 3,
) -> dict:
    """
    Search across trusted sources. Returns {source_id: [results]} plus a citation note.
    sources=None → all sources. Pass a list to target specific ones.
    """
    active = sources if sources else [sid for sid, cfg in SOURCES.items() if not cfg.get("opt_in")]
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
    if out:
        _write_cache(query, out)
    return {
        "query": query,
        "sources_queried": active,
        "total": total,
        "results": out,
        "note": NO_WIKIPEDIA_NOTE,
    }
