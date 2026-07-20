"""
global_settings.py — Fleet-wide settings (canonical in private willow-config).

Canonical: `$WILLOW_HOME/settings.global.json` (`~/github/.willow`; `~/.willow` alias OK).
`willow-2.0/willow/fylgja/config/settings.global.json` symlinks in via `link_fleet_home`.
Legacy `~/.willow/consent.json` is imported on first load and kept in sync on write.
"""
from __future__ import annotations

import argparse
import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from willow.fylgja.willow_home import fleet_home

VERSION = 1

WILLOW_HOME = fleet_home()
SETTINGS_PATH = Path(
    os.environ.get("WILLOW_SETTINGS_GLOBAL", WILLOW_HOME / "settings.global.json")
)
CONSENT_LEGACY_PATH = WILLOW_HOME / "consent.json"

CONSENT_KEYS = ("internet", "cloud_llm", "lan")
# B-31 (willow-mcp docs/BUGS.md): consent FAILS CLOSED. A fresh install, a
# missing consent block, or a malformed one is DENIED until the operator grants
# each channel explicitly. The egress gate (core/egress_authority.py) already
# reads with `is True` strictness; these defaults make the general reader and
# the settings writer agree with the enforced semantic instead of inverting it.
DEFAULT_CONSENT: dict[str, bool] = {
    "internet": False,
    "cloud_llm": False,
    "lan": False,
}

# Fleet feature flags (enabled=false until implemented)
FLAG_CONSENT_INTERNET_GATES_ALLOW_NET = "consent_internet_gates_allow_net"

DEFAULT_FLAGS: dict[str, dict[str, Any]] = {
    FLAG_CONSENT_INTERNET_GATES_ALLOW_NET: {
        "enabled": False,
        "implemented": False,
        "status": "deferred",
        "targets": ["kart_worker", "kart_sandbox", "sap_gate"],
        "note": (
            "Wire settings.global.json consent.internet to kart # allow_net "
            "and SAP network approval before bwrap grants outbound access."
        ),
    },
}


def _home() -> Path:
    return Path.home()


def _default_paths() -> dict[str, str]:
    home = _home()
    willow_root = os.environ.get("WILLOW_ROOT", "").strip()
    if not willow_root:
        for candidate in (
            home / "willow-2.0",
            home / "github" / "willow-2.0",
        ):
            if (candidate / "willow.sh").is_file() or (candidate / "willow" / "fylgja").is_dir():
                willow_root = str(candidate)
                break
    grove_root = os.environ.get("GROVE_ROOT", "").strip()
    if not grove_root:
        candidate = home / "github" / "safe-app-willow-grove"
        if candidate.is_dir():
            grove_root = str(candidate)
    safe_root = os.environ.get("WILLOW_SAFE_ROOT", "").strip()
    if not safe_root:
        candidate = home / "github" / "SAFE" / "Applications"
        if candidate.is_dir():
            safe_root = str(candidate)
    return {
        "willow_root": willow_root,
        "grove_root": grove_root,
        "safe_root": safe_root,
    }


def default_settings() -> dict[str, Any]:
    return {
        "version": VERSION,
        "consent": dict(DEFAULT_CONSENT),
        "paths": _default_paths(),
        # Optional UI hint only — does NOT override WILLOW_AGENT_NAME or agent_route
        "fleet": {"default_agent": ""},
        "flags": deepcopy(DEFAULT_FLAGS),
    }


def _normalize_flags(raw: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict):
        return deepcopy(DEFAULT_FLAGS)
    out = deepcopy(DEFAULT_FLAGS)
    for flag_id, default_spec in DEFAULT_FLAGS.items():
        entry = raw.get(flag_id)
        if not isinstance(entry, dict):
            continue
        merged = deepcopy(default_spec)
        if "enabled" in entry:
            merged["enabled"] = bool(entry["enabled"])
        if "implemented" in entry:
            merged["implemented"] = bool(entry["implemented"])
        if isinstance(entry.get("status"), str):
            merged["status"] = entry["status"]
        if isinstance(entry.get("note"), str):
            merged["note"] = entry["note"]
        out[flag_id] = merged
    return out


def get_flag(flag_id: str, *, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    data = settings if settings is not None else load_global_settings(create=False)
    flags = data.get("flags") if isinstance(data.get("flags"), dict) else {}
    spec = flags.get(flag_id)
    if isinstance(spec, dict):
        return deepcopy(spec)
    return deepcopy(DEFAULT_FLAGS.get(flag_id, {}))


def flag_enabled(flag_id: str, *, settings: dict[str, Any] | None = None) -> bool:
    """True only when the flag is explicitly enabled and marked implemented."""
    spec = get_flag(flag_id, settings=settings)
    return bool(spec.get("enabled")) and bool(spec.get("implemented"))


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, val in overlay.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def _normalize_consent(raw: Any) -> dict[str, bool]:
    """Fail-closed normalization (B-31): only a literal JSON ``true`` grants.

    A non-dict block, a missing key, or a truthy-but-not-True value
    (``"true"``, ``1``, ``"yes"``) all normalize to denied — the same
    strictness as ``core.egress_authority`` and willow-mcp's consent reader.
    """
    if not isinstance(raw, dict):
        return dict(DEFAULT_CONSENT)
    return {k: raw.get(k) is True for k in CONSENT_KEYS}


def _read_legacy_consent(path: Path | None = None) -> dict[str, bool] | None:
    path = path or CONSENT_LEGACY_PATH
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    # Flat legacy file: {"internet": true, ...}
    if "consent" not in data and any(k in data for k in CONSENT_KEYS):
        return _normalize_consent(data)
    if isinstance(data.get("consent"), dict):
        return _normalize_consent(data["consent"])
    return None


def _parse_settings_file(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def load_global_settings(
    *,
    path: Path | None = None,
    create: bool = True,
) -> dict[str, Any]:
    """Load fleet settings, merging defaults. Optionally create from legacy consent."""
    path = path or SETTINGS_PATH
    defaults = default_settings()
    raw = _parse_settings_file(path)
    if raw is None:
        legacy = _read_legacy_consent()
        if legacy is not None:
            merged = _deep_merge(defaults, {"consent": legacy})
            if create:
                save_global_settings(merged, path=path, sync_legacy=True)
            return merged
        if create:
            save_global_settings(defaults, path=path, sync_legacy=True)
        return deepcopy(defaults)

    version = raw.get("version", VERSION)
    if not isinstance(version, int):
        version = VERSION
    merged = _deep_merge(defaults, raw)
    merged["version"] = version
    merged["consent"] = _normalize_consent(merged.get("consent"))
    if not isinstance(merged.get("paths"), dict):
        merged["paths"] = defaults["paths"]
    if not isinstance(merged.get("fleet"), dict):
        merged["fleet"] = defaults["fleet"]
    merged["flags"] = _normalize_flags(merged.get("flags"))
    return merged


def save_global_settings(
    data: dict[str, Any],
    *,
    path: Path | None = None,
    sync_legacy: bool = True,
) -> None:
    path = path or SETTINGS_PATH
    """Atomic write of settings.global.json; optionally mirror consent to consent.json."""
    path.parent.mkdir(parents=True, exist_ok=True)
    out = _deep_merge(default_settings(), data)
    out["version"] = int(out.get("version", VERSION))
    out["consent"] = _normalize_consent(out.get("consent"))
    out["flags"] = _normalize_flags(out.get("flags"))
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    if sync_legacy:
        _write_legacy_consent(out["consent"])


def _write_legacy_consent(consent: dict[str, bool], path: Path | None = None) -> None:
    path = path or CONSENT_LEGACY_PATH
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(consent, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
    except Exception:
        pass


def read_consent(*, path: Path | None = None) -> dict[str, bool]:
    """Consent toggles for dashboard and gates. Never raises."""
    path = path or SETTINGS_PATH
    try:
        if path.is_file():
            return dict(load_global_settings(path=path, create=False)["consent"])
        if path.resolve() == SETTINGS_PATH.resolve():
            return dict(load_global_settings(path=path, create=True)["consent"])
        return dict(DEFAULT_CONSENT)
    except Exception:
        legacy = _read_legacy_consent()
        return legacy if legacy is not None else dict(DEFAULT_CONSENT)


def write_consent(consent: dict[str, bool], *, path: Path | None = None) -> None:
    """Update consent section; keeps other settings.global keys intact."""
    path = path or SETTINGS_PATH
    try:
        settings = load_global_settings(path=path, create=True)
        settings["consent"] = _normalize_consent(consent)
        save_global_settings(settings, path=path, sync_legacy=True)
    except Exception:
        pass


def get_path(key: str, *, settings: dict[str, Any] | None = None) -> str:
    data = settings if settings is not None else load_global_settings()
    paths = data.get("paths") if isinstance(data.get("paths"), dict) else {}
    val = paths.get(key, "")
    return val if isinstance(val, str) else ""


def init_global_settings(
    *,
    path: Path | None = None,
    default_agent: str = "",
    force: bool = False,
) -> Path:
    path = path or SETTINGS_PATH
    """Create or refresh ~/.willow/settings.global.json from defaults + legacy consent."""
    if path.is_file() and not force:
        load_global_settings(path=path, create=False)
        return path
    data = default_settings()
    if default_agent.strip():
        data["fleet"]["default_agent"] = default_agent.strip()
    legacy = _read_legacy_consent()
    if legacy is not None:
        data["consent"] = legacy
    save_global_settings(data, path=path, sync_legacy=True)
    return path


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Willow fleet global settings")
    parser.add_argument(
        "--init",
        action="store_true",
        help="Create ~/.willow/settings.global.json if missing (imports consent.json)",
    )
    parser.add_argument("--force", action="store_true", help="With --init, overwrite existing file")
    parser.add_argument("--agent", default="", help="Set fleet.default_agent")
    parser.add_argument("--print", action="store_true", help="Print current settings JSON")
    args = parser.parse_args()
    if args.init:
        p = init_global_settings(default_agent=args.agent, force=args.force)
        print(p)
    if args.print or not args.init:
        print(json.dumps(load_global_settings(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
