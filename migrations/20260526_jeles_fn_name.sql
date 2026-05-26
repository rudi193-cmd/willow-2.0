-- Jeles source registry: add fn_name column so Python is no longer the dispatch table.
-- After this migration, jeles_sources is the canonical source of truth.
-- Python only holds the search_* functions; everything else lives here.

ALTER TABLE jeles_sources ADD COLUMN IF NOT EXISTS fn_name text;

-- Default: fn_name = 'search_' + id (covers the vast majority of sources)
UPDATE jeles_sources
SET fn_name = 'search_' || replace(replace(id, '-', '_'), '.', '_')
WHERE fn_name IS NULL;

-- Overrides for IDs whose function names don't follow the pattern
UPDATE jeles_sources SET fn_name = 'search_internet_archive'  WHERE id = 'internet_archive';
UPDATE jeles_sources SET fn_name = 'search_chronicling_america' WHERE id = 'chronicling_america';
UPDATE jeles_sources SET fn_name = 'search_semantic_scholar'  WHERE id = 'semantic_scholar';
UPDATE jeles_sources SET fn_name = 'search_federal_register'  WHERE id = 'federal_register';
UPDATE jeles_sources SET fn_name = 'search_uk_legislation'    WHERE id = 'uk_legislation';
UPDATE jeles_sources SET fn_name = 'search_eu_data'           WHERE id = 'eu_data';
UPDATE jeles_sources SET fn_name = 'search_openfda'           WHERE id = 'openfda';
UPDATE jeles_sources SET fn_name = 'search_courtlistener'     WHERE id = 'courtlistener';
UPDATE jeles_sources SET fn_name = 'search_openaire'          WHERE id = 'openaire';
UPDATE jeles_sources SET fn_name = 'search_inaturalist'       WHERE id = 'inaturalist';
UPDATE jeles_sources SET fn_name = 'search_nominatim'         WHERE id = 'nominatim';
UPDATE jeles_sources SET fn_name = 'search_openlibrary'       WHERE id = 'openlibrary';
UPDATE jeles_sources SET fn_name = 'search_musicbrainz'       WHERE id = 'musicbrainz';
UPDATE jeles_sources SET fn_name = 'search_europepmc'         WHERE id = 'europepmc';
UPDATE jeles_sources SET fn_name = 'search_pubchem'           WHERE id = 'pubchem';
UPDATE jeles_sources SET fn_name = 'search_pubmed'            WHERE id = 'pubmed';
UPDATE jeles_sources SET fn_name = 'search_datagov'           WHERE id = 'datagov';
