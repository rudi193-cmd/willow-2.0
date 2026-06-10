"""
ratatosk doctor / explain / panic

Makes setup failures obvious and gives an emergency stop.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ratatosk import ollama
from ratatosk.protocol.envelope import clear_nonce_cache
from ratatosk.traces import explain_trace
from ratatosk.transport.config import _CONFIG_PATH, _TOKEN_PATH, load_transport_config
from ratatosk.transport.grove_client import GroveClient

_PANIC_FILE = Path.home() / ".ratatosk" / "panic.json"


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


@dataclass
class DoctorReport:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail} for c in self.checks],
        }


def _check_transport() -> CheckResult:
    cfg = load_transport_config()
    issues = cfg.issues()
    if issues:
        return CheckResult("transport", False, "; ".join(issues))
    return CheckResult("transport", True, f"mode={cfg.mode} url={cfg.grove_url}")


def _check_grove() -> CheckResult:
    client = GroveClient()
    ok, detail = client.ping()
    return CheckResult("grove", ok, detail)


def _check_ollama() -> CheckResult:
    if ollama.is_available():
        models = ollama.list_models()
        return CheckResult("ollama", True, f"models={len(models)} url={ollama.OLLAMA_URL}")
    return CheckResult("ollama", False, f"unreachable at {ollama.OLLAMA_URL}")


def _check_tailscale() -> CheckResult:
    if shutil.which("tailscale") is None:
        return CheckResult("tailscale", True, "not installed (optional)")
    try:
        out = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode != 0:
            return CheckResult("tailscale", False, out.stderr.strip() or "status failed")
        data = json.loads(out.stdout or "{}")
        backend = data.get("BackendState", "unknown")
        return CheckResult("tailscale", backend == "Running", f"backend={backend}")
    except Exception as exc:
        return CheckResult("tailscale", False, str(exc))


def _check_termux_plugins() -> CheckResult:
    termux = shutil.which("termux-info")
    if not termux:
        return CheckResult("termux", True, "not on Termux (skipped)")
    plugins = []
    for name in ("termux-gui", "termux-api", "termux-boot", "termux-widget"):
        plugins.append(f"{name}={'yes' if shutil.which(name) else 'no'}")
    return CheckResult("termux", True, " ".join(plugins))


def _check_panic_state() -> CheckResult:
    if _PANIC_FILE.exists():
        try:
            data = json.loads(_PANIC_FILE.read_text(encoding="utf-8"))
            return CheckResult("panic", False, f"active since {data.get('at', '?')}")
        except Exception:
            return CheckResult("panic", False, "panic file present")
    return CheckResult("panic", True, "inactive")


def run_doctor() -> DoctorReport:
    report = DoctorReport(
        checks=[
            _check_panic_state(),
            _check_transport(),
            _check_grove(),
            _check_ollama(),
            _check_tailscale(),
            _check_termux_plugins(),
        ]
    )
    return report


def explain(trace_id: str) -> dict[str, Any]:
    rows = explain_trace(trace_id)
    return {"trace_id": trace_id, "events": rows, "found": bool(rows)}


def panic(note: str = "operator panic") -> dict[str, Any]:
    _PANIC_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "note": note,
        "actions": [
            "stop listeners",
            "clear nonce cache",
            "revoke grove token manually",
            "disable public adapters",
        ],
    }
    _PANIC_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    clear_nonce_cache()
    # Best-effort: mark config public_exposure off
    os.environ["RATATOSK_PUBLIC_EXPOSURE"] = "0"
    if _CONFIG_PATH.exists():
        try:
            cfg = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            cfg["public_exposure"] = False
            _CONFIG_PATH.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        except Exception:
            pass
    return {"panic": True, "file": str(_PANIC_FILE), "token_path": str(_TOKEN_PATH)}


def clear_panic() -> None:
    if _PANIC_FILE.exists():
        _PANIC_FILE.unlink()
