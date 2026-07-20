"""
kart_sandbox.py — unified bwrap sandbox for Kart execution paths.

Used by: core/kart_execute.py (daemon + poll), sap kart_task_run fallback

Mount policy: willow/fylgja/config/kart-sandbox.json (+ dynamic worktree discovery).
"""
from __future__ import annotations

import datetime as _dt
import functools
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

_log = logging.getLogger("kart.sandbox")

_ALLOW_NET_DIRECTIVE = "# allow_net"
_ALLOW_LOCALHOST_DIRECTIVE = "# allow_localhost"
_DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "willow" / "fylgja" / "config" / "kart-sandbox.json"

# --- kart stage-5 Tier-1: delegation to the shipped `kartikeya` package --------
# The fleet-decoupled data-producers — collect_bind_mounts, collect_mcp_trust_ro_overlays,
# and kart_env — now delegate to `kartikeya`, which stripped the `willow.fylgja` coupling
# while preserving the logic byte-for-byte (equivalence proven: willow_compose store record
# kart_migration/3d91bb5a — pointing kartikeya at the fleet config reproduces this module's
# mounts/overlays/env exactly for every network mode). Two fleet-specific inputs kartikeya
# cannot know are injected via its documented env seams, set here with setdefault so an
# operator override always wins:
#   * KART_SANDBOX_CONFIG -> the fleet bwrap mount policy (kart-sandbox.json)
#   * KART_EXTRA_VENVS    -> the fleet venv fylgja binds (~/github/willow-2.0/.venv-dev)
# Deliberately NOT delegated in this step:
#   * build_bwrap_argv — thin bwrap-flag assembly over the delegated producers; kept so the
#     per-root config seam and the module-level monkeypatch points the tests rely on stay
#     intact (its output is proven to reassemble byte-identically).
#   * scan_bash — kartikeya's is a strict security upgrade (fork-bomb detection), a behaviour
#     change owed its own review, not an equivalence swap.
#   * run_shell — kartikeya's enables resource caps by default; that behaviour change gets
#     its own reviewed step.
#   * Tier-2 pieces (load_sandbox_config, …) — behaviour diverged; reconcile with review.
os.environ.setdefault("KART_SANDBOX_CONFIG", str(_DEFAULT_CONFIG))
os.environ.setdefault(
    "KART_EXTRA_VENVS", str(Path.home() / "github" / "willow-2.0" / ".venv-dev")
)


def _kk():
    """Lazy handle to the kartikeya sandbox backend (Tier-1 delegation target).

    Imported on first use, not at module load, so that importing this module for
    its non-delegated helpers (load_sandbox_config, collect_config_symlinks,
    parse_task_network, the audit-verify structural checks, …) does not require
    kartikeya to be installed — only the delegated data-producers below do.
    Python caches the import in sys.modules, so repeat calls are free.
    """
    from kartikeya import sandbox
    return sandbox


def bwrap_available() -> bool:
    return shutil.which("bwrap") is not None


def use_bwrap() -> bool:
    """Whether Kart intends bubblewrap sandboxing (not whether bwrap is installed)."""
    if os.environ.get("WILLOW_KART_NO_BWRAP", "").strip().lower() in ("1", "true", "yes"):
        return False
    return True


@functools.lru_cache(maxsize=1)
def _bwrap_supports_json_status() -> bool:
    """Whether the host bwrap understands --json-status-fd (KP3/S15)."""
    try:
        h = subprocess.run(["bwrap", "--help"], capture_output=True, text=True, timeout=5)
        return "--json-status-fd" in (h.stdout + h.stderr)
    except Exception:
        return False


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
    xdg_runtime = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    return {
        "HOME": home,
        "WILLOW_ROOT": repo,
        "WILLOW_GROVE_ROOT": os.environ.get("WILLOW_GROVE_ROOT", str(Path(home) / "github" / "safe-app-willow-grove")),
        "WILLOW_SAFE_ROOT": os.environ.get("WILLOW_SAFE_ROOT", str(Path(home) / "SAFE" / "Applications")),
        "WILLOW_AGENTS_ROOT": os.environ.get("WILLOW_AGENTS_ROOT", str(Path(home) / "SAFE" / "Agents")),
        "XDG_RUNTIME_DIR": xdg_runtime,
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


def collect_bind_mounts(root: Path | None = None) -> list[tuple[Path, Path, bool]]:
    """
    Return unique (host, container, read_only) mount triples for bwrap.
    read_only=False means read-write bind.

    Delegates to `kartikeya` (Tier-1). Root is resolved here the willow-2.0 way and
    passed through so the fleet's repo/worktree layout drives the mount set; the fleet
    config + venv reach kartikeya via KART_SANDBOX_CONFIG / KART_EXTRA_VENVS (set above).
    """
    return _kk().collect_bind_mounts(root or willow_repo_root())


def collect_mcp_trust_ro_overlays(root: Path | None = None) -> list[Path]:
    """Return willow-mcp on-disk trust roots that must be read-only inside bwrap.

    $WILLOW_HOME/mcp_apps holds per-app manifest.json ACLs and _identity_bindings/
    confirmed OAuth records — the gate for host stdio/serve. The fleet home is
    bind-mounted read-write for store/kart logs; this overlay blocks sandbox tasks
    from rewriting the ACLs that gate them (FRANK baf2f63a / #777).

    Delegates to `kartikeya` (Tier-1); root resolved the willow-2.0 way, passed through.
    """
    return _kk().collect_mcp_trust_ro_overlays(root or willow_repo_root())


def collect_config_symlinks(root: Path | None = None) -> list[tuple[str, str]]:
    """S8/KP6b: (resolved_target, configured_path) for every configured bind
    path that is a symlink on the host.

    collect_bind_mounts resolves and dedups by real path, so a symlinked
    store never appears in the container at its configured path unless the
    sandbox re-emits it as a --symlink. Generalizing here replaces the old
    hand-maintained re-add list — a new symlinked store in config Just Works.
    """
    repo = root or willow_repo_root()
    cfg = load_sandbox_config(repo)
    ctx = _template_ctx(repo)
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for key in ("bind_read_only", "bind_try_read_only", "bind_read_write", "bind_try"):
        for raw in cfg.get(key, []):
            p = Path(_render(str(raw), ctx))
            try:
                if not p.is_symlink():
                    continue
                resolved = p.resolve()
                if not resolved.exists():
                    continue
            except OSError:
                continue
            if str(p) in seen:
                continue
            seen.add(str(p))
            links.append((str(resolved), str(p)))
    return links


def build_bwrap_argv(
    *,
    allow_net: bool = False,
    allow_localhost: bool = False,
    root: Path | None = None,
) -> list[str]:
    # Thin bwrap-flag assembly. Deliberately NOT delegated: it consumes the
    # delegated data-producers (collect_bind_mounts / collect_mcp_trust_ro_overlays,
    # now kartikeya-backed) plus willow-2.0's own collect_config_symlinks by name, so
    # per-root config resolution and the module-level monkeypatch seams the test suite
    # relies on stay intact. The mount/overlay/env *content* — the fleet-decoupled part
    # — is what moved to kartikeya; this glue is proven to reassemble it byte-identically
    # (kart_migration/3d91bb5a). Full delegation of the assembly is a later step.
    args = ["bwrap"]
    # Isolated: --unshare-net blocks all sockets (including 127.0.0.1:11434 Ollama).
    # allow_localhost shares the host net ns so loopback services work, but does NOT
    # mount credentials (GAP-B) — unlike allow_net.
    if not allow_net and not allow_localhost:
        args.append("--unshare-net")
    # KP2 — namespace + kernel-surface hardening.
    #  --tmpfs /tmp + /dev/shm : private scratch, not a host bind (S11, S16) — no
    #                            cross-task channel, no host /tmp pollution.
    #  --unshare-ipc/--unshare-uts : isolate SysV/POSIX IPC + hostname (S12).
    #  --new-session           : own session → blocks TIOCSTI terminal injection,
    #                            CVE-2017-5226 (S2). Safe: Kart is non-interactive.
    #  --as-pid-1              : init/reaper inside the PID ns so children don't
    #                            leak as zombies (S14).
    # NOTE: a --seccomp syscall filter (S13) is deferred — it needs a libseccomp/BPF
    #       toolchain decision; --new-session already covers the CVE-2017-5226 vector.
    args += [
        "--dev", "/dev",
        "--proc", "/proc",
        "--tmpfs", "/tmp",
        "--tmpfs", "/dev/shm",
        "--unshare-pid",
        "--unshare-ipc",
        "--unshare-uts",
        "--new-session",
        "--as-pid-1",
        "--die-with-parent",
    ]

    # Track every destination already claimed inside the sandbox so the
    # symlink passes below never emit a second entry at the same path.
    # bwrap hard-fails on a duplicate ("Can't make symlink at /bin:
    # existing destination is usr/bin"), killing the task before its
    # command ever runs (flag-kart-bwrap-merged-usr-symlink-race —
    # 8.5% of "failed" tasks died in sandbox bring-up, not task logic).
    _claimed: set[str] = set()
    for host, container, read_only in collect_bind_mounts(root):
        flag = "--ro-bind" if read_only else "--bind"
        args += [flag, str(host), str(container)]
        _claimed.add(str(container))

    # Trust-root overlay: fleet home is rw, but mcp_apps must not be writable
    # from inside the sandbox (see collect_mcp_trust_ro_overlays).
    for trust_root in collect_mcp_trust_ro_overlays(root):
        trust_str = str(trust_root)
        if trust_str in _claimed:
            continue
        args += ["--ro-bind", trust_str, trust_str]
        _claimed.add(trust_str)

    # On merged-usr systems /bin, /lib, /lib64, /sbin are symlinks → /usr/*.
    # Recreate them in the sandbox so ELF interpreters (e.g. /lib64/ld-linux*.so.2)
    # resolve — ro-binding /usr alone is not enough for execvp.
    _MERGED_USR_LINKS = [
        ("/bin", "usr/bin"),
        ("/sbin", "usr/sbin"),
        ("/lib", "usr/lib"),
        ("/lib32", "usr/lib32"),
        ("/lib64", "usr/lib64"),
        ("/libx32", "usr/libx32"),
    ]
    for link_path, target in _MERGED_USR_LINKS:
        if not Path(link_path).is_symlink():
            continue
        if link_path in _claimed:
            continue
        args += ["--symlink", target, link_path]
        _claimed.add(link_path)

    # S8/KP6b: any configured bind path that is a host symlink resolves away in
    # collect_bind_mounts (dedup by real path), so re-emit each one as --symlink
    # at its configured path. Generalizes the old hand-coded ~/.willow re-add —
    # the next symlinked store added to config needs no code change.
    for _target, _link in collect_config_symlinks(root):
        if _link in _claimed:
            continue
        args += ["--symlink", _target, _link]
        _claimed.add(_link)

    # ~/.willow keeps one extra behavior the generic pass can't infer: on hosts
    # where the alias does not exist at all, create it anyway so legacy
    # ~/.willow paths work inside bwrap.
    from willow.fylgja.willow_home import willow_home, willow_home_alias

    _home_willow = willow_home_alias()
    _canonical_willow = willow_home()
    if (
        str(_home_willow) not in _claimed
        and _canonical_willow.is_dir()
        and (_home_willow.is_symlink() or not _home_willow.exists())
    ):
        args += ["--symlink", str(_canonical_willow), str(_home_willow)]

    # psycopg2's default socket dir is /var/run/postgresql. collect_bind_mounts
    # resolves the /var/run → /run symlink, so the socket ends up mounted at
    # /run/postgresql but never at /var/run/postgresql. Add a direct bind at
    # the original unresolved path so pg_bridge finds the socket without
    # needing PGHOST set explicitly.
    _pg_sock = Path("/var/run/postgresql")
    if _pg_sock.exists():
        args += ["--bind", str(_pg_sock.resolve()), str(_pg_sock)]

    if allow_net:
        # Credentials are present ONLY on a network-opted task (S1, GAP-B/C).
        # All read-only: a task may use them, never modify or replace them.
        home = Path.home()
        netrc = home / ".netrc"
        if netrc.is_file():
            args += ["--ro-bind", str(netrc), str(netrc)]

        gh_cfg = home / ".config" / "gh"
        if gh_cfg.is_dir():
            args += ["--ro-bind", str(gh_cfg), str(gh_cfg)]

        # ~/.ssh is never bound (S1) — private keys do not enter the sandbox.
        # SSH git auth flows through the agent socket; host-key verification needs
        # only known_hosts (read-only).
        known_hosts = home / ".ssh" / "known_hosts"
        if known_hosts.is_file():
            args += ["--ro-bind", str(known_hosts), str(known_hosts)]
        ssh_sock = os.environ.get("SSH_AUTH_SOCK", "").strip()
        if ssh_sock and Path(ssh_sock).exists():
            # The agent socket is read-write (clients write requests to it), but it
            # exposes no key material — the agent holds the keys out of process.
            args += ["--bind", ssh_sock, ssh_sock]

        # Ubuntu/Debian nsswitch.conf has mdns4_minimal [NOTFOUND=return] before dns,
        # which causes non-.local lookups to abort before reaching the DNS backend.
        # Shadow /etc/nsswitch.conf with a minimal version that goes straight to dns.
        # Written under WILLOW_HOME (not host /tmp) so it survives --tmpfs /tmp and
        # does not pollute the host /tmp (S11).
        from willow.fylgja.willow_home import willow_home as _wh
        _nsswitch = _wh(root) / "kart-nsswitch.conf"
        _nsswitch.write_text(
            "passwd:   files\ngroup:    files\nhosts:    files dns\n",
            encoding="utf-8",
        )
        args += ["--ro-bind", str(_nsswitch), "/etc/nsswitch.conf"]

    return args


def _sandbox_bash() -> str:
    """Absolute bash path for bwrap exec (merged-usr has no /bin in the sandbox)."""
    for candidate in ("/usr/bin/bash", "/bin/bash"):
        if Path(candidate).is_file():
            return candidate
    return "bash"


def task_allows_network(task_text: str) -> bool:
    return any(line.strip() == _ALLOW_NET_DIRECTIVE for line in task_text.splitlines())


def task_allows_localhost(task_text: str) -> bool:
    return any(line.strip() == _ALLOW_LOCALHOST_DIRECTIVE for line in task_text.splitlines())


def parse_task_network(task_text: str) -> tuple[str, bool, bool]:
    """Strip network directives; return (cmd_body, allow_net, allow_localhost)."""
    allow_net = task_allows_network(task_text)
    allow_localhost = (not allow_net) and task_allows_localhost(task_text)
    skip = {_ALLOW_NET_DIRECTIVE, _ALLOW_LOCALHOST_DIRECTIVE}
    lines = [line for line in task_text.splitlines() if line.strip() not in skip]
    return "\n".join(lines).strip(), allow_net, allow_localhost


def kart_env(
    root: Path | None = None,
    *,
    allow_net: bool = False,
    allow_localhost: bool = False,
) -> dict[str, str]:
    """Build the environment handed into the sandbox (incl. GAP-B credential gating).

    Delegates to `kartikeya` (Tier-1). Proven byte-identical to the former inline
    implementation for every (allow_net, allow_localhost) mode when kartikeya is
    pointed at the fleet config (kart_migration/3d91bb5a): same env-prefix passthrough,
    fleet env-file supplement, venv/PATH assembly, git identity, PG-socket discovery,
    and the credential strip on no-network tasks. Root resolved the willow-2.0 way.
    """
    return _kk().kart_env(
        root or willow_repo_root(),
        allow_net=allow_net,
        allow_localhost=allow_localhost,
    )


def sandbox_manifest(
    *,
    allow_net: bool = False,
    allow_localhost: bool = False,
    root: Path | None = None,
) -> dict:
    """KP3 — declare the boundary so a caller can tell 'empty' from 'absent'.

    Reports the roots that ARE mounted (rw vs ro), the tmpfs scratch, the network
    state, and the PATH dirs visible inside the sandbox. This is the read-side cure
    for the audit's defining defect: an unbound path returns empty, identical to a
    real absence, with no signal. The manifest is that signal.
    """
    engine = "bwrap" if use_bwrap() else "plain"
    bound_rw: list[str] = []
    bound_ro: list[str] = []
    try:
        for host, _container, read_only in collect_bind_mounts(root):
            (bound_ro if read_only else bound_rw).append(str(host))
        for trust_root in collect_mcp_trust_ro_overlays(root):
            bound_ro.append(str(trust_root))
    except Exception:
        pass
    path_dirs = kart_env(
        root, allow_net=allow_net, allow_localhost=allow_localhost
    ).get("PATH", "").split(":")
    if allow_net:
        network_mode = "full"
    elif allow_localhost:
        network_mode = "localhost"
    else:
        network_mode = "isolated"
    return {
        "engine": engine,
        "allow_net": allow_net,
        "allow_localhost": allow_localhost and not allow_net,
        "network_mode": network_mode,
        "bound_rw": sorted(bound_rw),
        "bound_ro": sorted(bound_ro),
        "tmpfs": ["/tmp", "/dev/shm"] if engine == "bwrap" else [],
        "path_dirs": [p for p in path_dirs if p],
    }


def unreachable_notes(cmd: str, manifest: dict) -> list[str]:
    """KP3 — cheap pre-flight: flag home-dir absolute paths the task references that
    are not mounted in the sandbox, so a silent empty result is annotated
    ('note: ~/.claude not mounted') rather than read as a real absence (S3/S5)."""
    if manifest.get("engine") != "bwrap":
        return []
    home = str(Path.home())
    bound = (
        manifest.get("bound_rw", [])
        + manifest.get("bound_ro", [])
        + manifest.get("tmpfs", [])
    )
    notes: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r"(?<![\w])(" + re.escape(home) + r"/[\w.\-/]+)", cmd):
        path = m.group(1).rstrip("/.,;:)\"'")
        if path in seen:
            continue
        seen.add(path)
        if not any(path == b or path.startswith(b.rstrip("/") + "/") for b in bound):
            notes.append(f"path not mounted in sandbox: {path}")
    return notes


# Matches a standalone `rtk` command token (not part of another word or path)
# so a rewritten command's `rtk <subcommand>` segments can be repointed at our
# vetted binary regardless of its on-disk filename or PATH.
_RTK_TOKEN_RE = re.compile(r"(?<![\w./-])rtk(?=\s)")


def _rtk_rewrite(cmd: str, config: dict) -> str:
    """Rewrite `cmd` through the vetted rtk-plus binary for output-token
    compression, when enabled in kart-sandbox.json's rtk_compress block.
    Fails open (returns cmd unchanged) on any error, missing binary, or when
    rtk itself declines to rewrite — never blocks execution."""
    rtk_cfg = (config or {}).get("rtk_compress") or {}
    if not rtk_cfg.get("enabled"):
        return cmd
    binary = os.path.expanduser(rtk_cfg.get("binary", "~/.willow/bin/rtk-plus"))
    if not os.path.isfile(binary):
        return cmd
    try:
        result = subprocess.run(
            [binary, "rewrite", cmd],
            capture_output=True,
            text=True,
            timeout=2,
            env={"PATH": os.environ.get("PATH", ""), "RTK_TELEMETRY_DISABLED": "1"},
        )
    except Exception:
        return cmd
    if result.returncode != 0:
        return cmd
    rewritten = result.stdout.strip()
    if not rewritten or rewritten == cmd:
        return cmd
    return _RTK_TOKEN_RE.sub(binary, rewritten)


def run_shell(
    cmd: str,
    *,
    timeout: int = 120,
    allow_net: bool = False,
    allow_localhost: bool = False,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> dict:
    """
    Execute one shell command via bash -c (inside bwrap when enabled).
    Returns {returncode, stdout, stderr, elapsed_s, sandbox: bwrap|plain}.
    """
    started = time.time()
    run_env = kart_env(allow_net=allow_net, allow_localhost=allow_localhost)
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

    original_cmd = cmd
    cmd = _rtk_rewrite(cmd, load_sandbox_config())
    rtk_rewritten = cmd != original_cmd

    # Use bash -c so shell operators (&&, |, $(), redirects) work correctly.
    bash = _sandbox_bash()
    argv = [bash, "-c", cmd]
    sandbox = "plain"
    pass_fds: tuple[int, ...] = ()
    status_file = None
    if use_bwrap():
        prefix = build_bwrap_argv(
            allow_net=allow_net, allow_localhost=allow_localhost
        )
        # KP3/S15: --json-status-fd lets us tell a sandbox-SETUP failure (mount/ns
        # error, bwrap exits before exec) from a COMMAND failure. bwrap writes
        # {"child-pid":N} once the child execs; its absence on a non-zero exit
        # means setup failed. Feature-gated so an old bwrap is unaffected.
        if _bwrap_supports_json_status():
            status_file = tempfile.TemporaryFile(mode="w+")
            fd = status_file.fileno()
            prefix = [prefix[0], "--json-status-fd", str(fd)] + prefix[1:]
            pass_fds = (fd,)
        full = prefix + ["--", bash, "-c", cmd]
        sandbox = "bwrap"
    else:
        full = argv

    def _setup_state() -> str | None:
        if status_file is None:
            return None
        try:
            status_file.seek(0)
            txt = status_file.read()
        except Exception:
            return None
        return "ok" if '"child-pid"' in txt else "failed"

    try:
        proc = subprocess.run(
            full,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=run_env,
            cwd=cwd,
            pass_fds=pass_fds,
        )
        elapsed = round(time.time() - started, 2)
        setup = _setup_state()
        out = {
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "elapsed_s": elapsed,
            "sandbox": sandbox,
        }
        if rtk_rewritten:
            out["rtk_rewritten"] = True
        if setup is not None:
            out["sandbox_setup"] = setup
            if setup == "failed":
                out["error"] = "sandbox_setup_failed"
        return out
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
    finally:
        if status_file is not None:
            try:
                status_file.close()
            except Exception:
                pass


def clip_output(text: str, limit: int) -> str:
    """Clip long output keeping head and tail, with an explicit marker.

    Replaces the old silent tail-keep slice ([-N:]) that dropped the
    beginning of output with no indication anything was missing.
    """
    if len(text) <= limit:
        return text
    head = limit * 2 // 3
    tail = limit - head
    dropped = len(text) - head - tail
    return f"{text[:head]}\n…[kart: {dropped} chars clipped]…\n{text[-tail:]}"


def run_shell_result_for_task(
    cmd: str,
    *,
    timeout: int = 120,
    allow_net: bool = False,
    allow_localhost: bool = False,
) -> tuple[str, dict]:
    """Normalize run_shell output for pg.task_complete(status, result)."""
    raw = run_shell(
        cmd,
        timeout=timeout,
        allow_net=allow_net,
        allow_localhost=allow_localhost,
    )
    status = "completed" if raw.get("returncode") == 0 and raw.get("error") != "timeout" else "failed"
    result = {
        "returncode": raw.get("returncode"),
        "stdout": clip_output((raw.get("stdout") or "").strip(), 8000),
        "stderr": clip_output((raw.get("stderr") or "").strip(), 1500),
        "elapsed_s": raw.get("elapsed_s"),
        "sandbox": raw.get("sandbox"),
    }
    if raw.get("sandbox_setup"):
        result["sandbox_setup"] = raw["sandbox_setup"]
    if raw.get("error"):
        result["error"] = raw["error"]
    # Uniform error capture: every failed task carries a non-empty, human-readable
    # `error`. A command that fails by exit code with empty stderr (e.g. grep
    # no-match, a silent non-zero step in an `&&` chain) would otherwise leave the
    # failure causeless and untriageable. Full stdout/stderr stay in their fields.
    if status == "failed" and not result.get("error"):
        rc = result["returncode"]
        last_err = result["stderr"].splitlines()[-1].strip() if result["stderr"] else ""
        last_out = result["stdout"].splitlines()[-1].strip() if result["stdout"] else ""
        if last_err:
            result["error"] = last_err[:200]
        elif last_out:
            result["error"] = f"exited {rc}: {last_out[:180]}"
        else:
            result["error"] = f"exited {rc} with no output"
    # KP7/S10: unclipped output rides along under private keys so the task-level
    # caller (which knows the task_id) can write a durable log artifact. Popped
    # by execute_task_row before the result reaches task_complete.
    result["_full_stdout"] = raw.get("stdout") or ""
    result["_full_stderr"] = raw.get("stderr") or ""
    # KP3: attach the boundary manifest + any unreachable-path notes so a caller can
    # tell "this is empty" from "I couldn't see this." Best-effort — never fail the
    # task over manifest construction.
    try:
        manifest = sandbox_manifest(
            allow_net=allow_net,
            allow_localhost=allow_localhost,
            root=None,
        )
        notes = unreachable_notes(cmd, manifest)
        if notes:
            manifest["notes"] = notes
        result["sandbox_manifest"] = manifest
    except Exception:
        pass
    return status, result


# ── KP7/S10 — durable per-task log artifacts ──────────────────────────────────

KART_LOG_RETENTION = 200


def _kart_logs_root() -> Path:
    from willow.fylgja.willow_home import willow_home
    return Path(willow_home()) / ".kart-logs"


def _prune_task_logs(root: Path, keep: int = KART_LOG_RETENTION) -> None:
    """Keep the newest `keep` task-log dirs; remove the rest. Best-effort."""
    try:
        dirs = sorted(
            (d for d in root.iterdir() if d.is_dir()),
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )
        for stale in dirs[keep:]:
            shutil.rmtree(stale, ignore_errors=True)
    except Exception:
        pass


def write_task_log(
    task_id: str,
    cmd: str,
    status: str,
    result: dict,
    *,
    full_stdout: str | None = None,
    full_stderr: str | None = None,
) -> str | None:
    """Write a durable forensic artifact for one task (KP7/S10).

    $WILLOW_HOME/.kart-logs/<task_id>/{meta.json, stdout.log, stderr.log}.
    meta.json carries the env *key list* only — values may hold credentials
    and must never land in a log file. Never raises; returns the dir path or
    None if the write failed.
    """
    try:
        safe_id = "".join(c for c in str(task_id) if c.isalnum() or c in "_-") or "unknown"
        log_dir = _kart_logs_root() / safe_id
        log_dir.mkdir(parents=True, exist_ok=True)

        manifest = result.get("sandbox_manifest") or {}
        env = kart_env(
            allow_net=bool(manifest.get("allow_net")),
            allow_localhost=bool(manifest.get("allow_localhost")),
        )
        meta = {
            "task_id": str(task_id),
            "cmd": cmd[:4000],
            "status": status,
            "returncode": result.get("returncode"),
            "error": result.get("error"),
            "elapsed_s": result.get("elapsed_s"),
            "sandbox": result.get("sandbox"),
            "sandbox_setup": result.get("sandbox_setup"),
            "allow_net": manifest.get("allow_net"),
            "allow_localhost": manifest.get("allow_localhost"),
            "network_mode": manifest.get("network_mode"),
            "cwd": os.getcwd(),
            "written_at": _dt.datetime.now().astimezone().isoformat(),
            "bwrap_argv_summary": {
                "bound_ro": manifest.get("bound_ro"),
                "bound_rw": manifest.get("bound_rw"),
                "tmpfs": manifest.get("tmpfs"),
                "path_dirs": manifest.get("path_dirs"),
                "notes": manifest.get("notes"),
            },
            "env_keys": sorted(env.keys()),
        }
        (log_dir / "meta.json").write_text(
            json.dumps(meta, indent=2, default=str), encoding="utf-8"
        )
        (log_dir / "stdout.log").write_text(
            full_stdout if full_stdout is not None else (result.get("stdout") or ""),
            encoding="utf-8",
        )
        (log_dir / "stderr.log").write_text(
            full_stderr if full_stderr is not None else (result.get("stderr") or ""),
            encoding="utf-8",
        )
        _prune_task_logs(log_dir.parent)
        return str(log_dir)
    except Exception:
        return None
