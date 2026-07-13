"""Unit tests for host gitsync-loop (scripts/gitsync/gitsync-loop.py)."""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

GITSYNC_ROOT = Path(__file__).resolve().parents[1] / "scripts" / "gitsync"
SPEC = importlib.util.spec_from_file_location("gitsync_loop", GITSYNC_ROOT / "gitsync-loop.py")
gitsync = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(gitsync)


class VaultTests(unittest.TestCase):
    def test_vault_repo_from_explicit_user(self):
        with mock.patch.object(gitsync, "_discover_vault_from_disk", return_value=""):
            with mock.patch.object(gitsync, "vault_identity_user", return_value="alice"):
                self.assertEqual(gitsync.vault_repo_name(), "alice-data-vault")

    def test_vault_repo_explicit_override(self):
        with mock.patch.dict(os.environ, {"GITSYNC_VAULT_REPO": "org/custom-vault"}):
            self.assertEqual(gitsync.vault_repo_name(), "custom-vault")

    def test_vault_discovered_from_disk(self):
        with mock.patch.object(gitsync, "_discover_vault_from_disk", return_value="alice-data-vault"):
            with mock.patch.object(gitsync, "vault_identity_user", return_value=""):
                self.assertEqual(gitsync.vault_repo_name(), "alice-data-vault")

    def test_excluded_skips_local_repo(self):
        with mock.patch.object(gitsync, "vault_repo_name", return_value="alice-data-vault"):
            with mock.patch.object(gitsync, "BASE", "/tmp/github"):
                with mock.patch("os.listdir", return_value=["alice-data-vault", "willow-2.0"]):
                    with mock.patch("os.path.isdir", side_effect=lambda p: True):
                        with mock.patch("os.path.join", side_effect=lambda *a: "/".join(a)):
                            repos = gitsync.local_repos()
        names = [n for n, _ in repos]
        self.assertNotIn("alice-data-vault", names)


class DiscoverOwnersTests(unittest.TestCase):
    def test_env_override(self):
        with mock.patch.dict(os.environ, {"GITSYNC_OWNERS": "foo,bar"}):
            self.assertEqual(gitsync.discover_owners(), ["foo", "bar"])

    def test_config_plus_auto_orgs(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "owners.json"
            cfg.write_text(json.dumps({
                "owners": ["alice"],
                "auto_orgs": True,
                "exclude_owners": ["skip-me"],
            }), encoding="utf-8")
            with mock.patch.object(gitsync, "OWNERS_FILE", str(cfg)):
                with mock.patch.object(gitsync, "sh", return_value=(0, "almanac-data\nskip-me\n", "")):
                    owners = gitsync.discover_owners()
            self.assertEqual(owners, ["alice", "almanac-data"])

    def test_empty_owners_uses_github_login(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "owners.json"
            cfg.write_text(json.dumps({"owners": [], "auto_orgs": False}), encoding="utf-8")
            with mock.patch.object(gitsync, "OWNERS_FILE", str(cfg)):
                with mock.patch.object(gitsync, "github_login", return_value="alice"):
                    self.assertEqual(gitsync.discover_owners(), ["alice"])


class NewRemoteReposTests(unittest.TestCase):
    def test_flags_uncloned_org_repo(self):
        repos = [{
            "name": "new-vertical",
            "nameWithOwner": "almanac-data/new-vertical",
            "createdAt": gitsync.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "isPrivate": False,
            "isFork": False,
        }]
        with mock.patch.object(gitsync, "local_clone_keys", return_value=set()):
            with mock.patch.object(gitsync, "excluded_repo_names", return_value=set()):
                with mock.patch.object(gitsync, "_list_owner_repos", return_value=repos):
                    fresh, errs = gitsync.new_remote_repos(["almanac-data"])
        self.assertEqual(errs, [])
        self.assertEqual(len(fresh), 1)
        self.assertIn("almanac-data/new-vertical", fresh[0])

    def test_skips_vault_in_new_remote_scan(self):
        repos = [{
            "name": "alice-data-vault",
            "nameWithOwner": "alice/alice-data-vault",
            "createdAt": gitsync.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "isPrivate": True,
            "isFork": False,
        }]
        with mock.patch.object(gitsync, "local_clone_keys", return_value=set()):
            with mock.patch.object(gitsync, "excluded_repo_names", return_value={"alice-data-vault"}):
                with mock.patch.object(gitsync, "_list_owner_repos", return_value=repos):
                    fresh, errs = gitsync.new_remote_repos(["alice"])
        self.assertEqual(fresh, [])
