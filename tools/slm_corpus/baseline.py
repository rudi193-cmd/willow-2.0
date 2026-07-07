#!/usr/bin/env python3
"""baseline.py — run local Ollama models over harvested inputs.

Produces baseline/<model>.jsonl records ({"id", "output", "model"}) used by
assemble.py to build DPO preference pairs (gold chosen, failing baseline
rejected). Run under Kart with allow_localhost=True.

Usage:
    python3 tools/slm_corpus/baseline.py --model mistral:7b --limit 200
    python3 tools/slm_corpus/baseline.py --model llama3.2:3b --task stop_summary
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.slm_corpus.harvest import corpus_dir  # noqa: E402
from tools.slm_corpus.templates import build_messages  # noqa: E402

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"

# Production model per task (provenance in templates.py). Tasks not listed
# default to mistral:7b.
TASK_MODEL = {
    "stop_summary": "llama3.2:3b",
    "dream_tension": "llama3.2:3b",
    "drift_verdict": "llama3.2:3b",
    "drift_redraft": "llama3.2:3b",
}


def _chat(model: str, messages: list[dict], timeout: int = 180) -> str:
    payload = json.dumps({"model": model, "messages": messages,
                          "stream": False}).encode()
    req = urllib.request.Request(
        OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read())
    return (body.get("message") or {}).get("content", "")


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate local-model baselines")
    ap.add_argument("--model", default="",
                    help="force one model; default = production model per task")
    ap.add_argument("--task", default="", help="restrict to one task type")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--dir", default="", help="corpus dir override")
    args = ap.parse_args()

    base = Path(args.dir).expanduser() if args.dir else corpus_dir()
    out_dir = base / "baseline"
    out_dir.mkdir(parents=True, exist_ok=True)

    done: set[str] = set()
    for path in out_dir.glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line)["id"])
            except (json.JSONDecodeError, KeyError):
                continue

    n = 0
    inputs_path = base / "inputs.jsonl"
    if not inputs_path.exists():
        print("no inputs.jsonl — run harvest.py first", file=sys.stderr)
        return 2

    out_name = (args.model or "per-task").replace(":", "_").replace("/", "_")
    out_path = out_dir / f"{out_name}.jsonl"
    with out_path.open("a", encoding="utf-8") as fh:
        for line in inputs_path.read_text(encoding="utf-8").splitlines():
            if n >= args.limit:
                break
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec["id"] in done:
                continue
            if args.task and rec["task_type"] != args.task:
                continue
            model = args.model or TASK_MODEL.get(rec["task_type"], "mistral:7b")
            try:
                messages = build_messages(rec["task_type"], rec["payload"])
                output = _chat(model, messages)
            except Exception as e:
                print(f"[{rec['id']}] {e}", file=sys.stderr)
                continue
            fh.write(json.dumps({"id": rec["id"], "output": output,
                                 "model": model}, ensure_ascii=False) + "\n")
            fh.flush()
            n += 1
            if n % 20 == 0:
                print(f"{n} done")

    print(f"wrote {n} baseline outputs to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
