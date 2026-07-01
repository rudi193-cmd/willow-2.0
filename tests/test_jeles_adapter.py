"""Generic JSON search adapter — extraction correctness + migrated-source equivalence."""
from core import jeles_sources as js


def test_extract_path_walks_nested_dicts():
    obj = {"a": {"b": {"c": 42}}}
    assert js._extract_path(obj, "a.b.c") == 42


def test_extract_path_missing_segment_returns_none():
    assert js._extract_path({"a": {}}, "a.b.c") is None
    assert js._extract_path({}, "a") is None
    assert js._extract_path(None, "a") is None


def test_generic_json_search_basic_field_map(monkeypatch):
    monkeypatch.setattr(js, "_get", lambda url, headers=None: {
        "results": [
            {"name": "Item One", "link": "https://x/1", "year": 2020},
            {"name": "Item Two", "link": "https://x/2", "year": 2021},
        ]
    })
    hits = js._generic_json_search(
        source_id="test_src",
        url_template="https://example.com/search?q={query}&n={limit}",
        results_path="results",
        field_map={"title": "name", "url": "link", "date": lambda i: str(i.get("year", ""))},
        query="anything", limit=5,
        institution="Test Institution",
    )
    assert len(hits) == 2
    assert hits[0]["title"] == "Item One"
    assert hits[0]["url"] == "https://x/1"
    assert hits[0]["date"] == "2020"
    assert hits[0]["source"] == "test_src"
    assert hits[0]["institution"] == "Test Institution"


def test_generic_json_search_respects_limit(monkeypatch):
    monkeypatch.setattr(js, "_get", lambda url, headers=None: {
        "results": [{"name": f"Item {i}"} for i in range(10)]
    })
    hits = js._generic_json_search(
        source_id="test_src", url_template="https://example.com?q={query}&n={limit}",
        results_path="results", field_map={"title": "name"}, query="x", limit=3,
    )
    assert len(hits) == 3


def test_generic_json_search_empty_response_returns_empty_list(monkeypatch):
    monkeypatch.setattr(js, "_get", lambda url, headers=None: None)
    hits = js._generic_json_search(
        source_id="test_src", url_template="https://example.com?q={query}",
        results_path="results", field_map={}, query="x", limit=5,
    )
    assert hits == []


def test_search_openalex_matches_prior_field_mapping(monkeypatch):
    """Regression: openalex migrated to the generic adapter — doi-fallback url,
    per-item institution flattening, and the '/'-split id must still work."""
    payload = {
        "results": [
            {
                "display_name": "A Paper About Things",
                "doi": "https://doi.org/10.1/xyz",
                "id": "https://openalex.org/W12345",
                "abstract": "An abstract.",
                "publication_year": 2019,
                "authorships": [
                    {"institutions": [{"display_name": "MIT"}]},
                    {"institutions": [{"display_name": "Stanford"}]},
                ],
            },
            {
                "display_name": "No DOI Paper",
                "doi": None,
                "id": "https://openalex.org/W99999",
                "abstract": "",
                "publication_year": 2020,
                "authorships": [],
            },
        ]
    }
    monkeypatch.setattr(js, "_get", lambda url, headers=None: payload)
    hits = js.search_openalex("things", limit=5)
    assert len(hits) == 2
    assert hits[0]["title"] == "A Paper About Things"
    assert hits[0]["url"] == "https://doi.org/10.1/xyz"
    assert hits[0]["institution"] == "MIT, Stanford"
    assert hits[0]["date"] == "2019"
    assert hits[0]["id"] == "W12345"
    # No DOI -> falls back to the id URL, matching prior `doi if doi else item["id"]` logic.
    assert hits[1]["url"] == "https://openalex.org/W99999"
    assert hits[1]["institution"] == ""


def test_search_nasa_matches_prior_field_mapping(monkeypatch):
    payload = {
        "collection": {
            "items": [
                {
                    "data": [{"title": "Apollo 11", "description": "Moon landing.",
                              "date_created": "1969-07-20T00:00:00Z", "nasa_id": "as11-40-5875"}],
                    "links": [{"href": "https://images-assets.nasa.gov/x.jpg"}],
                },
            ]
        }
    }
    monkeypatch.setattr(js, "_get", lambda url, headers=None: payload)
    hits = js.search_nasa("apollo", limit=5)
    assert len(hits) == 1
    assert hits[0]["title"] == "Apollo 11"
    assert hits[0]["url"] == "https://images-assets.nasa.gov/x.jpg"
    assert hits[0]["institution"] == "NASA"
    assert hits[0]["date"] == "1969-07-20"
    assert hits[0]["id"] == "as11-40-5875"
