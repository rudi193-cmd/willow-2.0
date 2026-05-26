#!/usr/bin/env python3
"""
seed_jeles_registry.py — Populate jeles_sources and jeles_domain_routes from
the static Python definitions in core/jeles_sources.py.

Run once after applying 20260525_jeles_source_registry.sql migration.
Safe to re-run — uses INSERT ... ON CONFLICT DO UPDATE.

Usage:
    python3 agents/hanuman/bin/seed_jeles_registry.py
    python3 agents/hanuman/bin/seed_jeles_registry.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from core.jeles_sources import (
    SOURCES,
    _DOMAIN_SEEDS,
    _DOMAIN_SOURCES,
    _DOMAIN_ROUTES,
)
from core.pg_bridge import PgBridge


def seed_sources(cur, dry_run: bool) -> int:
    count = 0
    for sid, cfg in SOURCES.items():
        domains = cfg.get("domain", [])
        key_req = cfg.get("key_required", False)
        opt_in  = cfg.get("opt_in", False)
        conf    = 0.85
        name    = cfg.get("name", sid)
        meta    = {}

        if dry_run:
            print(f"  [source] {sid!r:30s} domains={domains}  key={key_req}  opt_in={opt_in}")
        else:
            cur.execute("""
                INSERT INTO jeles_sources
                    (id, name, domains, key_required, enabled, opt_in, confidence, metadata)
                VALUES (%s, %s, %s, %s, true, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name         = EXCLUDED.name,
                    domains      = EXCLUDED.domains,
                    key_required = EXCLUDED.key_required,
                    opt_in       = EXCLUDED.opt_in,
                    confidence   = EXCLUDED.confidence,
                    metadata     = EXCLUDED.metadata,
                    valid_at     = now()
            """, (sid, name, domains, key_req, opt_in, conf, __import__("json").dumps(meta)))
        count += 1
    return count


def seed_domain_routes(cur, dry_run: bool) -> int:
    # Build keyword map from _DOMAIN_ROUTES for each domain
    keyword_map: dict[str, list[str]] = {}
    for keywords, source_ids in _DOMAIN_ROUTES:
        # Identify which domain(s) this route belongs to by matching source_ids to _DOMAIN_SOURCES
        for domain, dom_sources in _DOMAIN_SOURCES.items():
            if dom_sources[:len(source_ids)] == source_ids or set(source_ids) & set(dom_sources):
                keyword_map.setdefault(domain, []).extend(keywords)
                break
        else:
            # fallback: assign to "general"
            keyword_map.setdefault("general", []).extend(keywords)

    count = 0
    for domain, seeds in _DOMAIN_SEEDS.items():
        source_ids = _DOMAIN_SOURCES.get(domain, [])
        keywords   = list(dict.fromkeys(keyword_map.get(domain, [])))  # dedupe, preserve order

        if dry_run:
            print(f"  [domain] {domain!r:20s}  sources={source_ids}  keywords={len(keywords)}  seeds={len(seeds)}")
        else:
            cur.execute("""
                INSERT INTO jeles_domain_routes
                    (domain, keywords, source_ids, seed_sentences)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (domain) DO UPDATE SET
                    keywords       = EXCLUDED.keywords,
                    source_ids     = EXCLUDED.source_ids,
                    seed_sentences = EXCLUDED.seed_sentences,
                    updated_at     = now()
            """, (domain, keywords, source_ids, seeds))
        count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Jeles source registry into Postgres")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be written without DB writes")
    args = parser.parse_args()

    bridge = PgBridge()
    cur = bridge.conn.cursor()

    print(f"Seeding jeles_sources ({len(SOURCES)} entries)...")
    n_sources = seed_sources(cur, args.dry_run)
    print(f"  → {n_sources} sources {'would be' if args.dry_run else ''} written")

    print(f"Seeding jeles_domain_routes ({len(_DOMAIN_SEEDS)} domains)...")
    n_domains = seed_domain_routes(cur, args.dry_run)
    print(f"  → {n_domains} domain routes {'would be' if args.dry_run else ''} written")

    if not args.dry_run:
        bridge.conn.commit()
        print("Committed.")
        print()
        print("Next: run mem_jeles_build_centroids(force=true) to populate centroid vectors.")
    else:
        print("[DRY RUN] no writes performed")

    cur.close()
    bridge.conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
