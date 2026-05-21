"""
CLI for sap/code_graph.

Usage:
    python3 -m sap.code_graph index [--root PATH] [--db PATH] [--force]
    python3 -m sap.code_graph search QUERY [--kinds function,class] [--n 20]
    python3 -m sap.code_graph explain SYMBOL
    python3 -m sap.code_graph suggest TASK [--n 10]
    python3 -m sap.code_graph walk ANCHOR [--hops 2] [--tokens 8000]
    python3 -m sap.code_graph impact FILE [FILE ...]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_DEFAULT_DB = Path(os.environ.get(
    "WILLOW_CODE_GRAPH_DB",
    str(Path.home() / ".willow" / "code_graph.db"),
))
_DEFAULT_ROOT = Path(os.environ.get(
    "WILLOW_CODE_GRAPH_ROOT",
    str(Path(__file__).resolve().parent.parent.parent),
))


def cmd_index(args: argparse.Namespace) -> None:
    from sap.code_graph.indexer import index_repo
    root = Path(args.root) if args.root else _DEFAULT_ROOT
    db   = Path(args.db)   if args.db   else _DEFAULT_DB
    print(f"Indexing {root} → {db} …", flush=True)
    result = index_repo(root, db, force=args.force)
    print(f"Done. files={result['files_indexed']}  symbols={result['symbols_total']}")


def cmd_search(args: argparse.Namespace) -> None:
    from sap.code_graph.fuzzy import search_symbols
    db = Path(args.db) if args.db else _DEFAULT_DB
    kinds = args.kinds.split(",") if args.kinds else None
    results = search_symbols(db, args.query, max_results=args.n, kinds=kinds)
    for r in results:
        print(f"  {r['fqn']:<60} {r['kind']:<10} {r['file_path']}:{r['start_line']}")


def cmd_explain(args: argparse.Namespace) -> None:
    from sap.code_graph.fuzzy import explain_symbol
    db = Path(args.db) if args.db else _DEFAULT_DB
    r = explain_symbol(db, args.symbol)
    if "error" in r:
        print(r["error"], file=sys.stderr)
        sys.exit(1)
    print(f"{r['fqn']}  [{r['kind']}]")
    print(f"  file:      {r['file_path']}:{r['start_line']}-{r['end_line']}")
    print(f"  signature: {r['signature'] or '(none)'}")
    if r["callers"]:
        print(f"  callers ({len(r['callers'])}):")
        for c in r["callers"][:8]:
            print(f"    ← {c['fqn']}  via {c['via']}")
    if r["callees"]:
        print(f"  callees ({len(r['callees'])}):")
        for c in r["callees"][:8]:
            print(f"    → {c['fqn']}  via {c['via']}")


def cmd_suggest(args: argparse.Namespace) -> None:
    from sap.code_graph.fuzzy import suggest_files
    db = Path(args.db) if args.db else _DEFAULT_DB
    results = suggest_files(db, args.task, max_results=args.n)
    for r in results:
        syms = ", ".join(r["matching_symbols"][:4])
        print(f"  [{r['score']:>4}]  {r['file_path']:<50}  {syms}")


def cmd_walk(args: argparse.Namespace) -> None:
    from sap.code_graph.walker import walk
    db = Path(args.db) if args.db else _DEFAULT_DB
    result = walk(db, args.anchor, hop_depth=args.hops, max_tokens=args.tokens)
    print(f"anchor={result.anchor_fqn}  hops={result.hops_traversed}  tokens={result.tokens_returned}")
    print(f"files ({len(result.files)}):")
    for f in result.files:
        print(f"  {f}")
    print(f"symbols ({len(result.symbols)}):")
    for s in result.symbols:
        print(f"  hop{s['hop_distance']}  {s['fqn']:<60}  {s['file_path']}:{s['start_line']}")


def cmd_impact(args: argparse.Namespace) -> None:
    from sap.code_graph.walker import analyze_impact
    db = Path(args.db) if args.db else _DEFAULT_DB
    result = analyze_impact(db, args.files)
    print(f"source modules: {result['source_modules']}")
    print(f"affected files ({len(result['affected_files'])}):")
    for f in result["affected_files"]:
        print(f"  {f}")
    print(f"affected symbols ({len(result['affected_symbols'])}):")
    for s in result["affected_symbols"][:20]:
        print(f"  {s['fqn']}")


def main() -> None:
    p = argparse.ArgumentParser(
        prog="python3 -m sap.code_graph",
        description="Budget-aware Python symbol graph",
    )
    p.add_argument("--db",   default="", help="DB path (default: ~/.willow/code_graph.db)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("index", help="Index Python files → symbol graph")
    pi.add_argument("--root",  default="", help="Repo root (default: WILLOW_CODE_GRAPH_ROOT)")
    pi.add_argument("--force", action="store_true", help="Re-index all files")
    pi.set_defaults(func=cmd_index)

    ps = sub.add_parser("search", help="Fuzzy symbol search")
    ps.add_argument("query")
    ps.add_argument("--kinds", default="", help="Comma-separated: function,class,method,module")
    ps.add_argument("--n", type=int, default=20)
    ps.set_defaults(func=cmd_search)

    pe = sub.add_parser("explain", help="Explain a symbol: sig, callers, callees")
    pe.add_argument("symbol")
    pe.set_defaults(func=cmd_explain)

    pg = sub.add_parser("suggest", help="Suggest files relevant to a task")
    pg.add_argument("task")
    pg.add_argument("--n", type=int, default=10)
    pg.set_defaults(func=cmd_suggest)

    pw = sub.add_parser("walk", help="BFS from anchor within token budget")
    pw.add_argument("anchor")
    pw.add_argument("--hops",   type=int, default=2)
    pw.add_argument("--tokens", type=int, default=8000)
    pw.set_defaults(func=cmd_walk)

    pim = sub.add_parser("impact", help="Blast radius: what imports these files?")
    pim.add_argument("files", nargs="+")
    pim.set_defaults(func=cmd_impact)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
