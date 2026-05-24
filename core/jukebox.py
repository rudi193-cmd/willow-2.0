"""
jukebox.py — Semantic Jukebox
==============================
You describe a mood. It searches your KB. A guy named Noir tells you what he found.

Pipeline:
  text → embed → KB search → LLM narrates → optional Kokoro TTS

b17: JUKE1  ΔΣ=42
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from typing import Optional

_GROQ_BASE  = "https://api.groq.com/openai/v1"
_GROQ_MODEL = os.environ.get("WILLOW_JUKEBOX_GROQ_MODEL", "llama-3.3-70b-versatile")
_OLLAMA_URL = "http://localhost:11434/api/generate"
_OLLAMA_MODEL = os.environ.get("WILLOW_JUKEBOX_OLLAMA_MODEL", "llama3.1:8b")
_KOKORO_URL = os.environ.get("WILLOW_KOKORO_URL", "http://localhost:5000/v1/audio/speech")
_KOKORO_VOICE = os.environ.get("WILLOW_KOKORO_VOICE", "am_michael")

_NOIR_SYSTEM = """\
You are a hard-boiled noir detective narrating a case. The case is the user's own life, \
memories, and knowledge — pulled from their personal knowledge base. You speak in tight, \
evocative sentences. You find the hidden connections. You name the pattern before you \
prove it. You are never warm, but you are never cruel. The facts matter. The silences \
between facts matter more.

Rules:
- 150–250 words. Not a word more.
- Open with a single punchy line that frames the whole thing.
- Reference 2–3 specific details from the atoms provided — real titles, real phrases.
- Find one connection the user probably hasn't noticed.
- End on something that sits with them.
- Never say "knowledge base", "atoms", "KB", or "embedding". You found this in the \
  case file. That's all they need to know."""

_NOIR_PROMPT = """\
The mood: {mood}

Case file entries retrieved:
{atoms}

Narrate the case."""


def _groq_chat(messages: list[dict]) -> str:
    key = os.environ.get("GROQ_API_KEY") or os.environ.get("WILLOW_GROQ_API_KEY", "")
    if not key:
        raise RuntimeError("no groq key")
    body = json.dumps({
        "model": _GROQ_MODEL,
        "messages": messages,
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


def _ollama_generate(prompt: str) -> str:
    body = json.dumps({
        "model": _OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.85, "num_predict": 280},
    }).encode()
    req = urllib.request.Request(
        _OLLAMA_URL,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)["response"].strip()


def _narrate(mood: str, atoms: list[dict]) -> str:
    atom_text = "\n\n".join(
        f"— {a.get('title', '(untitled)')}: {a.get('summary', '')[:200]}"
        for a in atoms
    )
    user_msg = _NOIR_PROMPT.format(mood=mood, atoms=atom_text)

    # Try Groq first
    try:
        return _groq_chat([
            {"role": "system", "content": _NOIR_SYSTEM},
            {"role": "user",   "content": user_msg},
        ])
    except Exception:
        pass

    # Ollama fallback
    full_prompt = f"{_NOIR_SYSTEM}\n\n{user_msg}"
    return _ollama_generate(full_prompt)


def _speak(text: str, output_path: str = "/tmp/jukebox_out.wav") -> Optional[str]:
    """Send text to Kokoro TTS server. Returns path or None if unavailable."""
    try:
        body = json.dumps({
            "input": text,
            "voice": _KOKORO_VOICE,
            "response_format": "wav",
        }).encode()
        req = urllib.request.Request(
            _KOKORO_URL,
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            audio = r.read()
        with open(output_path, "wb") as f:
            f.write(audio)
        return output_path
    except Exception:
        return None


def segment(mood: str, n: int = 8, speak: bool = False) -> dict:
    """
    Full pipeline: mood → KB search → narration → optional TTS.
    Returns {mood, atoms, script, audio_path}.
    """
    from core.pg_bridge import PgBridge
    pg = PgBridge()
    try:
        atoms = pg.knowledge_search_semantic(mood, limit=n)
    finally:
        pg.close()

    if not atoms:
        return {
            "mood": mood,
            "atoms": [],
            "script": "Nothing in the file. The city was quiet tonight. Too quiet.",
            "audio_path": None,
        }

    script = _narrate(mood, atoms)

    audio_path = None
    if speak:
        audio_path = _speak(script)

    return {
        "mood": mood,
        "atoms": atoms,
        "script": script,
        "audio_path": audio_path,
    }
