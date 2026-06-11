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
