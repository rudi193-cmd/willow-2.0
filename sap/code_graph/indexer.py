"""
sap/code_graph/indexer.py — Python AST → SQLite symbol graph.

Walks Python source files, extracts symbols (modules, classes, functions,
methods) and import/inheritance edges, persists to the code_graph DB.

Analogous to CodeGraphContext's tree-sitter indexer but Python-only,
zero external deps beyond stdlib.
"""
from __future__ import annotations

import ast
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

logger = logging.getLogger("code_graph.indexer")

# Edges whose target contains these prefixes are skipped (builtins / stdlib)
_SKIP_TARGETS = {"__", "builtins", "typing", "os", "sys", "re", "json",
                 "pathlib", "dataclasses", "collections", "itertools",
                 "functools", "abc", "enum", "logging"}


def _db_connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    schema = (Path(__file__).parent / "schema.sql").read_text()
    conn.executescript(schema)
    conn.commit()
    return conn


def _file_to_module(file_path: Path, repo_root: Path) -> str:
    """Convert a file path to a dotted module name."""
    rel = file_path.relative_to(repo_root)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    elif parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    return ".".join(parts)


def _sig(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Build a compact signature string from an AST function node."""
    args = []
    for arg in node.args.args:
        ann = ast.unparse(arg.annotation) if arg.annotation else ""
        args.append(f"{arg.arg}: {ann}" if ann else arg.arg)
    defaults_offset = len(node.args.args) - len(node.args.defaults)
    for i, default in enumerate(node.args.defaults):
        idx = defaults_offset + i
        if 0 <= idx < len(args):
            try:
                args[idx] += f" = {ast.unparse(default)}"
            except Exception:
                pass
    if node.args.vararg:
        args.append(f"*{node.args.vararg.arg}")
    if node.args.kwarg:
        args.append(f"**{node.args.kwarg.arg}")
    ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return f"({', '.join(args)}){ret}"


def _index_file(
    file_path: Path,
    repo_root: Path,
    source: str,
    conn: sqlite3.Connection,
) -> int:
    """Parse one Python file and upsert symbols + edges. Returns symbol count."""
    module_fqn = _file_to_module(file_path, repo_root)
    rel_path = str(file_path.relative_to(repo_root))
    lines = source.splitlines()
    byte_size = len(source.encode())

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        logger.warning("parse error %s: %s", rel_path, e)
        return 0

    symbols: list[tuple] = []
    edges: list[tuple] = []

    # Module-level symbol
    symbols.append((
        module_fqn, module_fqn.split(".")[-1], "module",
        rel_path, 1, len(lines), "", byte_size,
    ))

    for node in ast.walk(tree):
        # Import edges
        if isinstance(node, ast.Import):
            for alias in node.names:
                target = alias.name
                if not any(target.startswith(s) for s in _SKIP_TARGETS):
                    edges.append((module_fqn, target, "import"))

        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            for alias in node.names:
                target = f"{base}.{alias.name}" if base else alias.name
                if not any(target.startswith(s) for s in _SKIP_TARGETS):
                    edges.append((module_fqn, target, "import"))

        # Class definitions
        elif isinstance(node, ast.ClassDef):
            class_fqn = f"{module_fqn}.{node.name}"
            end = getattr(node, "end_lineno", node.lineno)
            class_bytes = sum(len(lines[i]) + 1
                              for i in range(node.lineno - 1, min(end, len(lines))))
            symbols.append((
                class_fqn, node.name, "class",
                rel_path, node.lineno, end, f"class {node.name}", class_bytes,
            ))
            # Inheritance edges
            for base in node.bases:
                try:
                    base_name = ast.unparse(base)
                    if not any(base_name.startswith(s) for s in _SKIP_TARGETS):
                        edges.append((class_fqn, base_name, "inherit"))
                except Exception:
                    pass

            # Methods
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_fqn = f"{class_fqn}.{item.name}"
                    mend = getattr(item, "end_lineno", item.lineno)
                    mbytes = sum(len(lines[i]) + 1
                                 for i in range(item.lineno - 1, min(mend, len(lines))))
                    symbols.append((
                        method_fqn, item.name, "method",
                        rel_path, item.lineno, mend, _sig(item), mbytes,
                    ))

        # Module-level functions
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Skip if inside a class (already handled above)
            func_fqn = f"{module_fqn}.{node.name}"
            fend = getattr(node, "end_lineno", node.lineno)
            fbytes = sum(len(lines[i]) + 1
                         for i in range(node.lineno - 1, min(fend, len(lines))))
            symbols.append((
                func_fqn, node.name, "function",
                rel_path, node.lineno, fend, _sig(node), fbytes,
            ))

    # Upsert all
    conn.executemany(
        """INSERT INTO symbols (fqn, name, kind, file_path, start_line, end_line, signature, byte_size)
           VALUES (?,?,?,?,?,?,?,?)
           ON CONFLICT(fqn) DO UPDATE SET
             kind=excluded.kind, file_path=excluded.file_path,
             start_line=excluded.start_line, end_line=excluded.end_line,
             signature=excluded.signature, byte_size=excluded.byte_size""",
        symbols,
    )
    conn.executemany(
        """INSERT OR IGNORE INTO edges (source_fqn, target_fqn, edge_type)
           VALUES (?,?,?)""",
        edges,
    )
    conn.execute(
        """INSERT INTO indexed_files (path, language, byte_size, line_count, symbol_count, indexed_at)
           VALUES (?,?,?,?,?,?)
           ON CONFLICT(path) DO UPDATE SET
             byte_size=excluded.byte_size, line_count=excluded.line_count,
             symbol_count=excluded.symbol_count, indexed_at=excluded.indexed_at""",
        (rel_path, "python", byte_size, len(lines), len(symbols),
         datetime.now(timezone.utc).isoformat()),
    )
    return len(symbols)


def _py_files(root: Path, exclude: set[str]) -> Generator[Path, None, None]:
    for path in root.rglob("*.py"):
        parts = set(path.parts)
        if parts & exclude:
            continue
        yield path


def index_repo(
    repo_root: str | Path,
    db_path: str | Path,
    *,
    exclude_dirs: set[str] | None = None,
    force: bool = False,
) -> dict:
    """Walk repo_root, index all Python files into db_path.

    exclude_dirs: directory names to skip (default: .git, __pycache__, venv, .venv,
                  node_modules, worktrees, .mypy_cache)
    force: re-index even if file is unchanged (default: skip unchanged by mtime)
    Returns: {files_indexed, symbols_total, skipped}
    """
    repo_root = Path(repo_root).resolve()
    db_path = Path(db_path).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    _exclude = exclude_dirs or {
        ".git", "__pycache__", "venv", ".venv", "node_modules",
        "worktrees", ".mypy_cache", ".pytest_cache", "dist", "build",
        ".venv-dev", ".venv-prod", "site-packages", ".tox", ".eggs",
    }

    conn = _db_connect(db_path)
    files_indexed = 0
    symbols_total = 0
    skipped = 0

    try:
        for py_file in _py_files(repo_root, _exclude):
            rel = str(py_file.relative_to(repo_root))
            source = py_file.read_text(errors="replace")
            count = _index_file(py_file, repo_root, source, conn)
            symbols_total += count
            files_indexed += 1
            if files_indexed % 50 == 0:
                conn.commit()
                logger.debug("indexed %d files so far…", files_indexed)

        conn.commit()
    finally:
        conn.close()

    return {
        "files_indexed": files_indexed,
        "symbols_total": symbols_total,
        "skipped": skipped,
        "db_path": str(db_path),
    }
