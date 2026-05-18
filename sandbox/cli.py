"""CLI for git-shaped sandbox demo (`python -m sandbox`). b17: GSSM2 · ΔΣ=42"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import GitShapedError, advance, preview_advance
from .gate_form import NewFeatureGate
from .model import ShapeState, create_issue
from .reporting import allowed_line, json_lines, markdown_table
from .store import JsonStore


def _default_store_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "changes.json"


def _store(args: argparse.Namespace) -> JsonStore:
    return JsonStore(Path(args.data))


def cmd_init(args: argparse.Namespace) -> None:
    p = Path(args.data)
    p.parent.mkdir(parents=True, exist_ok=True)
    st = JsonStore(p)
    if not p.exists():
        st.save_all([])
    print(f"ok data_dir={p.parent} store={p}")


def cmd_issue_create(args: argparse.Namespace) -> None:
    ch = create_issue(
        args.title,
        subject=args.subject or "",
        flag_id=args.flag or "",
        grove_channel=args.grove or "",
        kb_seed_hint=args.kb_hint or "",
        fork_id=args.fork or "",
    )
    st = _store(args)
    st.upsert(ch)
    print(ch.id)


def cmd_advance(args: argparse.Namespace) -> None:
    st = _store(args)
    ch = st.get(args.id)
    if not ch:
        raise SystemExit(f"unknown id: {args.id}")
    to = ShapeState(args.to)
    if getattr(args, "dry_run", False):
        pv = preview_advance(ch, to, actor=args.actor, note=args.note or "")
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "id": ch.id,
                    "from_state": ch.state.value,
                    "to_state": pv.state.value,
                    "last_transition": {
                        "at": pv.history[-1].at,
                        "from": pv.history[-1].from_state.value,
                        "to": pv.history[-1].to_state.value,
                        "actor": pv.history[-1].actor,
                        "note": pv.history[-1].note,
                    },
                },
                indent=2,
            )
        )
        return
    try:
        advance(ch, to, actor=args.actor, note=args.note or "")
    except GitShapedError as e:
        raise SystemExit(str(e)) from e
    st.upsert(ch)
    print(f"{ch.id} -> {ch.state.value}")


def cmd_show(args: argparse.Namespace) -> None:
    st = _store(args)
    ch = st.get(args.id)
    if not ch:
        raise SystemExit(f"unknown id: {args.id}")
    print(json.dumps(ch.to_json(), indent=2))


def cmd_list(args: argparse.Namespace) -> None:
    st = _store(args)
    rows = sorted(st.load_all(), key=lambda x: (x.updated_at or x.id), reverse=True)
    if getattr(args, "json", False):
        print(json_lines(rows))
        return
    if getattr(args, "long", False):
        for r in rows:
            print(
                f"{r.id}\t{r.state.value}\t{r.updated_at or '—'}\t{r.title}\t"
                f"subj={r.subject or '—'}\tgrove={r.grove_channel or '—'}"
            )
        return
    for r in rows:
        print(f"{r.id}\t{r.state.value}\t{r.title}")


def cmd_allowed(args: argparse.Namespace) -> None:
    st = _store(args)
    ch = st.get(args.id)
    if not ch:
        raise SystemExit(f"unknown id: {args.id}")
    print(allowed_line(ch.state))
    for s in sorted(allowed_targets(ch.state), key=lambda x: x.value):
        print(f"  {s.value}")


def cmd_report(args: argparse.Namespace) -> None:
    st = _store(args)
    print(markdown_table(st.load_all()))


def cmd_delete(args: argparse.Namespace) -> None:
    st = _store(args)
    if not st.delete(args.id):
        raise SystemExit(f"unknown id: {args.id}")
    print(f"deleted {args.id}")


def cmd_reset(args: argparse.Namespace) -> None:
    if not getattr(args, "yes", False):
        raise SystemExit("refusing reset without --yes")
    _store(args).clear()
    print("store cleared")


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

    p_init = sub.add_parser("init", help="Ensure data dir and empty JSON store exist")
    p_init.set_defaults(func=cmd_init)

    p_issue = sub.add_parser("issue-create", help="Create change at state issue")
    p_issue.add_argument("--title", required=True)
    p_issue.add_argument("--subject", default="")
    p_issue.add_argument("--flag", default="", help="optional linked SOIL flag id")
    p_issue.add_argument("--grove", default="", help="optional Grove channel hint")
    p_issue.add_argument("--kb-hint", default="", dest="kb_hint", help="optional KB seed hint")
    p_issue.add_argument("--fork", default="", help="optional fork id")
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
    p_adv.add_argument("--dry-run", action="store_true", help="print JSON preview; do not write")
    p_adv.set_defaults(func=cmd_advance)

    p_show = sub.add_parser("show", help="JSON dump of one change")
    p_show.add_argument("id")
    p_show.set_defaults(func=cmd_show)

    p_ls = sub.add_parser("list", help="List all changes")
    p_ls.add_argument("--long", action="store_true", help="include timestamps and hints")
    p_ls.add_argument("--json", action="store_true", help="JSON array of full records")
    p_ls.set_defaults(func=cmd_list)

    p_al = sub.add_parser("allowed", help="Show legal next states for a change")
    p_al.add_argument("id")
    p_al.set_defaults(func=cmd_allowed)

    p_rep = sub.add_parser("report", help="Markdown table of all changes (for Grove/paste)")
    p_rep.set_defaults(func=cmd_report)

    p_del = sub.add_parser("delete", help="Remove one change by id")
    p_del.add_argument("id")
    p_del.set_defaults(func=cmd_delete)

    p_rst = sub.add_parser("reset", help="Delete ALL changes in the store")
    p_rst.add_argument("--yes", action="store_true", required=True, help="required safety flag")
    p_rst.set_defaults(func=cmd_reset)

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
