#!/usr/bin/env python3
# b17: E5783  ΔΣ=42
"""
session_quality_scorer.py — Score each session on completion, correction, and carry-over rates.

Answers: is working with agents getting better over time?

Metrics per session:
  - completion_rate: tasks completed / tasks mentioned
  - correction_count: number of correction signals in session
  - carryover_count: "next session / tomorrow / follow up" mentions
  - sean_directive_ratio: Sean directing vs. agents acting autonomously (estimated)
  - quality_score: weighted composite (0.0–1.0)

Output: ~/.willow/session_quality_report.json
        ~/.willow/session_quality_trend.json  (30-day rolling avg)
"""
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.pg_bridge import PgBridge

TASK_MENTION = re.compile(
    r"\b(todo|task|need to|should|must|will|going to|plan to|next step|action item)\b", re.I
)
TASK_COMPLETE = re.compile(
    r"\b(done|complete|completed|merged|shipped|fixed|closed|deployed|ratified|landed)\b", re.I
)
CORRECTION_SIGNAL = re.compile(
    r"\b(no,|wrong|you missed|that'?s not|stop doing|don'?t again|you got stupid|not what i|go back|still projecting|how many times)\b",
    re.I,
)
CARRYOVER_SIGNAL = re.compile(
    r"\b(next session|next time|tomorrow|follow up|pick up|carry over|deferred|not tonight)\b", re.I
)
DIRECTIVE = re.compile(
    r"\b(do this|build|write|check|find|tell me|show me|run|fix|create|update|delete)\b", re.I
)


def score_session(title: str, body: str) -> dict:
    if not body:
        return None

    lines = body.split("\n")

    task_mentions = sum(1 for l in lines if TASK_MENTION.search(l))
    task_completes = sum(1 for l in lines if TASK_COMPLETE.search(l))
    corrections = sum(1 for l in lines if CORRECTION_SIGNAL.search(l))
    carryovers = sum(1 for l in lines if CARRYOVER_SIGNAL.search(l))
    directives = sum(1 for l in lines if DIRECTIVE.search(l))

    completion_rate = task_completes / max(task_mentions, 1)
    # Penalty for corrections (normalized to 0-1, cap at 10)
    correction_penalty = min(corrections / 10.0, 1.0)
    # Penalty for carry-overs (normalized, cap at 5)
    carryover_penalty = min(carryovers / 5.0, 1.0)

    quality_score = (
        completion_rate * 0.45
        + (1 - correction_penalty) * 0.30
        + (1 - carryover_penalty) * 0.25
    )
    quality_score = round(min(max(quality_score, 0.0), 1.0), 4)

    return {
        "title": title,
        "task_mentions": task_mentions,
        "task_completes": task_completes,
        "completion_rate": round(completion_rate, 3),
        "corrections": corrections,
        "carryovers": carryovers,
        "directives": directives,
        "quality_score": quality_score,
    }


def compute_trend(scored: list[dict], window_days: int = 30) -> list[dict]:
    dated = [s for s in scored if s.get("date")]
    dated.sort(key=lambda x: x["date"])

    if not dated:
        return []

    trend = []
    dates = sorted({s["date"][:10] for s in dated})
    for i, day in enumerate(dates):
        # Rolling window
        start = (datetime.fromisoformat(day) - timedelta(days=window_days)).isoformat()[:10]
        window = [s for s in dated if start <= s["date"][:10] <= day]
        if not window:
            continue
        avg_q = sum(s["quality_score"] for s in window) / len(window)
        avg_completion = sum(s["completion_rate"] for s in window) / len(window)
        trend.append({
            "date": day,
            "rolling_avg_quality": round(avg_q, 4),
            "rolling_avg_completion": round(avg_completion, 4),
            "sessions_in_window": len(window),
        })

    return trend


def main():
    pg = PgBridge()
    with pg.conn.cursor() as cur:
        cur.execute(
            """SELECT id, title, summary, created_at FROM public.knowledge
               WHERE project = 'sessions' AND source_type = 'session'
               ORDER BY created_at"""
        )
        rows = cur.fetchall()

    print(f"Scoring {len(rows)} sessions...")

    scored = []
    for atom_id, title, body, created_at in rows:
        s = score_session(title or "", body or "")
        if s is None:
            continue
        s["atom_id"] = atom_id
        s["date"] = created_at.isoformat() if created_at else None
        scored.append(s)

    scored.sort(key=lambda x: x.get("date") or "")

    out_report = Path("/home/sean-campbell/.willow/session_quality_report.json")
    with open(out_report, "w") as f:
        json.dump(scored, f, indent=2)

    trend = compute_trend(scored)
    out_trend = Path("/home/sean-campbell/.willow/session_quality_trend.json")
    with open(out_trend, "w") as f:
        json.dump(trend, f, indent=2)

    if scored:
        all_avg = sum(s["quality_score"] for s in scored) / len(scored)
        recent = scored[-20:]
        recent_avg = sum(s["quality_score"] for s in recent) / len(recent)
        best = max(scored, key=lambda x: x["quality_score"])
        worst = min(scored, key=lambda x: x["quality_score"])

        print(f"\nAll-time avg quality:  {all_avg:.4f}")
        print(f"Last 20 sessions avg:  {recent_avg:.4f}  ({'↑ improving' if recent_avg > all_avg else '↓ declining'})")
        print(f"Best session:  {best['quality_score']:.4f}  — {best['title'][:60]}")
        print(f"Worst session: {worst['quality_score']:.4f}  — {worst['title'][:60]}")

        if trend:
            first_q = trend[0]["rolling_avg_quality"]
            last_q = trend[-1]["rolling_avg_quality"]
            delta = last_q - first_q
            print(f"Trend arc: {first_q:.4f} → {last_q:.4f}  (Δ {delta:+.4f})")

    print(f"\nQuality report → {out_report}")
    print(f"Trend report   → {out_trend}")


if __name__ == "__main__":
    main()
