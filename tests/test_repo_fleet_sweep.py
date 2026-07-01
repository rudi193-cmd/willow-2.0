import subprocess
from pathlib import Path

from scripts.repo_fleet_sweep import find_repos, survey_repo


def _mk_repo(path: Path) -> None:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "master", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "--allow-empty", "-q", "-m", "init"], check=True)


def test_find_repos_and_clean_survey(tmp_path):
    _mk_repo(tmp_path / "alpha")
    (tmp_path / "not-a-repo").mkdir()
    repos = find_repos(tmp_path)
    assert [r.name for r in repos] == ["alpha"]

    s = survey_repo(repos[0], branch_limit=15)
    assert s["repo"] == "alpha"
    assert s["branch"] == "master"
    assert s["findings"] == []


def test_untracked_source_is_flagged(tmp_path):
    _mk_repo(tmp_path / "beta")
    (tmp_path / "beta" / "loose_tool.py").write_text("print(1)\n")
    s = survey_repo(tmp_path / "beta", branch_limit=15)
    assert any("untracked source" in f for f in s["findings"])
    assert "loose_tool.py" in s["untracked_source"]


def test_branch_litter_threshold(tmp_path):
    _mk_repo(tmp_path / "gamma")
    for i in range(3):
        subprocess.run(["git", "-C", str(tmp_path / "gamma"), "branch", f"b{i}"], check=True)
    s = survey_repo(tmp_path / "gamma", branch_limit=2)
    assert any("branch litter" in f for f in s["findings"])


def _commit(repo: Path, name: str, msg: str) -> None:
    (repo / name).write_text("x\n")
    subprocess.run(["git", "-C", str(repo), "add", name], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "-m", msg], check=True)


def _wt_add(repo: Path, wt_path: Path, branch: str, base: str = "master") -> None:
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", "-b", branch,
                    str(wt_path), base], check=True)


def test_merged_clean_worktree_is_flagged(tmp_path):
    repo = tmp_path / "delta"
    _mk_repo(repo)
    wt = tmp_path / "delta-wt"
    _wt_add(repo, wt, "feature-merged")
    _commit(wt, "f.txt", "feat")
    subprocess.run(["git", "-C", str(repo), "merge", "-q", "feature-merged"], check=True)

    s = survey_repo(repo, branch_limit=15)
    assert any("merged worktree" in f and "feature-merged" in f for f in s["findings"])


def test_unmerged_worktree_not_flagged(tmp_path):
    repo = tmp_path / "epsilon"
    _mk_repo(repo)
    wt = tmp_path / "epsilon-wt"
    _wt_add(repo, wt, "feature-open")
    _commit(wt, "f.txt", "feat")  # committed but NOT merged into master

    s = survey_repo(repo, branch_limit=15)
    assert not any("merged worktree" in f for f in s["findings"])


def test_dirty_merged_worktree_not_flagged(tmp_path):
    repo = tmp_path / "zeta"
    _mk_repo(repo)
    wt = tmp_path / "zeta-wt"
    _wt_add(repo, wt, "feature-dirty")  # fully in master (fast-forward-equal)
    (wt / "wip.txt").write_text("uncommitted\n")  # dirty → must not be flagged

    s = survey_repo(repo, branch_limit=15)
    assert not any("merged worktree" in f for f in s["findings"])
