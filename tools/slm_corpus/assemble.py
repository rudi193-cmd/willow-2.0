#!/usr/bin/env python3
"""assemble.py — merge harvested inputs + gold outputs into training files.

Reads from the corpus dir:
    inputs.jsonl            harvested task inputs (harvest.py)
    gold/*.jsonl            gold outputs: {"id": ..., "output": "..."}
    baseline/*.jsonl        local-model outputs: {"id", "output", "model"}

Writes:
    sft_train.jsonl / sft_val.jsonl   chat-format SFT records
    dpo.jsonl                          preference pairs (gold vs failing baseline)
    stats.json                         per-task counts + validation failures

SFT record:
    {"messages": [...system/user..., {"role": "assistant", "content": gold}],
     "meta": {"id", "task_type", "source"}}

DPO record:
    {"messages": [...system/user...], "chosen": gold, "rejected": baseline,
     "meta": {"id", "task_type", "reject_reason", "baseline_model"}}

Split is deterministic by record id hash (default 5% val).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.slm_corpus.harvest import corpus_dir  # noqa: E402
from tools.slm_corpus.templates import (  # noqa: E402
    build_messages,
    canonicalize_output,
    validate_output,
)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _read_dir(d: Path) -> dict[str, dict]:
    """Merge all JSONL files in a directory, keyed by record id (last wins)."""
    merged: dict[str, dict] = {}
    if not d.is_dir():
        return merged
    for path in sorted(d.glob("*.jsonl")):
        for rec in _read_jsonl(path):
            rid = rec.get("id")
            if rid:
                merged[rid] = rec
    return merged


def _is_val(rid: str, val_pct: int) -> bool:
    return int(hashlib.sha1(rid.encode()).hexdigest(), 16) % 100 < val_pct


def main() -> int:
    ap = argparse.ArgumentParser(description="Assemble SLM corpus training files")
    ap.add_argument("--dir", default="", help="corpus dir override")
    ap.add_argument("--val-pct", type=int, default=5)
    args = ap.parse_args()

    base = Path(args.dir).expanduser() if args.dir else corpus_dir()
    inputs = {r["id"]: r for r in _read_jsonl(base / "inputs.jsonl")}
    gold = _read_dir(base / "gold")
    baseline = _read_dir(base / "baseline")

    stats: dict = {
        "inputs": len(inputs), "gold": len(gold), "baseline": len(baseline),
        "sft": defaultdict(int), "dpo": defaultdict(int),
        "gold_invalid": defaultdict(int), "gold_orphaned": 0,
    }

    sft_train, sft_val, dpo = [], [], []

    for rid, grec in gold.items():
        rec = inputs.get(rid)
        if rec is None:
            stats["gold_orphaned"] += 1
            continue
        task, payload = rec["task_type"], rec["payload"]
        output = grec.get("output", "")
        ok, reason = validate_output(task, payload, output)
        if not ok:
            stats["gold_invalid"][f"{task}: {reason}"] += 1
            continue
        canonical = canonicalize_output(task, output)
        messages = build_messages(task, payload)
        entry = {
            "messages": messages + [{"role": "assistant", "content": canonical}],
            "meta": {"id": rid, "task_type": task, "source": rec.get("source", {})},
        }
        (sft_val if _is_val(rid, args.val_pct) else sft_train).append(entry)
        stats["sft"][task] += 1

        brec = baseline.get(rid)
        if brec:
            b_out = brec.get("output", "")
            b_ok, b_reason = validate_output(task, payload, b_out)
            # A pair is informative when the baseline fails the contract
            # outright, or when the grader marked it rejected.
            rejected = (not b_ok) or brec.get("graded_reject", False)
            if rejected and b_out.strip() and b_out.strip() != canonical:
                dpo.append({
                    "messages": messages,
                    "chosen": canonical,
                    "rejected": b_out,
                    "meta": {"id": rid, "task_type": task,
                             "reject_reason": b_reason or brec.get("grade_reason", ""),
                             "baseline_model": brec.get("model", "")},
                })
                stats["dpo"][task] += 1

    def _write(name: str, rows: list[dict]) -> None:
        with (base / name).open("w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    _write("sft_train.jsonl", sft_train)
    _write("sft_val.jsonl", sft_val)
    _write("dpo.jsonl", dpo)

    stats["sft"] = dict(stats["sft"])
    stats["dpo"] = dict(stats["dpo"])
    stats["gold_invalid"] = dict(stats["gold_invalid"])
    stats["sft_train"] = len(sft_train)
    stats["sft_val"] = len(sft_val)
    stats["dpo_total"] = len(dpo)
    (base / "stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
