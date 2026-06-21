"""Fleet home Python venv — keep $WILLOW_HOME/venv aligned with willow-2.0/.venv-dev."""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from willow.fylgja.project_env import repo_root
from willow.fylgja.willow_home import fleet_home


def dev_venv(package_root: Path | None = None) -> Path:
    """Canonical dev venv inside the willow-2.0 checkout."""
    return (package_root or repo_root()).resolve() / ".venv-dev"


def fleet_venv(package_root: Path | None = None) -> Path:
    """Fleet-wide venv path under $WILLOW_HOME."""
    return fleet_home(package_root) / "venv"


def _venv_python(venv: Path) -> Path:
    return venv / "bin" / "python3"


def venv_is_usable(venv: Path) -> bool:
    """True when the venv can import Willow's MCP stack."""
    py = _venv_python(venv)
    if not py.is_file():
        return False
    try:
        subprocess.run(
            [str(py), "-c", "import mcp"],
            capture_output=True,
            timeout=30,
            check=True,
        )
        return True
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


@dataclass(frozen=True)
class FleetVenvStatus:
    ok: bool
    fleet_venv: Path
    dev_venv: Path
    detail: str

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "fleet_venv": str(self.fleet_venv),
            "dev_venv": str(self.dev_venv),
            "detail": self.detail,
        }


def check_fleet_venv(package_root: Path | None = None) -> FleetVenvStatus:
    """Report whether $WILLOW_HOME/venv is usable."""
    root = (package_root or repo_root()).resolve()
    target = dev_venv(root)
    link = fleet_venv(root)

    if not _venv_python(target).is_file():
        return FleetVenvStatus(
            ok=False,
            fleet_venv=link,
            dev_venv=target,
            detail=f"missing dev venv at {target} — run: bash setup.sh",
        )

    if not venv_is_usable(target):
        return FleetVenvStatus(
            ok=False,
            fleet_venv=link,
            dev_venv=target,
            detail=f"dev venv at {target} lacks Willow deps — run: bash setup.sh",
        )

    if not link.exists():
        return FleetVenvStatus(
            ok=False,
            fleet_venv=link,
            dev_venv=target,
            detail="missing fleet venv — run: ./willow.sh venv sync",
        )

    if link.is_symlink() and link.resolve() == target.resolve():
        return FleetVenvStatus(
            ok=True,
            fleet_venv=link,
            dev_venv=target,
            detail="fleet venv symlinked to dev venv",
        )

    if venv_is_usable(link):
        return FleetVenvStatus(
            ok=True,
            fleet_venv=link,
            dev_venv=target,
            detail="fleet venv is a standalone install with Willow deps",
        )

    return FleetVenvStatus(
        ok=False,
        fleet_venv=link,
        dev_venv=target,
        detail="fleet venv is a stub (no mcp) — run: ./willow.sh venv sync",
    )


def sync_fleet_venv(package_root: Path | None = None, *, dry_run: bool = False) -> FleetVenvStatus:
    """Point $WILLOW_HOME/venv at willow-2.0/.venv-dev (replace empty stubs)."""
    root = (package_root or repo_root()).resolve()
    target = dev_venv(root).resolve()
    link = fleet_venv(root)
    before = check_fleet_venv(root)
    if before.ok:
        return before

    if not _venv_python(target).is_file():
        raise FileNotFoundError(
            f"dev venv missing at {target} — create it with: bash setup.sh"
        )
    if not venv_is_usable(target):
        raise RuntimeError(
            f"dev venv at {target} is missing Willow deps — run: bash setup.sh"
        )

    if dry_run:
        return FleetVenvStatus(
            ok=True,
            fleet_venv=link,
            dev_venv=target,
            detail=f"would symlink {link} → {target}",
        )

    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink() and link.resolve() == target:
        return FleetVenvStatus(
            ok=True,
            fleet_venv=link,
            dev_venv=target,
            detail="fleet venv already symlinked to dev venv",
        )

    if link.exists() or link.is_symlink():
        backup = link.with_name(f"{link.name}.stub.bak")
        if backup.exists():
            if backup.is_dir():
                shutil.rmtree(backup)
            else:
                backup.unlink()
        if link.is_dir() and not link.is_symlink():
            link.rename(backup)
        else:
            link.unlink()

    link.symlink_to(target, target_is_directory=True)
    return FleetVenvStatus(
        ok=True,
        fleet_venv=link,
        dev_venv=target,
        detail=f"symlinked {link} → {target}",
    )
