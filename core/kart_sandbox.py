"""
kart_sandbox.py — unified bwrap sandbox for Kart execution paths.

Used by: core/kart_execute.py (daemon + poll), sap kart_task_run fallback

Mount policy: willow/fylgja/config/kart-sandbox.json (+ dynamic worktree discovery).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sysconfig
import time
from pathlib import Path

_ALLOW_NET_DIRECTIVE = "# allow_net"
_DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "willow" / "fylgja" / "config" / "kart-sandbox.json"


def bwrap_available() -> bool:
    return shutil.which("bwrap") is not None


def use_bwrap() -> bool:
    if os.environ.get("WILLOW_KART_NO_BWRAP", "").strip().lower() in ("1", "true", "yes"):
        return False
    return bwrap_available()


def willow_repo_root() -> Path | None:
    env = (os.environ.get("WILLOW_ROOT") or "").strip()
    candidates: list[Path] = []
    if env:
        candidates.append(Path(env).expanduser())
    candidates.append(Path(__file__).resolve().parent.parent)
    candidates.append(Path.home() / "github" / "willow-2.0")
    for base in candidates:
        try:
            resolved = base.resolve()
            if (resolved / "core" / "kart_sandbox.py").is_file() or (resolved / "core" / "pg_bridge.py").is_file():
                return resolved
        except OSError:
            continue
    return None


def _template_ctx(root: Path | None) -> dict[str, str]:
    home = str(Path.home())
    repo = str(root or willow_repo_root() or Path.cwd())
    return {
        "HOME": home,
        "WILLOW_ROOT": repo,
        "WILLOW_GROVE_ROOT": os.environ.get("WILLOW_GROVE_ROOT", str(Path(home) / "github" / "safe-app-willow-grove")),
        "WILLOW_SAFE_ROOT": os.environ.get("WILLOW_SAFE_ROOT", str(Path(home) / "SAFE" / "Applications")),
        "WILLOW_AGENTS_ROOT": os.environ.get("WILLOW_AGENTS_ROOT", str(Path(home) / "SAFE" / "Agents")),
    }


def _render(path_template: str, ctx: dict[str, str]) -> str:
    out = path_template
    for key, val in ctx.items():
        out = out.replace(f"{{{{{key}}}}}", val)
    return os.path.expanduser(out)


def load_sandbox_config(root: Path | None = None) -> dict:
    repo = root or willow_repo_root()
    path = (repo / "willow" / "fylgja" / "config" / "kart-sandbox.json") if repo else _DEFAULT_CONFIG
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _discover_worktree_targets(scan_roots: list[Path]) -> list[Path]:
    """Bind worktrees/ and every child (symlink targets included)."""
    found: list[Path] = []
    seen: set[str] = set()
    for root in scan_roots:
        if not root.is_dir():
            continue
        for candidate in (root, *root.iterdir()):
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            key = str(resolved)
            if key in seen:
                continue
            seen.add(key)
            found.append(resolved)
    return found


def collect_bind_mounts(root: Path | None = None) -> list[tuple[Path, Path, bool]]:
    """
    Return unique (host, container, read_only) mount triples for bwrap.
    read_only=False means read-write bind.
    """
    repo = root or willow_repo_root()
    cfg = load_sandbox_config(repo)
    ctx = _template_ctx(repo)

    mounts: dict[str, tuple[Path, Path, bool]] = {}

    def _add(host: Path, read_only: bool) -> None:
        try:
            if not host.exists():
                return
            resolved = host.resolve()
        except OSError:
            return
        key = str(resolved)
        ro = read_only
        if key in mounts:
            existing = mounts[key]
            mounts[key] = (existing[0], existing[1], existing[2] and ro)
        else:
            mounts[key] = (resolved, resolved, ro)

    for raw in cfg.get("bind_read_only", []):
        _add(Path(_render(str(raw), ctx)), True)
    for raw in cfg.get("bind_read_write", []):
        _add(Path(_render(str(raw), ctx)), False)
    for raw in cfg.get("bind_try", []):
        _add(Path(_render(str(raw), ctx)), False)

    scan_roots = [
        Path(_render(str(raw), ctx))
        for raw in cfg.get("worktree_scan_roots", ["{{WILLOW_ROOT}}/worktrees"])
    ]
    for wt in _discover_worktree_targets(scan_roots):
        _add(wt, False)

    # Python runtime paths for venv / psycopg2 inside bwrap
    repo_venv = (repo / ".venv-dev") if repo else None
    if repo_venv and repo_venv.is_dir():
        _add(repo_venv, True)
    home_venv = Path.home() / ".willow-venv"
    if home_venv.is_dir() and (not repo_venv or home_venv.resolve() != repo_venv.resolve()):
        _add(home_venv, True)
    try:
        import psycopg2 as _pg2

        _add(Path(_pg2.__file__).resolve().parent, True)
        libs = Path(_pg2.__file__).resolve().parent.parent / "psycopg2_binary.libs"
        _add(libs, True)
    except ImportError:
        pass
    user_site = sysconfig.get_path("purelib")
    if user_site:
        _add(Path(user_site), True)

    return sorted(mounts.values(), key=lambda t: str(t[0]))


def build_bwrap_argv(*, allow_net: bool = False, root: Path | None = None) -> list[str]:
    args = ["bwrap"]
    if not allow_net:
        args.append("--unshare-net")
    args += ["--dev", "/dev", "--proc", "/proc", "--unshare-pid", "--die-with-parent"]

    for host, container, read_only in collect_bind_mounts(root):
        flag = "--ro-bind" if read_only else "--bind"
        args += [flag, str(host), str(container)]

    # On merged-usr systems /bin, /lib, /lib64, /sbin are symlinks → /usr/*.
    # collect_bind_mounts resolves them to real paths, so the container gets
    # e.g. /usr/bin but no /bin symlink.  Without /lib64 the ELF interpreter
    # can't be found and bash/python3 fail with ENOENT.  Re-add the symlinks.
    _MERGED_USR_LINKS = [
        ("/bin", "usr/bin"),
        ("/sbin", "usr/sbin"),
        ("/lib", "usr/lib"),
        ("/lib32", "usr/lib32"),
        ("/lib64", "usr/lib64"),
        ("/libx32", "usr/libx32"),
    ]
    for link_path, target in _MERGED_USR_LINKS:
        p = Path(link_path)
        if p.is_symlink():
            args += ["--symlink", target, link_path]

    # If ~/.willow doesn't exist on the host (common when it hasn't been symlinked
    # yet) but ~/github/.willow does, inject a symlink so scripts using ~/.willow
    # paths work inside the container.
    _home_willow = Path.home() / ".willow"
    _github_willow = Path.home() / "github" / ".willow"
    if not _home_willow.exists() and _github_willow.is_dir():
        args += ["--symlink", str(_github_willow), str(_home_willow)]

    # psycopg2's default socket dir is /var/run/postgresql. collect_bind_mounts
    # resolves the /var/run → /run symlink, so the socket ends up mounted at
    # /run/postgresql but never at /var/run/postgresql. Add a direct bind at
    # the original unresolved path so pg_bridge finds the socket without
    # needing PGHOST set explicitly.
    _pg_sock = Path("/var/run/postgresql")
    if _pg_sock.exists():
        args += ["--bind", str(_pg_sock.resolve()), str(_pg_sock)]

    if allow_net:
        home = Path.home()
        netrc = home / ".netrc"
        if netrc.is_file():
            args += ["--ro-bind", str(netrc), str(netrc)]

        # Ubuntu/Debian nsswitch.conf has mdns4_minimal [NOTFOUND=return] before dns,
        # which causes non-.local lookups to abort before reaching the DNS backend.
        # Shadow /etc/nsswitch.conf with a minimal version that goes straight to dns.
        _nsswitch = Path("/tmp/kart-nsswitch.conf")
        _nsswitch.write_text(
            "passwd:   files\ngroup:    files\nhosts:    files dns\n",
            encoding="utf-8",
        )
        args += ["--ro-bind", str(_nsswitch), "/etc/nsswitch.conf"]

    return args


def task_allows_network(task_text: str) -> bool:
    return any(line.strip() == _ALLOW_NET_DIRECTIVE for line in task_text.splitlines())


def _parse_fleet_env_file(path: Path, prefixes: tuple[str, ...]) -> dict[str, str]:
    """Parse a shell KEY=VALUE env file. Skips comments and blank lines.
    Only includes keys matching prefixes. Strips surrounding quotes from values."""
    result: dict[str, str] = {}
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            if not key or not key.startswith(prefixes):
                continue
            val = val.strip()
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1]
            if val:
                result[key] = val
    except Exception:
        pass
    return result


def kart_env(root: Path | None = None) -> dict[str, str]:
    repo = root or willow_repo_root()
    cfg = load_sandbox_config(repo)
    prefixes = tuple(cfg.get("env_prefixes") or ("WILLOW_", "GROVE_", "PG", "POSTGRES", "OLLAMA_", "GIT_", "ANTHROPIC_", "GROQ_"))

    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": str(Path.home()),
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        "PYTHONUNBUFFERED": "1",
    }
    for key, val in os.environ.items():
        if key.startswith(prefixes):
            env[key] = val

    # Supplement with fleet env file so API keys (ANTHROPIC_API_KEY, GROQ_API_KEY, …)
    # reach bwrap tasks even when the calling process (MCP server, kart worker) didn't
    # inherit them from the user's shell. os.environ values take priority.
    _fleet_env_path = Path.home() / "github" / ".willow" / "env"
    for k, v in _parse_fleet_env_file(_fleet_env_path, prefixes).items():
        if k not in env:
            env[k] = v

    # Resolved repo wins over inherited env (MCP may pass $HOME or a stale path).
    if repo:
        env["WILLOW_ROOT"] = str(repo.resolve())
        env["PYTHONPATH"] = str(repo.resolve())

    venv_bin = None
    if repo and (repo / ".venv-dev" / "bin").is_dir():
        venv_bin = str(repo / ".venv-dev" / "bin")
    elif (Path.home() / ".willow-venv" / "bin").is_dir():
        venv_bin = str(Path.home() / ".willow-venv" / "bin")
    if venv_bin and venv_bin not in env["PATH"]:
        env["PATH"] = venv_bin + ":" + env["PATH"]

    if "GIT_AUTHOR_NAME" not in env:
        try:
            name = subprocess.check_output(["git", "config", "--global", "user.name"], text=True).strip()
            email = subprocess.check_output(["git", "config", "--global", "user.email"], text=True).strip()
            if name:
                env["GIT_AUTHOR_NAME"] = name
                env["GIT_COMMITTER_NAME"] = name
            if email:
                env["GIT_AUTHOR_EMAIL"] = email
                env["GIT_COMMITTER_EMAIL"] = email
        except Exception:
            pass

    # Inside bwrap, /var/run is not present (collect_bind_mounts resolves the
    # /var/run → /run symlink away). psycopg2 with host=None defaults to
    # /var/run/postgresql, which doesn't exist in the container.
    # Set WILLOW_PG_HOST to the real socket directory so pg_bridge finds it.
    if not env.get("WILLOW_PG_HOST"):
        import glob as _glob
        for _sock in _glob.glob("/run/postgresql/.s.PGSQL.*") + _glob.glob("/tmp/.s.PGSQL.*"):
            env["WILLOW_PG_HOST"] = str(Path(_sock).parent)
            break

    # The SAP gate requires WILLOW_SAFE_ROOT to initialize; without it classify
    # fails inside bwrap and promote_intake falls back to heuristic routing.
    if not env.get("WILLOW_SAFE_ROOT"):
        default_safe = Path.home() / "github" / "SAFE" / "Applications"
        if default_safe.is_dir():
            env["WILLOW_SAFE_ROOT"] = str(default_safe)

    return env


def run_shell(
    cmd: str,
    *,
    timeout: int = 120,
    allow_net: bool = False,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> dict:
    """
    Execute one shell command via bash -c (inside bwrap when enabled).
    Returns {returncode, stdout, stderr, elapsed_s, sandbox: bwrap|plain}.
    """
    started = time.time()
    run_env = kart_env()
    if env:
        run_env.update(env)
    if cwd:
        run_env["PWD"] = cwd

    if not cmd.strip():
        return {
            "returncode": 1,
            "stdout": "",
            "stderr": "empty command",
            "elapsed_s": 0.0,
            "sandbox": "none",
        }

    # Use bash -c so shell operators (&&, |, $(), redirects) work correctly.
    argv = ["bash", "-c", cmd]
    sandbox = "plain"
    if use_bwrap():
        prefix = build_bwrap_argv(allow_net=allow_net)
        full = prefix + argv
        sandbox = "bwrap"
    else:
        full = argv

    try:
        proc = subprocess.run(
            full,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=run_env,
            cwd=cwd,
        )
        elapsed = round(time.time() - started, 2)
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "elapsed_s": elapsed,
            "sandbox": sandbox,
        }
    except subprocess.TimeoutExpired as e:
        return {
            "returncode": -1,
            "stdout": (e.stdout or "") if isinstance(e.stdout, str) else "",
            "stderr": (e.stderr or "") if isinstance(e.stderr, str) else "",
            "elapsed_s": round(time.time() - started, 2),
            "error": "timeout",
            "sandbox": sandbox,
        }
    except Exception as e:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
            "elapsed_s": round(time.time() - started, 2),
            "error": str(e),
            "sandbox": sandbox,
        }


def run_shell_result_for_task(cmd: str, *, timeout: int = 120, allow_net: bool = False) -> tuple[str, dict]:
    """Normalize run_shell output for pg.task_complete(status, result)."""
    raw = run_shell(cmd, timeout=timeout, allow_net=allow_net)
    status = "completed" if raw.get("returncode") == 0 and raw.get("error") != "timeout" else "failed"
    result = {
        "returncode": raw.get("returncode"),
        "stdout": (raw.get("stdout") or "").strip()[-2000:],
        "stderr": (raw.get("stderr") or "").strip()[-500:],
        "elapsed_s": raw.get("elapsed_s"),
        "sandbox": raw.get("sandbox"),
    }
    if raw.get("error"):
        result["error"] = raw["error"]
    return status, result
