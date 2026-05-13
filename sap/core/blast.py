# b17: E97E5  ΔΣ=42
"""
sap/core/blast.py
Blast-radius scanner — maps what an AI agent can reach from this machine.

Pure functions. No module-level I/O. Caller gathers findings; this module
only defines paths, scans, and summarises.

Hot-reloadable via willow_reload(target="blast").
"""
import os
import pathlib
import re

# ── DLP patterns ───────────────────────────────────────────────────────────────
# Credential regexes applied to env var values. Ordered from most-specific to
# least so the first match wins and we don't double-count.
_DLP_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("AWS Access Key ID",        re.compile(r"AKIA[0-9A-Z]{16}")),
    ("AWS Secret Access Key",    re.compile(r"(?i)aws.{0,20}secret.{0,20}['\"][0-9a-zA-Z/+]{40}['\"]")),
    ("GitHub Token",             re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("Anthropic API Key",        re.compile(r"sk-ant-[A-Za-z0-9\-_]{90,}")),
    ("OpenAI API Key",           re.compile(r"sk-[A-Za-z0-9]{48}")),
    ("Generic Bearer Token",     re.compile(r"(?i)bearer\s+[a-zA-Z0-9\-._~+/]{20,}")),
    ("Generic API Key (32+)",    re.compile(r"[a-zA-Z0-9\-_]{32,}")),
]

# ── Sensitive path definitions ─────────────────────────────────────────────────

def _build_sensitive_paths(home: str, cwd: str) -> list[dict]:
    """Return the list of sensitive paths to probe. Each dict has keys:
    full, label, description, score."""
    h = pathlib.Path(home)
    c = pathlib.Path(cwd)
    return [
        # SSH
        {"full": str(h / ".ssh" / "id_rsa"),      "label": "~/.ssh/id_rsa",      "description": "RSA private key — grants SSH access to your servers",      "score": 20},
        {"full": str(h / ".ssh" / "id_ed25519"),   "label": "~/.ssh/id_ed25519",  "description": "Ed25519 private key — grants SSH access to your servers",   "score": 20},
        {"full": str(h / ".ssh" / "id_ecdsa"),     "label": "~/.ssh/id_ecdsa",    "description": "ECDSA private key — grants SSH access to your servers",     "score": 20},
        # Cloud
        {"full": str(h / ".aws" / "credentials"),  "label": "~/.aws/credentials", "description": "AWS access keys — full cloud account access",               "score": 20},
        {"full": str(h / ".aws" / "config"),       "label": "~/.aws/config",      "description": "AWS configuration — account and region settings",           "score": 5},
        {"full": str(h / ".config" / "gcloud" / "credentials.db"), "label": "~/.config/gcloud/credentials.db", "description": "Google Cloud credentials", "score": 15},
        {"full": str(h / ".docker" / "config.json"), "label": "~/.docker/config.json", "description": "Docker registry auth tokens",                         "score": 10},
        # Auth files
        {"full": str(h / ".netrc"),                "label": "~/.netrc",           "description": "FTP/HTTP credentials in plain text",                        "score": 15},
        {"full": str(h / ".npmrc"),                "label": "~/.npmrc",           "description": "npm auth token — can publish packages as you",              "score": 10},
        # Willow sovereign stack
        {"full": str(h / ".willow" / "secrets" / ".willow_master.key"), "label": "~/.willow/secrets/.willow_master.key", "description": "Willow Fernet master key — decrypts all vault credentials", "score": 20},
        {"full": str(h / ".willow" / "secrets" / ".willow_creds.db"),   "label": "~/.willow/secrets/.willow_creds.db",   "description": "Willow encrypted credential vault (SQLite + Fernet)",        "score": 10},
        {"full": str(h / ".willow" / "secrets" / "credentials.json"),   "label": "~/.willow/secrets/credentials.json",   "description": "Willow plaintext credential fallback — API keys in clear text", "score": 15},
        # CWD secrets
        {"full": str(c / ".env"),                  "label": ".env (cwd)",         "description": "App secrets — database passwords, API keys",                "score": 20},
        {"full": str(c / ".env.local"),            "label": ".env.local (cwd)",   "description": "Local overrides — often contains real credentials",         "score": 15},
        {"full": str(c / ".env.production"),       "label": ".env.production (cwd)", "description": "Production secrets",                                    "score": 20},
    ]


# ── Core scan ──────────────────────────────────────────────────────────────────

def run_blast(home: str | None = None, cwd: str | None = None) -> dict:
    """Scan this machine for sensitive files and credential env vars.

    Returns:
        {
          "reachable": [{"full", "label", "description", "score"}, ...],
          "env_findings": [{"key", "pattern_name"}, ...],
          "score": int,   # 0-100, higher = cleaner
        }
    """
    home = home or str(pathlib.Path.home())
    cwd  = cwd  or os.getcwd()

    paths = _build_sensitive_paths(home, cwd)
    deduction = 0
    reachable: list[dict] = []

    for p in paths:
        try:
            f = pathlib.Path(p["full"])
            if f.exists() and os.access(p["full"], os.R_OK):
                reachable.append(p)
                deduction += p["score"]
        except Exception:
            pass

    env_findings: list[dict] = []
    for key, value in os.environ.items():
        if not value:
            continue
        for pattern_name, rx in _DLP_PATTERNS:
            if rx.search(value):
                env_findings.append({"key": key, "pattern_name": pattern_name})
                deduction += 10
                break  # one match per var

    return {
        "reachable": reachable,
        "env_findings": env_findings,
        "score": max(0, 100 - deduction),
    }


def _truncate_path(full: str) -> str:
    """Reduce a path to its trailing 2 segments for safe transmission."""
    if not full:
        return ""
    cleaned = full.rstrip("/\\")
    parts = [p for p in re.split(r"[/\\]+", cleaned) if p]
    if len(parts) <= 2:
        return cleaned
    return "/".join(parts[-2:])


def summarize_blast(result: dict, top_n: int = 5) -> dict:
    """Build a network-safe summary (no full paths, no env key names)."""
    reachable = result.get("reachable", [])
    env_findings = result.get("env_findings", [])
    sorted_paths = sorted(reachable, key=lambda p: (-p["score"], p["label"]))
    return {
        "score": result.get("score", 100),
        "exposure_count": len(reachable) + len(env_findings),
        "env_exposure_count": len(env_findings),
        "worst_paths": [
            {"path": _truncate_path(p["label"]), "score": p["score"]}
            for p in sorted_paths[:top_n]
        ],
    }
