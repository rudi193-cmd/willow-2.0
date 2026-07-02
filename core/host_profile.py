"""Read-only host hardware probe for INDEX and fleet_status."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from willow.fylgja.willow_home import fleet_home


def _read_dmi(field: str) -> str:
    path = Path(f"/sys/class/dmi/id/{field}")
    try:
        return path.read_text().strip()
    except Exception:
        return ""


def _cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return ""


def _cpu_threads() -> int:
    try:
        return Path("/proc/cpuinfo").read_text().count("processor\t")
    except Exception:
        return 0


def _meminfo_kb() -> dict[str, int]:
    out: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, _, val = line.partition(":")
            if key.strip() in ("MemTotal", "MemAvailable", "SwapTotal"):
                out[key.strip()] = int(val.strip().split()[0])
    except Exception:
        pass
    return out


def _kb_to_gib(kb: int) -> float:
    return round(kb / 1024 / 1024, 1)


def _ollama_gpu_state() -> bool | None:
    """Where Ollama's loaded models run: True = GPU (fully or split),
    False = CPU only, None = nothing loaded right now (idle) or `ollama ps`
    unavailable. Ollama unloads models after a few idle minutes, so idle is
    the common case at boot — report unknown, not a false negative."""
    try:
        proc = subprocess.run(
            ["ollama", "ps"], capture_output=True, text=True, timeout=5
        )
        if proc.returncode != 0:
            return None
        rows = [ln for ln in (proc.stdout or "").strip().splitlines()[1:] if ln.strip()]
        if not rows:
            return None
        return any("gpu" in row.lower() for row in rows)
    except Exception:
        return None


def _nvidia_probe() -> dict:
    result: dict = {
        "available": False,
        "name": "",
        "driver": "",
        "vram_mib": None,
        "cuda": "",
        "ollama_on_gpu": None,
    }
    try:
        proc = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode != 0:
            return result
        line = (proc.stdout or "").strip().splitlines()[0]
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3:
            result["available"] = True
            result["name"] = parts[0]
            result["driver"] = parts[1]
            m = re.search(r"(\d+)", parts[2])
            if m:
                result["vram_mib"] = int(m.group(1))
        ver = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if ver.returncode == 0:
            cm = re.search(r"CUDA Version:\s*([\d.]+)", ver.stdout or "")
            if cm:
                result["cuda"] = cm.group(1)
        state = _ollama_gpu_state()
        if state is None and "ollama" in (ver.stdout or "").lower():
            # ollama ps idle/unavailable but nvidia-smi sees an ollama process
            state = True
        result["ollama_on_gpu"] = state
    except Exception:
        pass
    return result


def probe_host() -> dict:
    """Ground-truth host snapshot from /proc, DMI, and nvidia-smi."""
    mem = _meminfo_kb()
    total_kb = mem.get("MemTotal", 0)
    avail_kb = mem.get("MemAvailable", 0)
    swap_kb = mem.get("SwapTotal", 0)
    nvidia = _nvidia_probe()
    threads = _cpu_threads()
    cores = max(threads // 2, 1) if threads else 0

    gpu_short = ""
    if nvidia.get("available"):
        name = nvidia.get("name") or "NVIDIA"
        gpu_short = name.replace("NVIDIA ", "", 1) if name.startswith("NVIDIA ") else name
    elif (Path("/sys/class/drm").exists()):
        gpu_short = "iGPU"

    return {
        "hostname": Path("/etc/hostname").read_text().strip()
        if Path("/etc/hostname").exists()
        else "",
        "product": _read_dmi("product_name"),
        "vendor": _read_dmi("sys_vendor"),
        "cpu_model": _cpu_model(),
        "cpu_cores": cores,
        "cpu_threads": threads,
        "ram_total_kb": total_kb,
        "ram_total_gib": _kb_to_gib(total_kb),
        "ram_available_gib": _kb_to_gib(avail_kb),
        "swap_gib": _kb_to_gib(swap_kb),
        "gpu_short": gpu_short,
        "nvidia": nvidia,
    }


def load_host_profile() -> dict:
    """Live probe merged with operator-verified fleet cache (installed RAM, etc.)."""
    profile = probe_host()
    cache_path = fleet_home() / "host_profile.json"
    if cache_path.is_file():
        try:
            cached = json.loads(cache_path.read_text())
            for key, val in cached.items():
                if val is not None and key not in profile:
                    profile[key] = val
                elif key in ("ram_installed_gib", "ram_dimm_layout", "kb_atom_id", "verified_at"):
                    profile[key] = val
        except Exception:
            pass
    return profile


def index_hardware_parts(profile: dict | None = None) -> tuple[list[str], dict]:
    """Compact INDEX tokens + full profile dict for memory.json sidecar."""
    p = profile or load_host_profile()
    parts: list[str] = []

    if p.get("ram_total_gib"):
        installed = p.get("ram_installed_gib")
        if installed and installed > p["ram_total_gib"]:
            parts.append(f"{p['ram_total_gib']:.0f}G/{installed:.0f}G RAM")
        else:
            parts.append(f"{p['ram_total_gib']:.0f}G RAM")
    if p.get("gpu_short"):
        gpu = p["gpu_short"]
        if p.get("nvidia", {}).get("ollama_on_gpu"):
            gpu = f"{gpu}+ollama"
        parts.append(gpu)

    return parts, p
