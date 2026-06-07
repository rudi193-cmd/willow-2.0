"""
voice_drafter.py — Generate reply drafts in the author's voice.
b17: UPST1  ΔΣ=42

Input:  thread bundle (from analyzer) + voice profile
Output: draft_body string

Never posts. Draft stored in SOIL; human must approve before anything goes out.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.insert(0, _ROOT)

from core.llm_edge import respond
from core import soil
from willow.fylgja.willow_home import willow_home

_VOICE_FILE = willow_home(Path(__file__).resolve().parents[4]) / "upstream_steward" / "voice.md"
_GH_AUTHOR = "rudi193-cmd"

_SOIL_VOICE = "upstream_steward/voice"
_VOICE_DEFAULTS = {
    "style": "Direct. Genuine. Match their energy.",
    "no_bullets": True,
    "no_em_dash": True,
    "no_salutation": True,
    "no_sign_off": True,
    "terse_if_samples_are_terse": True,
}

_SYSTEM_TEMPLATE = """\
You are drafting a GitHub reply in the exact voice of {author}.

Here are real examples of how {author} actually writes on GitHub — match this register precisely:

{samples}

Voice notes:
{voice_profile}

Rules:
- Match the LENGTH and REGISTER of the samples above. If samples are terse, be terse.
- Start with the substance. No salutation line, no "Hi," no "Thanks for the review,".
- If there's something genuinely interesting or clever in their comment, name it specifically.
- Commitments go in prose, not bullet points.
- Answer questions directly and briefly.
- If they offered to help (PR, review, etc.), accept naturally or explain why not.
- Do NOT end with "let me know if you have questions" or any cliché sign-off.
- NEVER use em dashes (—). Use a comma, period, or reword instead.
- Output ONLY the reply body. Nothing else.\
"""


def _fetch_gh_comment_samples(limit: int = 6) -> list[str]:
    """Pull recent GitHub comments by the author as voice samples."""
    try:
        result = subprocess.run(
            ["gh", "api", f"/users/{_GH_AUTHOR}/events?per_page=100"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            return []
        events = json.loads(result.stdout)
        samples = []
        for ev in events:
            if ev.get("type") not in ("IssueCommentEvent", "PullRequestReviewCommentEvent", "PullRequestReviewEvent"):
                continue
            payload = ev.get("payload", {})
            comment = payload.get("comment") or payload.get("review") or {}
            body = (comment.get("body") or "").strip()
            # Skip empty, bot-like, or very long comments
            if not body or len(body) < 20 or len(body) > 1200:
                continue
            # Skip if it looks like a template or auto-generated form
            if body.startswith("<!--"):
                continue
            samples.append(body)
            if len(samples) >= limit:
                break
        return samples
    except Exception:
        return []


def _load_voice() -> str:
    """Load voice profile from SOIL (JSONB), seeding from flat file on first run."""
    record = soil.get(_SOIL_VOICE, "profile")
    if record:
        return record.get("style", _VOICE_DEFAULTS["style"])
    # First run: seed SOIL from flat file if present, else use defaults
    if _VOICE_FILE.exists():
        style = _VOICE_FILE.read_text().strip()
    else:
        style = _VOICE_DEFAULTS["style"]
    profile = {**_VOICE_DEFAULTS, "style": style}
    soil.put(_SOIL_VOICE, "profile", profile)
    return style


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
    samples = _fetch_gh_comment_samples()
    if samples:
        samples_block = "\n\n".join(f'  "{s}"' for s in samples)
    else:
        samples_block = "  (no prior comment samples available yet)"
    system = _SYSTEM_TEMPLATE.format(
        author=_GH_AUTHOR,
        samples=samples_block,
        voice_profile=voice_profile,
    )

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
