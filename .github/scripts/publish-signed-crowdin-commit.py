#!/usr/bin/env python3
"""Publish downloaded locale files as a commit signed by the token-exchange app.

The Crowdin action writes the files into the workspace. Creating the commit
through GitHub's API, with no custom author, makes GitHub sign it as the
app that owns the installation token.
"""

import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

BRANCH = "l10n_crowdin_action"
BASE = "main"
COMMIT_HEADLINE = "New Crowdin translations by Github Action"
PR_TITLE = "chore: New Crowdin Translations by GitHub Action"
SOURCE_FILE = "locales/en/messages.json"


def git_bytes(*args):
    return subprocess.check_output(["git", *args])


def git_text(*args):
    return git_bytes(*args).decode().strip()


def api(method, path, body=None):
    repo = os.environ["GITHUB_REPOSITORY"]
    url = f"https://api.github.com/repos/{repo}{path}"
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", f"Bearer {os.environ['GH_TOKEN']}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    if body is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request) as response:
            raw = response.read().decode()
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        raw = error.read().decode()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"message": raw}
        return error.code, payload


def require(status, payload, action):
    if status not in (200, 201):
        message = payload.get("message", payload)
        sys.exit(f"Failed to {action}: HTTP {status} {message}")
    return payload


def graphql(query, variables):
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        method="POST",
    )
    request.add_header("Authorization", f"Bearer {os.environ['GH_TOKEN']}")
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        sys.exit(error.read().decode())
    if payload.get("errors"):
        sys.exit(json.dumps(payload["errors"], indent=2))
    return payload["data"]


def is_translation(path):
    return path.startswith("locales/") and path.endswith("/messages.json") and path != SOURCE_FILE


def locale_changes(base_sha):
    tracked = [
        path
        for path in git_text("ls-tree", "-r", "--name-only", base_sha, "locales").splitlines()
        if is_translation(path)
    ]
    on_disk = []
    for root, _dirs, files in os.walk("locales"):
        for name in files:
            path = os.path.join(root, name)
            if is_translation(path):
                on_disk.append(path)

    additions = []
    present = set(on_disk)
    for path in sorted(present):
        with open(path, "rb") as handle:
            content = handle.read()
        if path in tracked and git_bytes("show", f"{base_sha}:{path}") == content:
            continue
        additions.append(
            {"path": path, "contents": base64.b64encode(content).decode()}
        )

    deletions = [{"path": path} for path in sorted(set(tracked) - present)]
    return additions, deletions


def point_branch_at(sha):
    status, payload = api(
        "PATCH",
        f"/git/refs/heads/{BRANCH}",
        {"sha": sha, "force": True},
    )
    if status == 404:
        status, payload = api(
            "POST",
            "/git/refs",
            {"ref": f"refs/heads/{BRANCH}", "sha": sha},
        )
        require(status, payload, f"create {BRANCH}")
        return
    require(status, payload, f"point {BRANCH} at {BASE}")


def commit(base_sha, additions, deletions):
    file_changes = {}
    if additions:
        file_changes["additions"] = additions
    if deletions:
        file_changes["deletions"] = deletions
    data = graphql(
        """
        mutation($input: CreateCommitOnBranchInput!) {
          createCommitOnBranch(input: $input) {
            commit { oid }
          }
        }
        """,
        {
            "input": {
                "branch": {
                    "repositoryNameWithOwner": os.environ["GITHUB_REPOSITORY"],
                    "branchName": BRANCH,
                },
                "message": {"headline": COMMIT_HEADLINE},
                "expectedHeadOid": base_sha,
                "fileChanges": file_changes,
            }
        },
    )
    return data["createCommitOnBranch"]["commit"]["oid"]


def open_pull_request():
    owner = os.environ["GITHUB_REPOSITORY"].split("/", 1)[0]
    status, pulls = api(
        "GET",
        f"/pulls?head={owner}:{BRANCH}&base={BASE}&state=open",
    )
    require(status, pulls, "list pull requests")
    if pulls:
        print(f"Pull request already exists: {pulls[0]['html_url']}")
        return
    status, pull = api(
        "POST",
        "/pulls",
        {"title": PR_TITLE, "head": BRANCH, "base": BASE},
    )
    pull = require(status, pull, "create pull request")
    print(f"Pull request created: {pull['html_url']}")


def main():
    subprocess.check_call(["git", "fetch", "origin", BASE, "--depth=1"])
    base_sha = git_text("rev-parse", f"origin/{BASE}")
    additions, deletions = locale_changes(base_sha)
    if not additions and not deletions:
        print("No locale changes to publish")
        return

    print(f"Publishing {len(additions)} updated and {len(deletions)} deleted locale files")
    point_branch_at(base_sha)
    oid = commit(base_sha, additions, deletions)
    status, payload = api("GET", f"/commits/{oid}")
    payload = require(status, payload, "read commit")
    verification = payload["commit"]["verification"]
    author = payload["commit"]["author"]["name"]
    print(f"Commit {oid} author={author} verified={verification.get('verified')} reason={verification.get('reason')}")
    if not verification.get("verified"):
        sys.exit("GitHub did not verify the commit")
    open_pull_request()


if __name__ == "__main__":
    main()
