"""
llm_edge.py — Model-agnostic LLM edge call.
b17: EDGE1  ΔΣ=42

Python handles all pipeline logic. The LLM only touches this edge:
  respond(system_prompt, context_atoms, input_text) → str

Provider-agnostic router (Ollama → Gemini → Groq 70b → fleet). See inference_router.py.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Optional

_GROQ_BASE = "https://api.groq.com/openai/v1"
_GROQ_MODEL = os.environ.get("WILLOW_EDGE_GROQ_MODEL", "llama-3.3-70b-versatile")
_OLLAMA_URL = "http://localhost:11434/api/generate"
_OLLAMA_MODEL = os.environ.get("WILLOW_EDGE_OLLAMA_MODEL", "llama3.2:3b")


def _format_atoms(atoms: list[dict]) -> str:
    parts = []
    for a in atoms:
        title = a.get("title", "(untitled)")
        summary = a.get("summary") or a.get("content", "")
        if isinstance(summary, dict):
            summary = json.dumps(summary)
        parts.append(f"— {title}: {str(summary)[:200]}")
    return "\n\n".join(parts)


def _groq(system: str, user: str) -> str:
    key = os.environ.get("GROQ_API_KEY") or os.environ.get("WILLOW_GROQ_API_KEY", "")
    if not key:
        raise RuntimeError("no groq key")
    body = json.dumps({
        "model": _GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        "max_tokens": 400,
        "temperature": 0.85,
    }).encode()
    req = urllib.request.Request(
        f"{_GROQ_BASE}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "willow/2.0",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["choices"][0]["message"]["content"].strip()


def _ollama(system: str, user: str, model: Optional[str] = None) -> str:
    prompt = f"{system}\n\n{user}"
    body = json.dumps({
        "model": model or _OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.85, "num_predict": 350},
    }).encode()
    req = urllib.request.Request(
        _OLLAMA_URL,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)["response"].strip()


def respond(
    system_prompt: str,
    context_atoms: list[dict],
    input_text: str,
    ollama_model: Optional[str] = None,
) -> str:
    """
    Core edge call. Python builds the context; this fires the LLM.

    Args:
        system_prompt:  The persona/instruction prompt (e.g. Saga's system prompt).
        context_atoms:  Pre-fetched KB atoms. Python already decided which ones.
        input_text:     The user content (journal entry, message, etc.).
        ollama_model:   Override the Ollama model for this call.

    Returns:
        The LLM's response string.
    """
    try:
        from core.inference_router import respond as _router_respond
        text, _provider = _router_respond(system_prompt, context_atoms, input_text)
        return text
    except Exception:
        pass

    atom_block = _format_atoms(context_atoms) if context_atoms else "(no case file)"
    user_msg = f"Input:\n{input_text}\n\nCase file:\n{atom_block}"
    try:
        return _groq(system_prompt, user_msg)
    except Exception:
        pass
    return _ollama(system_prompt, user_msg, model=ollama_model)
