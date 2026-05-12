"""CLI for git-shaped sandbox demo (`python -m sandbox`). b17: GSSM2 · ΔΣ=42"""
from __future__ import annotations

import argparse
from pathlib import Path

from .engine import GitShapedError, advance
from .gate_form import NewFeatureGate
from .model import ShapeState, create_issue
from .store import JsonStore


def _default_store_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "changes.json"


def _store(args: argparse.Namespace) -> JsonStore:
    return JsonStore(Path(args.data))


def cmd_issue_create(args: argparse.Namespace) -> None:
    ch = create_issue(args.title, subject=args.subject or "", flag_id=args.flag or "")
    st = _store(args)
    st.upsert(ch)
    print(ch.id)


def cmd_advance(args: argparse.Namespace) -> None:
    st = _store(args)
    ch = st.get(args.id)
    if not ch:
        raise SystemExit(f"unknown id: {args.id}")
    try:
        advance(ch, ShapeState(args.to), actor=args.actor, note=args.note or "")
    except GitShapedError as e:
        raise SystemExit(str(e)) from e
    st.upsert(ch)
    print(f"{ch.id} -> {ch.state.value}")


def cmd_show(args: argparse.Namespace) -> None:
    st = _store(args)
    ch = st.get(args.id)
    if not ch:
        raise SystemExit(f"unknown id: {args.id}")
    import json

    print(json.dumps(ch.to_json(), indent=2))


def cmd_list(args: argparse.Namespace) -> None:
    st = _store(args)
    for r in sorted(st.load_all(), key=lambda x: x.id):
        print(f"{r.id}\t{r.state.value}\t{r.title}")


def cmd_gate_check(args: argparse.Namespace) -> None:
    g = NewFeatureGate(
        state_touch=args.state,
        open_pr_equivalent=args.open_pr,
        merge_equivalent=args.merge,
        archive_equivalent=args.archive,
    )
    errs = g.validate()
    if errs:
        for e in errs:
            print(f"ERR: {e}")
        raise SystemExit(1)
    print("gate_ok")


def main() -> None:
    p = argparse.ArgumentParser(prog="sandbox", description="Git-shaped state machine (WLGSM reference impl)")
    p.add_argument("--data", default=str(_default_store_path()), help="JSON store path")

    sub = p.add_subparsers(dest="cmd", required=True)

    p_issue = sub.add_parser("issue-create", help="Create change at state issue")
    p_issue.add_argument("--title", required=True)
    p_issue.add_argument("--subject", default="")
    p_issue.add_argument("--flag", default="", help="optional linked SOIL flag id")
    p_issue.set_defaults(func=cmd_issue_create)

    p_adv = sub.add_parser("advance", help="Advance one step (git-shaped)")
    p_adv.add_argument("id")
    p_adv.add_argument(
        "--to",
        required=True,
        choices=[s.value for s in ShapeState],
        help="target state",
    )
    p_adv.add_argument("--actor", required=True)
    p_adv.add_argument("--note", default="")
    p_adv.set_defaults(func=cmd_advance)

    p_show = sub.add_parser("show", help="JSON dump of one change")
    p_show.add_argument("id")
    p_show.set_defaults(func=cmd_show)

    p_ls = sub.add_parser("list", help="List all changes")
    p_ls.set_defaults(func=cmd_list)

    p_gate = sub.add_parser("gate-check", help="Validate §4 new-feature gate answers")
    p_gate.add_argument("--state", required=True)
    p_gate.add_argument("--open-pr", required=True, dest="open_pr")
    p_gate.add_argument("--merge", required=True)
    p_gate.add_argument("--archive", required=True)
    p_gate.set_defaults(func=cmd_gate_check)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
