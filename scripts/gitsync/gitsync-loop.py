#!/usr/bin/env python3
"""Host git-universe sync. Fetch + ff-only pull all clones (safe, never
clobbers), detect brand-new remote repos, write a status file each pass.
Does NOT auto-clone new repos and NEVER touches the operator data vault
(`{github_user}-data-vault` by default — see owners.json).

New-repo discovery scans configured GitHub owners (personal account + orgs).
See owners.json or GITSYNC_OWNERS (comma-separated) to override.

Modes:
  --once   run a single pass and exit (used by the systemd timer)
  (none)   loop forever, sleeping SYNC_INTERVAL between passes (nohup mode)

Runtime files (status/log/pid) land next to this script.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

BASE = os.path.expanduser("~/github")
HERE = os.path.dirname(os.path.abspath(__file__))
STATUS = os.path.join(HERE, "gitsync-status.txt")
LOG = os.path.join(HERE, "gitsync.log")
PIDFILE = os.path.join(HERE, "gitsync-loop.pid")
OWNERS_FILE = os.path.join(HERE, "owners.json")
INTERVAL = int(os.environ.get("SYNC_INTERVAL", "1500"))   # 25 min (loop mode)
NEWWIN = int(os.environ.get("SYNC_NEWREPO_MIN", "360"))  # flag repos created <6h
VAULT_SUFFIX = "-data-vault"
SCHEMA_VAULT = f"willow{VAULT_SUFFIX}"  # public schema repo — still synced

_ORIGIN_RE = re.compile(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$")


def sh(a, cwd=None, t=90):
    try:
        r = subprocess.run(a, cwd=cwd, capture_output=True, text=True, timeout=t)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except Exception as e:
        return 99, "", f"ERR:{e}"


def now():
    return datetime.now(timezone.utc)


def age_min(ts):
    try:
        return (now() - datetime.fromisoformat(ts.replace("Z", "+00:00"))).total_seconds() / 60
    except Exception:
        return 1e9


def _load_owners_config() -> dict:
    try:
        with open(OWNERS_FILE, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def github_login() -> str:
    """Authenticated GitHub user — primary account for owner discovery."""
    cfg = _load_owners_config()
    for candidate in (
        os.environ.get("GITSYNC_GITHUB_USER", "").strip(),
        str(cfg.get("github_user") or "").strip(),
    ):
        if candidate:
            return candidate
    rc, login, _ = sh(["gh", "api", "user", "--jq", ".login"], t=15)
    if rc == 0 and login:
        return login
    return os.environ.get("USER") or os.environ.get("LOGNAME") or ""


def vault_identity_user() -> str:
    """Explicit operator vault slug — never inferred from GitHub login."""
    cfg = _load_owners_config()
    for candidate in (
        os.environ.get("GITSYNC_VAULT_USER", "").strip(),
        str(cfg.get("vault_user") or "").strip(),
    ):
        if candidate:
            return candidate
    return ""


def _discover_vault_from_disk() -> str:
    """If exactly one operator vault clone exists, use it (e.g. alice-data-vault)."""
    candidates: list[str] = []
    try:
        for name in os.listdir(BASE):
            low = name.lower()
            if not low.endswith(VAULT_SUFFIX) or low == SCHEMA_VAULT:
                continue
            path = os.path.join(BASE, name)
            if os.path.isdir(os.path.join(path, ".git")):
                candidates.append(low)
    except OSError:
        return ""
    if len(candidates) == 1:
        return candidates[0]
    return ""


def vault_repo_name() -> str:
    """Operator private vault repo folder name (e.g. alice-data-vault)."""
    cfg = _load_owners_config()
    explicit = (
        os.environ.get("GITSYNC_VAULT_REPO", "").strip()
        or str(cfg.get("vault_repo") or "").strip()
    )
    if explicit:
        return explicit.split("/")[-1].lower()

    user = vault_identity_user()
    if user:
        return f"{user.lower()}{VAULT_SUFFIX}"

    discovered = _discover_vault_from_disk()
    if discovered:
        return discovered

    login = github_login()
    if login:
        return f"{login.lower()}{VAULT_SUFFIX}"

    unix = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
    if unix:
        return f"{unix.lower()}{VAULT_SUFFIX}"
    return ""


def excluded_repo_names() -> set[str]:
    """Local repo folder names excluded from fetch/pull and NEW_REMOTE flags."""
    cfg = _load_owners_config()
    names: set[str] = set()
    vault = vault_repo_name()
    if vault:
        names.add(vault)
    for item in cfg.get("excluded_repos") or []:
        slug = str(item).strip().lower()
        if slug:
            names.add(slug.split("/")[-1])
    extra = os.environ.get("GITSYNC_EXCLUDED_REPOS", "")
    for item in extra.split(","):
        slug = item.strip().lower()
        if slug:
            names.add(slug.split("/")[-1])
    return names


def is_excluded_repo(name: str) -> bool:
    return name.lower() in excluded_repo_names()


def discover_owners() -> list[str]:
    """Personal account + orgs to scan for brand-new repos."""
    env = os.environ.get("GITSYNC_OWNERS", "").strip()
    if env:
        return [o.strip() for o in env.split(",") if o.strip()]

    cfg = _load_owners_config()
    owners: list[str] = list(cfg.get("owners") or [])
    if not owners:
        login = github_login()
        if login:
            owners = [login]
    exclude = {o.lower() for o in (cfg.get("exclude_owners") or [])}

    if cfg.get("auto_orgs", True):
        rc, out, _ = sh(["gh", "api", "user/orgs", "--jq", ".[].login"], t=30)
        if rc == 0 and out:
            for line in out.splitlines():
                login = line.strip()
                if login and login.lower() not in exclude:
                    owners.append(login)

    seen: set[str] = set()
    ordered: list[str] = []
    for owner in owners:
        key = owner.lower()
        if key in seen or key in exclude:
            continue
        seen.add(key)
        ordered.append(owner)
    return ordered


def local_repos():
    out = []
    for n in sorted(os.listdir(BASE)):
        p = os.path.join(BASE, n)
        if is_excluded_repo(n):
            continue
        if os.path.isdir(os.path.join(p, ".git")):
            out.append((n, p))
    wp = os.path.join(BASE, ".willow")
    if os.path.isdir(os.path.join(wp, ".git")):
        out.append((".willow", wp))
    return out


def local_clone_keys() -> set[str]:
    """Folder names and owner/repo keys for clones already on disk."""
    keys: set[str] = set()
    for name, path in local_repos():
        keys.add(name.lower())
        rc, url, _ = sh(["git", "-C", path, "remote", "get-url", "origin"], t=15)
        if rc != 0 or not url:
            continue
        m = _ORIGIN_RE.search(url)
        if m:
            owner = m.group("owner").lower()
            repo = m.group("repo").lower()
            keys.add(repo)
            keys.add(f"{owner}/{repo}")
    return keys


def sync_one(name, p):
    if sh(["git", "fetch", "--all", "--prune", "--quiet"], p)[0] != 0:
        return ("ferr", name)
    ndirty = len([line for line in sh(["git", "status", "--porcelain"], p, 20)[1].splitlines() if line.strip()])
    rc, ab, _ = sh(["git", "rev-list", "--left-right", "--count", "HEAD...@{upstream}"], p, 20)
    if rc != 0 or "\t" not in ab:
        return ("no_up", name)
    a, b = (int(x) for x in ab.split("\t"))
    if a == 0 and b == 0:
        return ("uptodate", name)
    if b == 0 and a > 0:
        return ("ahead", f"{name} (ahead {a})")
    if a > 0 and b > 0:
        return ("diverged", f"{name} (ahead {a}/behind {b}, dirty {ndirty})")
    if sh(["git", "pull", "--ff-only", "--quiet"], p, 90)[0] == 0:
        return ("pulled", f"{name} (+{b})")
    return ("dirty_behind", f"{name} (behind {b}, dirty {ndirty})")


def _list_owner_repos(owner: str) -> list[dict] | None:
    rc, out, _ = sh(
        ["gh", "repo", "list", owner, "--limit", "400",
         "--json", "name,createdAt,isPrivate,isFork,nameWithOwner"],
        t=60,
    )
    if rc != 0:
        return None
    try:
        repos = json.loads(out)
    except json.JSONDecodeError:
        return None
    return repos if isinstance(repos, list) else []


def new_remote_repos(owners: list[str] | None = None):
    owners = owners or discover_owners()
    local = local_clone_keys()
    excluded = excluded_repo_names()
    fresh: list[str] = []
    list_errors: list[str] = []

    for owner in owners:
        repos = _list_owner_repos(owner)
        if repos is None:
            list_errors.append(owner)
            continue
        for r in repos:
            name = r.get("name", "")
            full = (r.get("nameWithOwner") or f"{owner}/{name}").lower()
            if not name:
                continue
            if name.lower() in excluded:
                continue
            if full in local or name.lower() in local:
                continue
            if age_min(r.get("createdAt", "")) > NEWWIN:
                continue
            age = int(age_min(r.get("createdAt", "")))
            label = f"{owner}/{name} ({age}min old"
            if r.get("isPrivate"):
                label += ", PRIVATE"
            if r.get("isFork"):
                label += ", FORK"
            label += ")"
            fresh.append(label)

    fresh.sort()
    return fresh, list_errors


def run_pass():
    owners = discover_owners()
    vault = vault_repo_name()
    buckets = {}
    for name, p in local_repos():
        k, v = sync_one(name, p)
        buckets.setdefault(k, []).append(v)
    fresh, list_errors = new_remote_repos(owners)
    attention = bool(
        buckets.get("diverged")
        or buckets.get("dirty_behind")
        or fresh
        or list_errors
    )
    stamp = now().strftime("%Y-%m-%dT%H:%MZ")
    lines = [
        f"# gitsync {stamp}  ATTENTION={'YES' if attention else 'no'}",
        f"pulled={len(buckets.get('pulled', []))} uptodate={len(buckets.get('uptodate', []))} "
        f"ahead={len(buckets.get('ahead', []))} diverged={len(buckets.get('diverged', []))} "
        f"dirty_behind={len(buckets.get('dirty_behind', []))} no_upstream={len(buckets.get('no_up', []))} "
        f"fetch_err={len(buckets.get('ferr', []))} new_remote={len(fresh)} "
        f"owners={len(owners)} vault_skip={vault or 'none'}",
    ]
    if buckets.get("pulled"):
        lines.append("PULLED: " + "; ".join(buckets["pulled"]))
    if buckets.get("diverged"):
        lines.append("DIVERGED: " + "; ".join(buckets["diverged"]))
    if buckets.get("dirty_behind"):
        lines.append("DIRTY_BEHIND: " + "; ".join(buckets["dirty_behind"]))
    if fresh:
        lines.append("NEW_REMOTE (not cloned): " + "; ".join(fresh))
    if list_errors:
        lines.append("LIST_ERR: " + "; ".join(list_errors))
    if buckets.get("ferr"):
        lines.append("FETCH_ERR: " + "; ".join(buckets["ferr"]))
    body = "\n".join(lines) + "\n"
    tmp = STATUS + ".tmp"
    with open(tmp, "w") as f:
        f.write(body)
    os.replace(tmp, STATUS)
    with open(LOG, "a") as f:
        f.write(lines[0] + " | " + lines[1] + "\n")


def main():
    once = "--once" in sys.argv[1:]
    with open(PIDFILE, "w") as f:
        f.write(str(os.getpid()))
    if once:
        run_pass()
        return
    while True:
        try:
            run_pass()
        except Exception as e:
            with open(LOG, "a") as f:
                f.write(f"# pass error {e!r}\n")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
