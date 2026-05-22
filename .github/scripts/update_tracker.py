import json
import os
import re
import subprocess
import sys
from datetime import datetime

AUTHOR = "rudi193-cmd"
REPO = "rudi193-cmd/willow-2.0"

SEARCH_QUERY = """
query($q: String!, $cursor: String) {
  search(query: $q, type: ISSUE, first: 100, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on PullRequest {
        number
        title
        url
        repository { nameWithOwner owner { login } }
      }
    }
  }
}
"""


def run_gh_graphql(query: str, variables: dict) -> dict:
    payload = json.dumps({"query": query, "variables": variables})
    result = subprocess.run(
        ["gh", "api", "graphql", "--input", "-"],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(result.stderr or result.stdout, file=sys.stderr)
        raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)
    data = json.loads(result.stdout)
    if data.get("errors"):
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    return data["data"]


def run_gh_search(state_args: list[str]) -> list[dict]:
    """Find PRs by author via GraphQL search (works in Actions; gh search prs does not)."""
    if state_args == ["--merged"]:
        q = f"author:{AUTHOR} type:pr is:merged"
    elif state_args == ["--state", "open"]:
        q = f"author:{AUTHOR} type:pr state:open"
    elif state_args == ["--state", "closed"]:
        q = f"author:{AUTHOR} type:pr state:closed"
    else:
        raise ValueError(f"unsupported search args: {state_args}")

    prs: list[dict] = []
    cursor = None
    while True:
        variables = {"q": q, "cursor": cursor}
        data = run_gh_graphql(SEARCH_QUERY, variables)
        search = data["search"]
        for node in search["nodes"]:
            if not node:
                continue
            prs.append(
                {
                    "number": node["number"],
                    "title": node["title"],
                    "url": node["url"],
                    "repository": node["repository"],
                }
            )
        if not search["pageInfo"]["hasNextPage"]:
            break
        cursor = search["pageInfo"]["endCursor"]

    return [pr for pr in prs if not pr["repository"]["nameWithOwner"].startswith(f"{AUTHOR}/")]


def main():
    print("Fetching PRs via GraphQL search...")
    open_prs = run_gh_search(["--state", "open"])
    merged_prs = run_gh_search(["--merged"])
    all_closed_prs = run_gh_search(["--state", "closed"])

    print(
        f"Found {len(open_prs)} open, {len(merged_prs)} merged, "
        f"{len(all_closed_prs)} closed (external repos only)"
    )
    if os.environ.get("GITHUB_ACTIONS") == "true" and not (open_prs or merged_prs or all_closed_prs):
        print(
            "WARNING: zero external PRs in CI — check GH_TOKEN / UPSTREAM_TRACKER_PAT",
            file=sys.stderr,
        )

    merged_urls = {pr["url"] for pr in merged_prs}
    closed_prs = [pr for pr in all_closed_prs if pr["url"] not in merged_urls]

    today = datetime.now().strftime("%Y-%m-%d")
    issue_body = f"## Upstream Contribution Status — {today}\n\n"

    if open_prs:
        issue_body += "### ⏳ Still Open\n\n"
        for pr in open_prs:
            issue_body += f"- [{pr['repository']['nameWithOwner']} #{pr['number']}]({pr['url']}) — {pr['title']}\n"
        issue_body += "\n"

    if merged_prs:
        issue_body += "### ✅ Merged\n\n"
        for pr in merged_prs:
            issue_body += f"- [{pr['repository']['nameWithOwner']} #{pr['number']}]({pr['url']}) — {pr['title']}\n"
        issue_body += "\n"

    if closed_prs:
        issue_body += "### ❌ Closed (Not Merged)\n\n"
        for pr in closed_prs:
            issue_body += f"- [{pr['repository']['nameWithOwner']} #{pr['number']}]({pr['url']}) — {pr['title']}\n"
        issue_body += "\n"

    issue_body += "---\n_When PRs merge: close this issue, update CONTRIBUTORS.md, add badge to README._\n"

    print("Updating issue...")
    issue_result = subprocess.run(
        ["gh", "issue", "list", "--repo", REPO, "--label", "upstream-tracker", "--state", "open", "--json", "number"],
        capture_output=True,
        text=True,
        check=True,
    )
    issues = json.loads(issue_result.stdout)
    if issues:
        issue_num = str(issues[0]["number"])
        with open("issue_body.md", "w", encoding="utf-8") as f:
            f.write(issue_body)
        subprocess.run(["gh", "issue", "edit", issue_num, "--repo", REPO, "--body-file", "issue_body.md"], check=True)
        print(f"Updated issue #{issue_num}")
    else:
        print("Could not find upstream-tracker issue")

    print("Updating CONTRIBUTORS.md...")
    with open("CONTRIBUTORS.md", encoding="utf-8") as f:
        content = f.read()

    new_table = (
        "| Project | Maintainer | What we contributed | Status |\n"
        "|---------|-----------|---------------------|--------|\n"
    )

    for pr in merged_prs:
        owner = pr["repository"]["owner"]["login"]
        repo = pr["repository"]["nameWithOwner"]
        new_table += f"| [{repo}](https://github.com/{repo}) | {owner} | {pr['title']} | [PR #{pr['number']}]({pr['url']}) merged |\n"
    for pr in open_prs:
        owner = pr["repository"]["owner"]["login"]
        repo = pr["repository"]["nameWithOwner"]
        new_table += f"| [{repo}](https://github.com/{repo}) | {owner} | {pr['title']} | [PR #{pr['number']}]({pr['url']}) open |\n"
    for pr in closed_prs:
        owner = pr["repository"]["owner"]["login"]
        repo = pr["repository"]["nameWithOwner"]
        new_table += f"| [{repo}](https://github.com/{repo}) | {owner} | {pr['title']} | [PR #{pr['number']}]({pr['url']}) closed |\n"

    pattern = (
        r"\| Project \| Maintainer \| What we contributed \| Status \|\n"
        r"\|---------\|-----------\|---------------------\|--------\|\n"
        r"(?:\|.*\|\n)*"
    )
    updated, count = re.subn(pattern, new_table, content, count=1)
    if count != 1:
        raise RuntimeError("CONTRIBUTORS.md upstream table header not found — regex did not match")

    with open("CONTRIBUTORS.md", "w", encoding="utf-8") as f:
        f.write(updated)
    print("Updated CONTRIBUTORS.md")


if __name__ == "__main__":
    main()
