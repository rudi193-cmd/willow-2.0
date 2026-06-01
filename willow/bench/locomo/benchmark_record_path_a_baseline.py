"""Record a Path-A full-run result as a baseline row in baselines.jsonl."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

BENCH_DIR = pathlib.Path(__file__).parent
BASELINES_FILE = BENCH_DIR / "baselines.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a Path-A baseline row.")
    parser.add_argument("--run-json", required=True, help="Path to the run output JSON.")
    args = parser.parse_args()

    run_path = pathlib.Path(args.run_json)
    if not run_path.exists():
        print(f"ERROR: run-json not found: {run_path}", file=sys.stderr)
        return 1

    with open(run_path, encoding="utf-8") as fh:
        data = json.load(fh)

    overall = data.get("overall", {})
    config = data.get("config", {})

    row = {
        "timestamp": data.get("timestamp", ""),
        "run_file": run_path.name,
        "model": config.get("llm_model", ""),
        "backend": config.get("backend", ""),
        "top_k": config.get("top_k", []),
        "memory_profile": config.get("memory_profile", ""),
        "conversations": config.get("conversations", 0),
        "questions_scored": data.get("questions_scored", 0),
        "token_f1": round(overall.get("token_f1", 0), 6),
        "recall_at_10": round(overall.get("recall_at_10", overall.get("recall_at_5", 0)), 6),
        "precision_at_10": round(overall.get("precision_at_10", overall.get("precision_at_5", 0)), 6),
        "mrr": round(overall.get("mrr", 0), 6),
        "by_category": {
            cat: {k: round(v, 6) for k, v in metrics.items()}
            for cat, metrics in data.get("by_category", {}).items()
        },
    }

    with open(BASELINES_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")

    print(
        f"Recorded baseline: token_f1={row['token_f1']:.4f}"
        f"  recall={row['recall_at_10']:.4f}"
        f"  mrr={row['mrr']:.4f}"
        f"  → {BASELINES_FILE.name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
