"""
willow/sigmap/impact.py — Impact analysis for a target file.
b17: SMAP1  ΔΣ=42

Given a file path and dependency graphs, returns what would be affected
by changes to that file: direct importers, transitive importers (2 hops),
affected test files, and affected API route files.
"""


def get_impact(
    target: str,
    graph: dict,      # {path: [import_paths]} forward edges
    rev_graph: dict,  # {path: [importers]} reverse edges
) -> dict:
    """Return impact report for target file.

    Returns:
    {
        "direct": [paths that directly import target],
        "transitive": [paths that transitively import target, up to 2 hops],
        "tests": [test files affected],
        "routes": [API route files affected],
    }
    """
    direct = list(rev_graph.get(target, []))

    # 2-hop transitive importers (exclude direct to avoid duplication)
    transitive = []
    for d in direct:
        for importer in rev_graph.get(d, []):
            if importer != target and importer not in direct and importer not in transitive:
                transitive.append(importer)

    def _is_test(p: str) -> bool:
        pl = p.lower()
        return (
            "/test" in pl or "/spec" in pl or "/fixture" in pl
            or "test_" in pl or "_test." in pl or ".spec." in pl
            or pl.startswith("test") or pl.startswith("spec")
        )

    def _is_route(p: str) -> bool:
        pl = p.lower()
        return (
            "/router" in pl or "/route" in pl or "/api/" in pl
            or "/endpoint" in pl or "/views." in pl or "/handlers." in pl
            or pl.endswith("_routes.py") or pl.endswith("_router.py")
        )

    all_affected = direct + transitive
    tests = [p for p in all_affected if _is_test(p)]
    routes = [p for p in all_affected if _is_route(p)]

    return {
        "direct":     direct,
        "transitive": transitive,
        "tests":      tests,
        "routes":     routes,
    }
