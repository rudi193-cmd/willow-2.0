"""
inference_router.py — Provider-agnostic LLM edge (CLI/model agnostic).

Priority (WILLOW_INFERENCE_PROVIDER):
  local  → Ollama only
  cloud  → Gemini → Groq (70b) → OpenRouter-compatible fleet keys
  auto   → Ollama, then cloud chain

No Anthropic required. Any OpenAI-compatible or Gemini REST key works.
b17: INFR1 · ΔΣ=42
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Callable, Optional

_GROQ_BASE = "https://api.groq.com/openai/v1"
_GROQ_MODEL = os.environ.get(
    "WILLOW_EDGE_GROQ_MODEL",
    os.environ.get("WILLOW_GROQ_MODEL", "llama-3.3-70b-versatile"),
)
_GEMINI_MODEL = os.environ.get("WILLOW_GEMINI_MODEL", "gemini-2.0-flash")
_OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
_OLLAMA_MODEL = os.environ.get("WILLOW_OLLAMA_MODEL", "qwen2.5:3b")


def _load_key(*names: str) -> str:
    for name in names:
        val = os.environ.get(name, "").strip()
        if val:
            return val
    try:
        from sap.core.inference import load_credential
        for name in names:
            val = load_credential(name) or ""
            if val:
                return val.strip()
    except Exception:
        pass
    return ""


def _openai_chat(
    url: str,
    model: str,
    key: str,
    system: str,
    user: str,
    *,
    provider: str,
    extra_headers: Optional[dict[str, str]] = None,
) -> Optional[str]:
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": int(os.environ.get("WILLOW_INFERENCE_MAX_TOKENS", "2048")),
        "temperature": float(os.environ.get("WILLOW_INFERENCE_TEMPERATURE", "0.7")),
    }).encode()
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "User-Agent": "willow/2.0",
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(f"{url.rstrip('/')}/chat/completions", data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=int(os.environ.get("WILLOW_INFERENCE_TIMEOUT", "120"))) as r:
        data = json.load(r)
        return data["choices"][0]["message"]["content"].strip()


def _try_ollama(system: str, user: str) -> Optional[str]:
    model = os.environ.get("WILLOW_INFERENCE_OLLAMA_MODEL", _OLLAMA_MODEL)
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        f"{_OLLAMA_URL.rstrip('/')}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=int(os.environ.get("WILLOW_INFERENCE_TIMEOUT", "300"))) as r:
        data = json.load(r)
        return (data.get("message") or {}).get("content", "").strip() or None


def _try_gemini(system: str, user: str) -> Optional[str]:
    key = _load_key("GEMINI_API_KEY", "GOOGLE_API_KEY")
    if not key:
        return None
    model = _GEMINI_MODEL
    body = json.dumps({
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
    }).encode()
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        f"?key={key}"
    )
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=int(os.environ.get("WILLOW_INFERENCE_TIMEOUT", "120"))) as r:
        data = json.load(r)
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
        return text.strip() or None


def _try_groq(system: str, user: str) -> Optional[str]:
    key = _load_key("GROQ_API_KEY", "WILLOW_GROQ_API_KEY")
    if not key:
        return None
    return _openai_chat(_GROQ_BASE, _GROQ_MODEL, key, system, user, provider="groq")


def _try_openrouter(system: str, user: str) -> Optional[str]:
    key = _load_key("OPENROUTER_API_KEY")
    if not key:
        return None
    model = os.environ.get("WILLOW_OPENROUTER_MODEL", "openai/gpt-4o-mini")
    return _openai_chat(
        "https://openrouter.ai/api/v1",
        model,
        key,
        system,
        user,
        provider="openrouter",
        extra_headers={"HTTP-Referer": "https://willow.local"},
    )


def _try_fleet(system: str, user: str) -> Optional[str]:
    try:
        from sap.clients.professor_client import _ask_fleet
        return _ask_fleet(system, user)
    except Exception:
        return None


def _chain(mode: str) -> list[tuple[str, Callable[[str, str], Optional[str]]]]:
    local = [("ollama", _try_ollama)]
    cloud = [
        ("gemini", _try_gemini),
        ("groq", _try_groq),
        ("openrouter", _try_openrouter),
        ("fleet", _try_fleet),
    ]
    m = (mode or "auto").strip().lower()
    if m == "local":
        return local
    if m == "cloud":
        return cloud
    return local + cloud


def chat(system: str, user: str, *, mode: Optional[str] = None) -> tuple[str, str]:
    """
    Returns (response_text, provider_used). Raises RuntimeError if all backends fail.
    """
    errors: list[str] = []
    for name, fn in _chain(mode or os.environ.get("WILLOW_INFERENCE_PROVIDER", "auto")):
        try:
            out = fn(system, user)
            if out:
                return out, name
        except Exception as e:
            errors.append(f"{name}:{e}")
    raise RuntimeError("inference unavailable: " + "; ".join(errors[:4]))


def respond(system_prompt: str, context_atoms: list[dict], input_text: str) -> tuple[str, str]:
    """Same shape as llm_edge.respond but returns provider label."""
    parts = []
    for a in context_atoms or []:
        title = a.get("title", "(untitled)")
        summary = a.get("summary") or a.get("content", "")
        if isinstance(summary, dict):
            summary = json.dumps(summary)
        parts.append(f"— {title}: {str(summary)[:200]}")
    atom_block = "\n\n".join(parts) if parts else "(no case file)"
    user_msg = f"Input:\n{input_text}\n\nCase file:\n{atom_block}"
    return chat(system_prompt, user_msg)
