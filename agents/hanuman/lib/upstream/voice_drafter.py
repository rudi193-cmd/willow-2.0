"""
voice_drafter.py — Generate reply drafts in the author's voice.
b17: UPST1  ΔΣ=42

Input:  thread bundle (from analyzer) + voice profile
Output: draft_body string

Never posts. Draft stored in SOIL; human must approve before anything goes out.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.insert(0, _ROOT)

from core.llm_edge import respond

_VOICE_FILE = Path.home() / ".willow" / "upstream_steward" / "voice.md"

_SYSTEM_TEMPLATE = """\
You are drafting a GitHub reply in the voice of the repository author.

Voice profile:
{voice_profile}

Rules:
- 2–5 sentences. Warm but not gushing.
- Open with genuine thanks or acknowledgement of their specific point — not a numbered list.
- Name the interesting/smart part of their comment if there is one.
- Weave in any concrete commitments as natural prose, not bullet points.
- If they asked a question, answer it directly and briefly.
- If they offered to help (PR, review, etc.), accept warmly or explain why not.
- End with an invitation or a held thought — not a sign-off cliche.
- Match their register: casual comment → casual reply; technical review → technical but human reply.
- Write as the author. First person. No "I hope this reply finds you well."
- Do NOT include a salutation line — start with the substance.
- Output ONLY the reply body. No preamble, no "Here's a draft:", no quotes.\
"""


def _load_voice() -> str:
    if _VOICE_FILE.exists():
        return _VOICE_FILE.read_text().strip()
    return "Be genuine, warm, direct. No bullet lists. Match the commenter's energy."


def _build_context_atoms(bundle: dict) -> list[dict]:
    atoms = []
    if bundle.get("fun_bits"):
        atoms.append({
            "title": "Fun / notable bits in their comment",
            "content": " | ".join(bundle["fun_bits"]),
        })
    if bundle.get("open_questions"):
        atoms.append({
            "title": "Open questions to address",
            "content": " | ".join(bundle["open_questions"]),
        })
    if bundle.get("ci_state") and bundle["ci_state"] not in ("n/a", "unknown"):
        atoms.append({
            "title": "CI / merge state",
            "content": f"CI: {bundle['ci_state']}, mergeable: {bundle.get('mergeable', 'unknown')}",
        })
    return atoms


def draft(pending: dict) -> str:
    """
    Generate a reply draft for a pending work item.

    pending must have: their_comment, title, repo, kind
    Returns draft body string (empty string on failure).
    """
    their_comment = (pending.get("their_comment") or "").strip()
    if not their_comment:
        return ""

    voice_profile = _load_voice()
    system = _SYSTEM_TEMPLATE.format(voice_profile=voice_profile)

    author = pending.get("author", "them")
    repo = pending.get("repo", "")
    title = pending.get("title", "")
    fun_bits = pending.get("fun_bits", [])
    questions = pending.get("open_questions", [])

    prompt_parts = [
        f"Repo: {repo}",
        f"Thread: {title}",
        f"Their comment (@{author}):\n{their_comment}",
    ]
    if fun_bits:
        prompt_parts.append("Notable: " + "; ".join(fun_bits))
    if questions:
        prompt_parts.append("Questions they raised: " + "; ".join(questions))

    prompt = "\n\n".join(prompt_parts)
    atoms = _build_context_atoms(pending)

    try:
        return respond(system, atoms, prompt)
    except Exception as exc:
        print(f"voice_drafter: llm error — {exc}", file=sys.stderr, flush=True)
        return ""


if __name__ == "__main__":
    import json
    # Quick test: pipe a JSON pending record
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            rec = json.load(f)
    else:
        rec = json.loads(sys.stdin.read())
    result = draft(rec)
    print(result)
