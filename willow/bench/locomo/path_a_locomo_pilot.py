#!/usr/bin/env python3
"""Path A — LoCoMo pilot: one conversation through Willow Postgres KB.

Ingests LoCoMo observations into KB (project=willow/bench/locomo), runs
keyword retrieval per QA, scores recall@k / MRR (same metrics as mcp-memory-service).

Usage:
  python3 path_a_locomo_pilot.py --all --semantic          # full LoCoMo-10 smoke
  python3 path_a_locomo_pilot.py --all --from-conv-index 2 # resume LoCoMo-10 from conv 2
  python3 path_a_locomo_pilot.py --conv-index 0 --semantic
  python3 path_a_locomo_pilot.py --conv-index 0 --mode qa --llm mock

Outputs:
  external_runs/locomo_willow_<timestamp>.json
  external_runs/locomo_hypotheses_willow_<timestamp>.jsonl  (qa mode only)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

BENCH_DIR = Path(__file__).resolve().parent
WILLOW_ROOT = Path(os.environ.get("WILLOW_ROOT", str(BENCH_DIR.parent.parent.parent)))
LOCOMO_DATA = BENCH_DIR / "data" / "locomo" / "locomo10.json"
DOMAIN_ROOT = "willow/bench/locomo"


def _project(sample_id: str) -> str:
    return _memory_project(sample_id)

sys.path.insert(0, str(BENCH_DIR))
sys.path.insert(0, str(WILLOW_ROOT))

from locomo_dataset import LocomoConversation, load_dataset  # noqa: E402
from locomo_evaluator import (  # noqa: E402
    aggregate_results,
    mrr,
    precision_at_k,
    recall_at_k,
    token_f1,
)
from locomo_memory import (  # noqa: E402
    build_ingest_records,
    context_lines,
    project_id as _memory_project,
    search_kb as _search_kb_memory,
)

from core.pg_bridge import PgBridge  # noqa: E402

try:
    import psycopg2  # noqa: E402
except ImportError:
    psycopg2 = None  # type: ignore



def _atom_dia_refs(atom: dict) -> List[str]:
    refs: List[str] = []
    content = atom.get("content") or {}
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except json.JSONDecodeError:
            content = {}
    dia = content.get("dia_ref")
    if isinstance(dia, list):
        refs.extend(str(d) for d in dia if d)
    elif dia:
        for part in str(dia).split(","):
            part = part.strip()
            if part:
                refs.append(part)
    for kw in content.get("keywords") or []:
        if isinstance(kw, str) and kw.startswith("dia:"):
            refs.append(kw[4:])
    title = atom.get("title") or ""
    # title is sample_id:D1:3 — take segment after first colon only if it looks like D#
    if ":" in title:
        _, rest = title.split(":", 1)
        if rest and rest[0] in "Dd":
            refs.append(rest)
    return list(dict.fromkeys(refs))


def _match_kb_evidence(
    atoms: List[dict], evidence_ids: List[str]
) -> Tuple[List[str], Set[str]]:
    relevant = {f"ev_{dia}" for dia in evidence_ids}
    retrieved: List[str] = []
    for atom in atoms:
        matched = None
        for dia in _atom_dia_refs(atom):
            if dia in evidence_ids:
                matched = f"ev_{dia}"
                break
        retrieved.append(matched or f"irrelevant_{len(retrieved)}")
    return retrieved, relevant


def _project_atom_count(pg: PgBridge, project: str) -> int:
    pg._ensure_conn()
    with pg.conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM knowledge WHERE project = %s AND invalid_at IS NULL",
            (project,),
        )
        row = cur.fetchone()
        return int(row[0]) if row else 0


def _pg_transient(exc: BaseException) -> bool:
    if psycopg2 is not None and isinstance(
        exc, (psycopg2.OperationalError, psycopg2.InterfaceError)
    ):
        return True
    msg = str(exc).lower()
    return "server closed the connection" in msg or "connection already closed" in msg


def _knowledge_put_retry(pg: PgBridge, record: dict, max_attempts: int = 5) -> PgBridge:
    """Put with reconnect/backoff on transient Postgres failures."""
    last_exc: Optional[BaseException] = None
    for attempt in range(max_attempts):
        try:
            pg.knowledge_put(record)
            return pg
        except Exception as exc:
            if not _pg_transient(exc) or attempt >= max_attempts - 1:
                raise
            last_exc = exc
            wait = min(30, 2 ** attempt)
            print(
                f"  pg retry {attempt + 1}/{max_attempts} after {type(exc).__name__} "
                f"(sleep {wait}s)",
                flush=True,
            )
            time.sleep(wait)
            try:
                pg.conn.close()
            except Exception:
                pass
            pg = PgBridge()
    if last_exc:
        raise last_exc
    return pg


def ingest_conversation(
    pg: PgBridge,
    conv: LocomoConversation,
    *,
    skip_if_present: bool = True,
    force_ingest: bool = False,
    memory_profile: str = "v2",
) -> Tuple[int, PgBridge]:
    project = _project(conv.sample_id)
    records = build_ingest_records(conv, profile=memory_profile)
    expected = len(records)
    if skip_if_present and not force_ingest:
        existing = _project_atom_count(pg, project)
        if existing >= expected:
            print(f"Skip ingest ({existing} atoms already in {project})")
            return existing, pg
        if memory_profile == "v1" and existing >= max(1, expected - 25):
            print(
                f"Skip ingest ({existing}/{expected} atoms in {project}; "
                "close enough for QA resume)"
            )
            return existing, pg

    stored = 0
    for i, record in enumerate(records):
        pg = _knowledge_put_retry(pg, record)
        stored += 1
        if i and i % 50 == 0:
            print(f"  ingest progress: {i}/{expected}", flush=True)
    return stored, pg


def _search_kb(
    pg: PgBridge,
    question: str,
    sample_id: str,
    max_k: int,
    semantic: bool,
    conv: Optional[LocomoConversation] = None,
    memory_profile: str = "v2",
) -> List[dict]:
    return _search_kb_memory(
        pg,
        question,
        sample_id,
        max_k,
        semantic,
        conv=conv,
        profile=memory_profile,
    )


def evaluate_retrieval(
    pg: PgBridge,
    conv: LocomoConversation,
    top_k: List[int],
    semantic: bool,
    memory_profile: str = "v2",
) -> List[Dict]:
    max_k = max(top_k)
    per_question: List[Dict] = []
    for qa in conv.qa_pairs:
        if qa.category == "adversarial":
            continue
        atoms = _search_kb(
            pg, qa.question, conv.sample_id, max_k, semantic, conv, memory_profile
        )
        retrieved, relevant = _match_kb_evidence(atoms, qa.evidence)
        metrics: Dict = {
            "category": qa.category,
            "question": qa.question,
            "evidence": qa.evidence,
        }
        for k in top_k:
            metrics[f"recall_at_{k}"] = recall_at_k(retrieved, relevant, k)
            metrics[f"precision_at_{k}"] = precision_at_k(retrieved, relevant, k)
        metrics["mrr"] = mrr(retrieved, relevant)
        per_question.append(metrics)
    return per_question


async def evaluate_qa(
    pg: PgBridge,
    conv: LocomoConversation,
    top_k: List[int],
    llm: str,
    semantic: bool,
    llm_model: str = "",
    memory_profile: str = "v2",
    judge: str = "",
    judge_model: str = "",
) -> Tuple[List[Dict], List[Dict]]:
    from locomo_llm import create_adapter, create_judge

    max_k = max(top_k)
    adapter = create_adapter(llm, model=llm_model)
    judge_adapter = create_judge(judge, model=judge_model) if judge else None
    per_question: List[Dict] = []
    hypotheses: List[Dict] = []

    try:
        for i, qa in enumerate(conv.qa_pairs):
            if qa.category == "adversarial":
                continue
            if i and i % 20 == 0:
                print(f"  qa progress: {i}/{len(conv.qa_pairs)}", flush=True)
            atoms = _search_kb(
                pg, qa.question, conv.sample_id, max_k, semantic, conv, memory_profile
            )
            context = context_lines(atoms)
            predicted = await adapter.generate_answer(qa.question, context)
            retrieved, relevant = _match_kb_evidence(atoms, qa.evidence)
            f1 = token_f1(predicted, qa.answer)
            qid = f"{conv.sample_id}_{i}"
            metrics: Dict = {
                "category": qa.category,
                "question_id": qid,
                "token_f1": f1,
            }
            if judge_adapter is not None:
                correct = await judge_adapter.judge(
                    qa.question, qa.answer, predicted
                )
                metrics["judge_correct"] = 1.0 if correct else 0.0
            for k in top_k:
                metrics[f"recall_at_{k}"] = recall_at_k(retrieved, relevant, k)
                metrics[f"precision_at_{k}"] = precision_at_k(retrieved, relevant, k)
            metrics["mrr"] = mrr(retrieved, relevant)
            per_question.append(metrics)
            hypotheses.append({
                "question_id": qid,
                "question": qa.question,
                "hypothesis": predicted,
                "gold": qa.answer,
                "category": qa.category,
            })
    finally:
        sess = getattr(adapter, "_session", None)
        if sess is not None and not sess.closed:
            await sess.close()
    return per_question, hypotheses


def _run_one(
    pg: PgBridge,
    conv: LocomoConversation,
    conv_index: int,
    args: argparse.Namespace,
    use_semantic: bool,
    out_dir: Path,
    ts: str,
    hypotheses_out: Optional[Path],
) -> Tuple[dict, List[Dict]]:
    print(f"\n--- conv {conv_index}: {conv.sample_id} "
          f"({len(conv.observations)} obs, {len(conv.qa_pairs)} QA) ---")
    n, pg = ingest_conversation(
        pg,
        conv,
        skip_if_present=not args.force_ingest,
        force_ingest=args.force_ingest,
        memory_profile=args.memory_profile,
    )
    print(f"KB ready ({n} atoms, profile={args.memory_profile}) → {_project(conv.sample_id)}")

    if args.mode == "retrieval":
        per_q = evaluate_retrieval(
            pg, conv, args.top_k, use_semantic, args.memory_profile
        )
        hyps: List[Dict] = []
    else:
        llm_model = args.claude_model if args.llm == "claude" else (
            args.ollama_model if args.llm == "ollama" else ""
        )
        per_q, hyps = asyncio.run(
            evaluate_qa(
                pg, conv, args.top_k, args.llm, use_semantic, llm_model,
                args.memory_profile, args.judge, args.judge_model,
            )
        )
        if hypotheses_out is not None:
            with hypotheses_out.open("a", encoding="utf-8") as fh:
                for row in hyps:
                    fh.write(json.dumps(row) + "\n")

    result = aggregate_results(
        per_q,
        conversation_id=conv.sample_id,
        mode=args.mode,
        config={
            "backend": "willow_kb",
            "domain": _project(conv.sample_id),
            "conv_index": conv_index,
            "top_k": args.top_k,
            "semantic": use_semantic,
            "memory_profile": args.memory_profile,
            "llm": args.llm if args.mode == "qa" else None,
            "llm_model": (
                args.claude_model if args.llm == "claude" and args.claude_model
                else args.ollama_model if args.llm == "ollama"
                else None
            ) if args.mode == "qa" else None,
            "judge": (args.judge or None) if args.mode == "qa" else None,
            "judge_model": (
                (args.judge_model or None) if args.judge else None
            ) if args.mode == "qa" else None,
        },
    )
    for k, v in sorted(result.overall.items()):
        print(f"  {k}: {v:.4f}")
    row = {
        "conversation_id": conv.sample_id,
        "conv_index": conv_index,
        "observations": len(conv.observations),
        "questions_scored": len(per_q),
        "overall": result.overall,
        "by_category": result.by_category,
    }
    return row, per_q


def _load_merge_state(path: Path) -> Tuple[List[dict], List[Dict]]:
    """Load prior per_conversation rows + per-question metrics for resume merge."""
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = list(data.get("per_conversation") or [])
    per_q = list(data.get("per_question") or [])
    if not per_q and rows:
        print(
            f"Warning: {path} has no per_question — global scores will omit merged convs",
            file=sys.stderr,
        )
    return rows, per_q


def _run_indices(
    conversations: List[LocomoConversation],
    indices: List[int],
    args: argparse.Namespace,
    use_semantic: bool,
    out_dir: Path,
    ts: str,
    hyp_path: Optional[Path],
) -> Tuple[List[dict], List[Dict]]:
    """Run conversations — fresh Postgres connection per conv (survives PG restarts)."""
    per_conv_rows: List[dict] = []
    all_per_q: List[Dict] = []
    for idx in indices:
        with PgBridge() as pg:
            row, per_q = _run_one(
                pg, conversations[idx], idx, args, use_semantic, out_dir, ts, hyp_path
            )
        per_conv_rows.append(row)
        all_per_q.extend(per_q)
    return per_conv_rows, all_per_q


def main() -> int:
    parser = argparse.ArgumentParser(description="Path A LoCoMo pilot (Willow KB)")
    parser.add_argument("--conv-index", type=int, default=None, help="Single conversation 0-9")
    parser.add_argument("--all", action="store_true", help="Run all 10 LoCoMo conversations")
    parser.add_argument(
        "--from-conv-index",
        type=int,
        default=0,
        help="With --all: start at this conversation index (resume after crash)",
    )
    parser.add_argument(
        "--merge-json",
        default="",
        help="With --all + --from-conv-index: merge prior run artifact (needs per_question)",
    )
    parser.add_argument(
        "--merge-rebuild-prefix",
        action="store_true",
        help="With --from-conv-index>0: re-run QA for convs 0..N-1 before resuming (full locomo10)",
    )
    parser.add_argument(
        "--append-hypotheses",
        default="",
        help="qa mode: append hypotheses to this jsonl instead of creating a new file",
    )
    parser.add_argument(
        "--force-ingest",
        action="store_true",
        help="Re-ingest observations even when KB already has atoms for this conv",
    )
    parser.add_argument(
        "--memory-profile",
        choices=("v1", "v2"),
        default="v2",
        help="v2: dated atoms + session summaries + hybrid retrieval (default)",
    )
    parser.add_argument("--mode", choices=("retrieval", "qa"), default="retrieval")
    parser.add_argument("--top-k", type=int, nargs="+", default=[10])
    parser.add_argument("--semantic", action="store_true")
    parser.add_argument("--llm", default="mock", help="qa mode: mock|ollama|claude")
    parser.add_argument(
        "--ollama-model",
        default="llama3.2:3b",
        help="qa mode + --llm ollama: Ollama model tag",
    )
    parser.add_argument("--claude-model", default="", help="qa mode + --llm claude: model id")
    parser.add_argument(
        "--judge",
        default="",
        help="qa mode: LLM-as-judge scorer (e.g. 'claude') for same-ruler accuracy; "
        "off by default (token_f1 only)",
    )
    parser.add_argument(
        "--judge-model",
        default="",
        help="qa mode + --judge: judge model id (default: ClaudeJudge default)",
    )
    parser.add_argument("--data-path", default=str(LOCOMO_DATA))
    args = parser.parse_args()

    if not args.all and args.conv_index is None:
        args.conv_index = 0
    if args.all and args.conv_index is not None:
        print("Use --all alone, or --conv-index alone (not both)")
        return 1
    if not args.all and args.from_conv_index:
        print("--from-conv-index requires --all")
        return 1
    if args.merge_json and not args.all:
        print("--merge-json requires --all")
        return 1
    if args.judge and args.mode != "qa":
        print("--judge requires --mode qa")
        return 1

    data_path = Path(args.data_path)
    data_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading LoCoMo from {data_path} ...", flush=True)
    if args.all and args.from_conv_index:
        print(
            f"=== LoCoMo QA run {datetime.now(timezone.utc).isoformat()} "
            f"(from conv {args.from_conv_index}) ===",
            flush=True,
        )
    conversations = load_dataset(str(data_path))
    n_conv = len(conversations)

    if args.all:
        start = max(0, args.from_conv_index)
        if start >= n_conv:
            print(f"--from-conv-index must be 0..{n_conv - 1}")
            return 1
        indices = list(range(start, n_conv))
        if start:
            print(f"Resuming LoCoMo-10 from conv index {start} ({len(indices)} conversations)")
    else:
        if args.conv_index < 0 or args.conv_index >= n_conv:
            print(f"conv-index must be 0..{n_conv - 1}")
            return 1
        indices = [args.conv_index]

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = BENCH_DIR / "external_runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    use_semantic = args.semantic or args.mode == "qa"
    if args.all and not args.semantic and args.mode == "retrieval":
        use_semantic = True  # full smoke uses semantic by default

    hyp_path: Optional[Path] = None
    if args.mode == "qa":
        if args.append_hypotheses:
            hyp_path = Path(args.append_hypotheses)
            hyp_path.parent.mkdir(parents=True, exist_ok=True)
            if not hyp_path.exists():
                hyp_path.write_text("", encoding="utf-8")
        else:
            hyp_path = out_dir / f"locomo_hypotheses_willow_{ts}.jsonl"
            hyp_path.write_text("", encoding="utf-8")

    per_conv_rows: List[dict] = []
    all_per_q: List[Dict] = []

    if args.merge_json:
        merge_path = Path(args.merge_json)
        if not merge_path.is_file():
            print(f"merge-json not found: {merge_path}")
            return 1
        merged_rows, merged_per_q = _load_merge_state(merge_path)
        per_conv_rows.extend(merged_rows)
        all_per_q.extend(merged_per_q)
        print(f"Merged {len(merged_rows)} conversations from {merge_path}")

    if args.merge_rebuild_prefix and args.all and args.from_conv_index > 0:
        prefix = list(range(0, args.from_conv_index))
        print(f"Rebuilding prefix conversations {prefix} for merged locomo10 scores ...")
        prefix_rows, prefix_per_q = _run_indices(
            conversations, prefix, args, use_semantic, out_dir, ts, hyp_path
        )
        # Replace any overlap from merge-json with fresh prefix rows
        skip_ids = {r["conversation_id"] for r in prefix_rows}
        per_conv_rows = [r for r in per_conv_rows if r["conversation_id"] not in skip_ids]
        all_per_q = [
            q for q in all_per_q
            if not any(
                str(q.get("question_id", "")).startswith(f"{sid}_")
                for sid in skip_ids
            )
        ]
        per_conv_rows = sorted(
            per_conv_rows + prefix_rows,
            key=lambda r: r.get("conv_index", 0),
        )
        all_per_q.extend(prefix_per_q)

    run_rows, run_per_q = _run_indices(
        conversations, indices, args, use_semantic, out_dir, ts, hyp_path
    )
    per_conv_rows.extend(run_rows)
    all_per_q.extend(run_per_q)

    llm_model = None
    if args.mode == "qa":
        llm_model = (
            args.claude_model if args.llm == "claude" and args.claude_model
            else args.ollama_model if args.llm == "ollama"
            else None
        )

    global_result = aggregate_results(
        all_per_q,
        conversation_id="all" if args.all else per_conv_rows[0]["conversation_id"],
        mode=args.mode,
        config={
            "backend": "willow_kb",
            "domain_root": DOMAIN_ROOT,
            "conversations": len(per_conv_rows),
            "from_conv_index": args.from_conv_index if args.all else None,
            "top_k": args.top_k,
            "semantic": use_semantic,
            "llm": args.llm if args.mode == "qa" else None,
            "llm_model": llm_model,
        },
    )

    suffix = "locomo10" if args.all else per_conv_rows[0]["conversation_id"]
    payload = {
        "benchmark": "LoCoMo",
        "path": "A",
        "timestamp": ts,
        "mode": args.mode,
        "overall": global_result.overall,
        "by_category": global_result.by_category,
        "by_conversation": {r["conversation_id"]: r["overall"] for r in per_conv_rows},
        "per_conversation": per_conv_rows,
        "per_question": all_per_q,
        "config": global_result.config,
        "questions_scored": len(all_per_q),
    }
    out_path = out_dir / f"locomo_willow_{suffix}_{ts}.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"\n=== Global ({args.mode}, n={len(all_per_q)} questions) ===")
    for k, v in sorted(global_result.overall.items()):
        print(f"  {k}: {v:.4f}")
    print(f"\nWrote {out_path}")
    if hyp_path and hyp_path.exists():
        print(f"Wrote {hyp_path}")
    if args.all and args.mode in ("retrieval", "qa"):
        try:
            import subprocess
            rec = subprocess.run(
                [
                    sys.executable,
                    str(BENCH_DIR / "benchmark_record_path_a_baseline.py"),
                    "--run-json", str(out_path),
                ],
                capture_output=True,
                text=True,
                cwd=str(BENCH_DIR),
            )
            if rec.returncode == 0:
                print(rec.stdout.strip())
            else:
                print("benchmark_record_path_a_baseline.py failed:", rec.stderr or rec.stdout)
        except Exception as exc:
            print(f"Could not record baseline row: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
