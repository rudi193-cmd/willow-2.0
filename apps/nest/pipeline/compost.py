"""
pipeline/compost.py — Summarize a file and write a KB atom.
b17: B2DA2  ΔΣ=42

Fleet routing priority: Groq → Cerebras → Ollama local → skip.
Summary is written to files/store record (nest_status → composted).
"""

import json
import os
import sys
from pathlib import Path

# PDF text extraction (optional)
try:
    import pdfminer.high_level as _pdf
    _PDF_OK = True
except ImportError:
    _PDF_OK = False

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.nest.store_bridge import update_status, get_record

CREDENTIALS_FILE = Path(os.environ.get(
    "WILLOW_CREDENTIALS",
    str(Path.home() / "github" / "willow-1.9" / "credentials.json"),
))

MAX_CHARS = 6000
SUMMARY_PROMPT = (
    "Summarize the following document in 3–5 sentences. "
    "Capture the main topic, key facts, and any named entities. "
    "Be terse. Do not editorialize.\n\n"
)


def _load_creds() -> dict:
    if CREDENTIALS_FILE.exists():
        return json.loads(CREDENTIALS_FILE.read_text())
    return {}


def _read_text(path: Path) -> str | None:
    ext = path.suffix.lower()
    if ext == ".pdf":
        if not _PDF_OK:
            return None
        try:
            import io
            buf = io.StringIO()
            _pdf.extract_text_to_fp(open(path, "rb"), buf)
            return buf.getvalue()[:MAX_CHARS]
        except Exception:
            return None
    try:
        return path.read_text(errors="replace")[:MAX_CHARS]
    except Exception:
        return None


def _call_groq(prompt: str, creds: dict) -> str | None:
    key = creds.get("GROQ_API_KEY") or creds.get("GROQ_API_KEY_1")
    if not key:
        return None
    try:
        import urllib.request
        payload = json.dumps({
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 256,
        }).encode()
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def _call_ollama(prompt: str) -> str | None:
    try:
        import urllib.request
        payload = json.dumps({
            "model": "yggdrasil:v9",
            "prompt": prompt,
            "stream": False,
        }).encode()
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())["response"].strip()
    except Exception:
        return None


def run(b17: str) -> dict:
    """
    Summarize the file associated with b17. Updates store record to 'composted'.
    Returns {"b17": ..., "summary": ..., "provider": ..., "status": ...}.
    """
    record = get_record(b17)
    if not record:
        return {"error": f"no record for b17={b17}"}

    path = Path(record.get("moved_to") or record.get("path", ""))
    if not path.exists():
        return {"error": f"file not found: {path}"}

    text = _read_text(path)
    if not text or not text.strip():
        update_status(b17, "composted", {"summary": "[no extractable text]", "provider": "none"})
        return {"b17": b17, "summary": "[no extractable text]", "provider": "none", "status": "composted"}

    prompt = SUMMARY_PROMPT + text

    creds = _load_creds()
    summary = _call_groq(prompt, creds)
    provider = "groq"

    if not summary:
        summary = _call_ollama(prompt)
        provider = "ollama"

    if not summary:
        summary = f"[compost failed — manual review needed] {path.name}"
        provider = "none"

    update_status(b17, "composted", {"summary": summary, "provider": provider})
    return {"b17": b17, "summary": summary, "provider": provider, "status": "composted"}
