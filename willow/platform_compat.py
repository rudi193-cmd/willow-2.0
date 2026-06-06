import os
import sys
import tempfile
from pathlib import Path

IS_WINDOWS: bool = sys.platform == "win32"
IS_POSIX: bool = not IS_WINDOWS
IS_WSL: bool = (
    IS_POSIX
    and Path("/proc/version").exists()
    and "microsoft" in Path("/proc/version").read_text(errors="replace").lower()
)


def tmp_dir() -> Path:
    return Path(tempfile.gettempdir())


def runtime_dir(name: str) -> Path:
    if IS_WINDOWS:
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_RUNTIME_DIR", Path.home() / ".local" / "run"))
    result = base / name
    result.mkdir(parents=True, exist_ok=True)
    return result
