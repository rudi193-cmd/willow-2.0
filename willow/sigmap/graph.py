"""
willow/sigmap/graph.py — Python dependency graph builder.
b17: SMAP1  ΔΣ=42

Parses Python import statements using ast to build forward and reverse
dependency graphs. Resolves module names to filesystem paths under root.
Handles absolute imports, relative imports (.foo, ..foo), and package
hierarchies.
"""
import ast
import sys
from pathlib import Path


def _module_to_path(module_parts: list[str], root: Path) -> list[Path]:
    """Try to resolve a module name (as list of parts) to a file path under root.

    Returns a list of candidate paths (may be empty if not found).
    """
    candidates = []
    base = root
    for part in module_parts:
        base = base / part

    # Check as package (__init__.py)
    pkg = base / "__init__.py"
    if pkg.exists():
        candidates.append(pkg)

    # Check as module file
    mod = base.with_suffix(".py")
    if mod.exists():
        candidates.append(mod)

    return candidates


def _resolve_relative(
    module: str,
    level: int,
    source_path: Path,
    root: Path,
) -> list[Path]:
    """Resolve a relative import (level > 0) to filesystem paths.

    level=1 → same package, level=2 → parent package, etc.
    """
    # Walk up `level` directories from the source file's package
    anchor = source_path.parent
    for _ in range(level - 1):
        anchor = anchor.parent
        if anchor == anchor.parent:
            return []  # hit filesystem root

    if not module:
        # from . import foo → the anchor package itself
        candidates = []
        init = anchor / "__init__.py"
        if init.exists():
            candidates.append(init)
        return candidates

    parts = module.split(".")
    target = anchor
    for part in parts:
        target = target / part

    candidates = []
    pkg = target / "__init__.py"
    if pkg.exists():
        candidates.append(pkg)
    mod = target.with_suffix(".py")
    if mod.exists():
        candidates.append(mod)
    return candidates


def _extract_imports(source_path: Path, root: Path) -> list[Path]:
    """Parse a Python file and return all resolvable imported paths."""
    try:
        source = source_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
    except Exception:
        return []

    resolved = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                found = _module_to_path(parts, root)
                resolved.extend(found)

        elif isinstance(node, ast.ImportFrom):
            level = node.level or 0
            module = node.module or ""

            if level > 0:
                # Relative import
                found = _resolve_relative(module, level, source_path, root)
                resolved.extend(found)
            else:
                # Absolute import
                parts = module.split(".") if module else []
                found = _module_to_path(parts, root)
                resolved.extend(found)

    # Deduplicate, resolve to absolute, filter to only files under root
    seen = set()
    result = []
    for p in resolved:
        try:
            ap = p.resolve()
            if str(ap).startswith(str(root.resolve())) and ap not in seen:
                seen.add(ap)
                result.append(ap)
        except Exception:
            pass

    return result


def build_graph(root: Path, files: list[Path]) -> tuple[dict, dict]:
    """Build forward and reverse dependency graphs.

    Returns (graph, rev_graph) where:
      graph[path_str]     = [path_strs this file imports]
      rev_graph[path_str] = [path_strs that import this file]

    All paths are stored as strings (absolute).
    """
    graph: dict[str, list[str]] = {}
    rev_graph: dict[str, list[str]] = {}

    # Only index Python files for graph resolution
    py_files = [f for f in files if f.suffix == ".py"]
    file_set = {str(f.resolve()) for f in py_files}

    for source_path in py_files:
        src_str = str(source_path.resolve())
        imports = _extract_imports(source_path, root)

        for imp_path in imports:
            imp_str = str(imp_path)
            if imp_str in file_set:
                graph.setdefault(src_str, []).append(imp_str)
                rev_graph.setdefault(imp_str, []).append(src_str)

        if src_str not in graph:
            graph[src_str] = []

    return graph, rev_graph
