#!/usr/bin/env python3
"""
think_map.py — Think Map CLI.
b17: THNK3  ΔΣ=42

Usage:
    think_map.py new "<problem statement>" [--no-hydrate]
    think_map.py list [--all]
    think_map.py show <map_id>
    think_map.py approach <map_id> "<text>" "<tradeoff>" [--recommend]
    think_map.py constraint <map_id> "<text>" [--soft]
    think_map.py satellite <map_id> "<text>" [--ref <ref>]
    think_map.py recommend <map_id> <node_id>
    think_map.py hydrate <map_id>
    think_map.py confirm <map_id>
    think_map.py validate <map_id>
    think_map.py export <map_id> [--fork]
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from agents.hanuman.lib.think_map.store import (
    new_map, get_map, list_maps, add_approach, add_constraint,
    add_satellite, set_recommended, confirm_map, validate,
)
from agents.hanuman.lib.think_map.hydrate import hydrate as _hydrate
from agents.hanuman.lib.think_map.export import export_map as _export_map

_W = 68


def _sep(char="─"):
    return char * _W


def _render(r: dict) -> None:
    status = r.get("status", "?")
    status_tag = "[CONFIRMED]" if status == "confirmed" else "[Draft]"
    print(f"\n{_sep()}")
    print(f"  {r['id']}  {status_tag}")
    print(f"  {r.get('updated_at','')[:19]}")
    print(_sep())

    center = r.get("center", {})
    print(f"\n● {center.get('text', '(no problem set)')}")
    print()

    nodes = r.get("nodes", [])
    approaches = [n for n in nodes if n.get("kind") == "approach"]
    constraints = [n for n in nodes if n.get("kind") == "constraint"]
    satellites = [n for n in nodes if n.get("kind") == "satellite"]

    if approaches:
        for a in approaches:
            rec = "★ rec" if a.get("recommended") else "     "
            print(f"  ├─ [{a['id']}] {rec}  {a['text']}")
            if a.get("tradeoff"):
                print(f"  │           Tradeoff: {a['tradeoff']}")
        print()

    if constraints:
        for c in constraints:
            icon = "⛔" if c.get("hard") else "⚠"
            print(f"  {icon} [{c['id']}] {c['text']}")
        print()

    if satellites:
        for s in satellites:
            pin = "📌" if s.get("pinned") else "○"
            ref = f"  ({s['ref']})" if s.get("ref") else ""
            print(f"  {pin} [{s['id']}] {s['text']}{ref}")
        print()

    errors = validate(r)
    if errors and status == "draft":
        print("  To confirm, fix:")
        for e in errors:
            print(f"    - {e}")
    elif not errors and status == "draft":
        print(f"  Ready to confirm: think_map.py confirm {r['id']}")

    print(_sep())


def cmd_new(problem: str, auto_hydrate: bool = True) -> None:
    r = new_map(problem)
    print(f"Created: {r['id']}")
    if auto_hydrate:
        print("  Hydrating satellites...")
        try:
            r = _hydrate(r["id"])
            sats = [n for n in r.get("nodes", []) if n.get("kind") == "satellite"]
            if sats:
                print(f"  {len(sats)} satellite(s) added from KB/handoffs/tensions")
        except Exception as exc:
            print(f"  (hydrate skipped: {exc})")
    _render(r)


def cmd_hydrate(mid: str) -> None:
    r = get_map(mid)
    if not r:
        print(f"Not found: {mid}", file=sys.stderr)
        sys.exit(1)
    before = sum(1 for n in r.get("nodes", []) if n.get("kind") == "satellite")
    print(f"Hydrating {mid}...")
    r = _hydrate(mid)
    after = sum(1 for n in r.get("nodes", []) if n.get("kind") == "satellite")
    added = after - before
    print(f"  +{added} satellite(s) (total: {after})")
    _render(r)


def cmd_list(show_all: bool = False) -> None:
    maps = list_maps() if show_all else list_maps(status="draft")
    if not maps:
        print("No think maps." if show_all else "No draft maps. Use --all to see confirmed.")
        return
    for r in maps:
        status = r.get("status", "?")
        n_approaches = sum(1 for n in r.get("nodes", []) if n.get("kind") == "approach")
        has_rec = any(n.get("recommended") for n in r.get("nodes", []) if n.get("kind") == "approach")
        rec_tag = "★" if has_rec else " "
        center = r.get("center", {}).get("text", "")[:50]
        print(f"  [{status[:4]}] {rec_tag} {r['id']}")
        print(f"         {center}")
        print(f"         {n_approaches}/3 approaches  {r.get('updated_at','')[:10]}")


def cmd_show(mid: str) -> None:
    r = get_map(mid)
    if not r:
        print(f"Not found: {mid}", file=sys.stderr)
        sys.exit(1)
    _render(r)


def cmd_approach(mid: str, text: str, tradeoff: str, recommend: bool = False) -> None:
    r = add_approach(mid, text, tradeoff, recommended=recommend)
    approaches = [n for n in r["nodes"] if n.get("kind") == "approach"]
    print(f"Added approach ({len(approaches)}/3). Map: {mid}")
    if recommend:
        print(f"  ★ Marked as recommended")
    node = next((n for n in reversed(r["nodes"]) if n.get("kind") == "approach"), None)
    if node:
        print(f"  Node ID: {node['id']}")


def cmd_constraint(mid: str, text: str, hard: bool = True) -> None:
    r = add_constraint(mid, text, hard=hard)
    node = next((n for n in reversed(r["nodes"]) if n.get("kind") == "constraint"), None)
    icon = "⛔" if hard else "⚠"
    print(f"  {icon} Constraint added: {node['id'] if node else '?'}")


def cmd_satellite(mid: str, text: str, ref: str = "") -> None:
    r = add_satellite(mid, text, ref=ref)
    node = next((n for n in reversed(r["nodes"]) if n.get("kind") == "satellite"), None)
    print(f"  ○ Satellite added: {node['id'] if node else '?'}")


def cmd_recommend(mid: str, node_id: str) -> None:
    set_recommended(mid, node_id)
    print(f"  ★ {node_id} marked as recommended")


def cmd_validate(mid: str) -> None:
    r = get_map(mid)
    if not r:
        print(f"Not found: {mid}", file=sys.stderr)
        sys.exit(1)
    errors = validate(r)
    if errors:
        print(f"Not ready ({len(errors)} issues):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print(f"Valid — ready to confirm: think_map.py confirm {mid}")


def cmd_export(mid: str, fork: bool = False) -> None:
    try:
        r = _export_map(mid, create_fork=fork)
        print(f"Exported: {r['id']}")
        print(f"  Title:    {r['title']}")
        print(f"  Decision: {r['recommended_approach']}")
        if r.get("kb_atom_id"):
            print(f"  KB atom:  {r['kb_atom_id']}")
        else:
            print("  KB atom:  (ingest failed — check MCP)")
        if r.get("fork_id"):
            print(f"  Fork:     {r['fork_id']}")
    except (KeyError, ValueError) as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


def cmd_confirm(mid: str) -> None:
    try:
        r = confirm_map(mid)
        print(f"Confirmed: {mid}")
        _render(r)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


def _usage() -> None:
    print(__doc__)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        _usage()
        sys.exit(1)

    cmd = args[0]

    if cmd == "new":
        if len(args) < 2:
            print("Usage: think_map.py new \"<problem>\" [--no-hydrate]", file=sys.stderr)
            sys.exit(1)
        cmd_new(args[1], auto_hydrate="--no-hydrate" not in args)

    elif cmd == "list":
        cmd_list(show_all="--all" in args)

    elif cmd == "show":
        if len(args) < 2:
            print("Usage: think_map.py show <map_id>", file=sys.stderr)
            sys.exit(1)
        cmd_show(args[1])

    elif cmd == "approach":
        if len(args) < 4:
            print("Usage: think_map.py approach <id> \"<text>\" \"<tradeoff>\" [--recommend]", file=sys.stderr)
            sys.exit(1)
        cmd_approach(args[1], args[2], args[3], recommend="--recommend" in args)

    elif cmd == "constraint":
        if len(args) < 3:
            print("Usage: think_map.py constraint <id> \"<text>\" [--soft]", file=sys.stderr)
            sys.exit(1)
        cmd_constraint(args[1], args[2], hard="--soft" not in args)

    elif cmd == "satellite":
        if len(args) < 3:
            print("Usage: think_map.py satellite <id> \"<text>\" [--ref <ref>]", file=sys.stderr)
            sys.exit(1)
        ref = ""
        if "--ref" in args:
            idx = args.index("--ref")
            if idx + 1 < len(args):
                ref = args[idx + 1]
        cmd_satellite(args[1], args[2], ref=ref)

    elif cmd == "recommend":
        if len(args) < 3:
            print("Usage: think_map.py recommend <map_id> <node_id>", file=sys.stderr)
            sys.exit(1)
        cmd_recommend(args[1], args[2])

    elif cmd == "hydrate":
        if len(args) < 2:
            print("Usage: think_map.py hydrate <map_id>", file=sys.stderr)
            sys.exit(1)
        cmd_hydrate(args[1])

    elif cmd == "export":
        if len(args) < 2:
            print("Usage: think_map.py export <map_id> [--fork]", file=sys.stderr)
            sys.exit(1)
        cmd_export(args[1], fork="--fork" in args)

    elif cmd == "validate":
        if len(args) < 2:
            print("Usage: think_map.py validate <map_id>", file=sys.stderr)
            sys.exit(1)
        cmd_validate(args[1])

    elif cmd == "confirm":
        if len(args) < 2:
            print("Usage: think_map.py confirm <map_id>", file=sys.stderr)
            sys.exit(1)
        cmd_confirm(args[1])

    else:
        _usage()
        sys.exit(1)
