# core/embedder.py
import re
import time
import requests

OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL = "nomic-embed-text"
TIMEOUT_S = 10
_RETRIES = 2
_RETRY_DELAY_S = 2
MAX_CHARS = 4_000      # conservative limit — progress-bar/tokenizer content can hit 0.5 chars/token
MAX_CHARS_CJK = 1_500  # safe for CJK (~1500 tokens at 1 char/token)
MAX_BYTES = 16_000     # nomic-embed-text hard byte limit (conservative)

_CJK_RE = re.compile(
    "[　-鿿豈-﫿︰-﹏]"
)


def _truncate(text: str) -> str:
    """Apply tighter char limit for high-Unicode text to stay within token context.

    CJK and box-drawing/progress-bar Unicode are 3 bytes each in UTF-8.
    6000 chars of those = 18KB, which exceeds nomic-embed-text's context.
    Two guards:
      1. CJK density > 10% -> apply CJK char limit
      2. Encoded byte length > MAX_BYTES -> truncate by bytes
    """
    candidate = text[:MAX_CHARS]
    if len(candidate) > 0 and len(_CJK_RE.findall(candidate)) / len(candidate) > 0.10:
        return text[:MAX_CHARS_CJK]
    encoded = candidate.encode("utf-8")
    if len(encoded) > MAX_BYTES:
        return encoded[:MAX_BYTES].decode("utf-8", errors="ignore")
    return candidate


def embed(text: str) -> list[float] | None:
    text = _truncate(text)
    for attempt in range(_RETRIES):
        try:
            resp = requests.post(
                OLLAMA_URL,
                json={"model": MODEL, "prompt": text},
                timeout=TIMEOUT_S,
            )
            resp.raise_for_status()
            return resp.json()["embedding"]
        except requests.exceptions.ConnectionError:
            # Service not running — don't retry, return immediately.
            return None
        except Exception:
            if attempt < _RETRIES - 1:
                time.sleep(_RETRY_DELAY_S)
    return None
