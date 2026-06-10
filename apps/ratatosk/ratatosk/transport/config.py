"""
Tailnet-first transport configuration.

Default: private tailnet Grove URL. Optional adapters: ngrok, cloudflare,
pangolin, funnel — never hardcoded as the only path.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

TransportMode = Literal["tailnet", "ngrok", "cloudflare", "pangolin", "funnel"]

_PLACEHOLDERS = {"INSERT_NGROK_URL_HERE", "INSERT_GROVE_TOKEN_HERE", ""}

try:
    from willow.fylgja.willow_home import willow_home as _willow_home
except Exception:  # pragma: no cover - standalone Termux install fallback
    _willow_home = None


def fleet_home() -> Path:
    """Use Willow's canonical fleet home when available; fallback for standalone Termux."""
    if _willow_home is not None:
        return _willow_home()
    if os.environ.get("WILLOW_HOME"):
        return Path(os.environ["WILLOW_HOME"]).expanduser().resolve()
    return Path.home() / ".ratatosk"


def config_path() -> Path:
    return Path.home() / ".ratatosk" / "config.json"


def token_path() -> Path:
    return fleet_home() / "grove_token"


@dataclass
class TransportConfig:
    mode: TransportMode
    grove_url: str
    grove_token: str
    agent_name: str
    public_exposure: bool
    tailnet_url: str
    ngrok_url: str
    cloudflare_url: str
    pangolin_url: str
    funnel_url: str

    def issues(self) -> list[str]:
        out: list[str] = []
        if not self.grove_url or self.grove_url in _PLACEHOLDERS:
            out.append("GROVE_URL not configured")
        if not self.grove_url.startswith(("http://", "https://")):
            out.append(f"invalid GROVE_URL: {self.grove_url!r}")
        if not self.grove_token or self.grove_token in _PLACEHOLDERS:
            out.append("GROVE_TOKEN not configured")
        if self.public_exposure and self.mode == "tailnet":
            out.append("public exposure enabled but transport mode is tailnet")
        if self.mode != "tailnet" and not self.public_exposure:
            out.append(
                f"transport mode {self.mode} is a public relay — set RATATOSK_PUBLIC_EXPOSURE=1"
            )
        return out


def _read_token() -> str:
    env = os.environ.get("GROVE_TOKEN", "").strip()
    if env and env not in _PLACEHOLDERS:
        return env
    path = token_path()
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


def _read_file_config() -> dict:
    path = config_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def load_transport_config() -> TransportConfig:
    file_cfg = _read_file_config()
    mode: TransportMode = (
        os.environ.get("RATATOSK_TRANSPORT")
        or file_cfg.get("transport")
        or "tailnet"
    ).lower()  # type: ignore[assignment]

    tailnet = (
        os.environ.get("RATATOSK_GROVE_TAILNET_URL")
        or file_cfg.get("grove_tailnet_url")
        or ""
    ).rstrip("/")
    ngrok = (os.environ.get("RATATOSK_GROVE_NGROK_URL") or file_cfg.get("grove_ngrok_url") or "").rstrip("/")
    cloudflare = (
        os.environ.get("RATATOSK_GROVE_CLOUDFLARE_URL")
        or file_cfg.get("grove_cloudflare_url")
        or ""
    ).rstrip("/")
    pangolin = (
        os.environ.get("RATATOSK_GROVE_PANGOLIN_URL")
        or file_cfg.get("grove_pangolin_url")
        or ""
    ).rstrip("/")
    funnel = (
        os.environ.get("RATATOSK_GROVE_FUNNEL_URL")
        or file_cfg.get("grove_funnel_url")
        or ""
    ).rstrip("/")

    explicit = (os.environ.get("GROVE_URL") or file_cfg.get("grove_url") or "").rstrip("/")
    public = os.environ.get("RATATOSK_PUBLIC_EXPOSURE", file_cfg.get("public_exposure", "0")) in (
        "1",
        "true",
        "yes",
    )

    url_by_mode = {
        "tailnet": tailnet,
        "ngrok": ngrok,
        "cloudflare": cloudflare,
        "pangolin": pangolin,
        "funnel": funnel,
    }
    grove_url = explicit or url_by_mode.get(mode, "") or tailnet

    return TransportConfig(
        mode=mode,
        grove_url=grove_url,
        grove_token=_read_token(),
        agent_name=os.environ.get("WILLOW_AGENT_NAME", file_cfg.get("agent_name", "ratatosk")),
        public_exposure=public,
        tailnet_url=tailnet,
        ngrok_url=ngrok,
        cloudflare_url=cloudflare,
        pangolin_url=pangolin,
        funnel_url=funnel,
    )


def save_transport_config(cfg: TransportConfig) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "transport": cfg.mode,
        "grove_url": cfg.grove_url,
        "grove_tailnet_url": cfg.tailnet_url,
        "grove_ngrok_url": cfg.ngrok_url,
        "grove_cloudflare_url": cfg.cloudflare_url,
        "grove_pangolin_url": cfg.pangolin_url,
        "grove_funnel_url": cfg.funnel_url,
        "agent_name": cfg.agent_name,
        "public_exposure": cfg.public_exposure,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path
