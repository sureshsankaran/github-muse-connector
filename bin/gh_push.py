#!/usr/bin/env python3
"""Push a local directory to a GitHub repo branch via the Git Data API.

Stays on api.github.com (the only host the custom.github connector allows),
so no git-over-HTTPS to github.com is needed.

Usage:
    gh_push.py <local_dir> <owner/repo> <branch> <commit message>

Skips: .git/, .gradle/, out/, */build/, *.apk, *.zip, local.properties
"""
import base64
import json
import os
import sys
import urllib.request

for _p in ("/opt/hatch/skills/skill-creator/bin",
           os.path.dirname(os.path.abspath(__file__))):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)
from dynamic_credentials import (  # noqa: E402
    add_surrogate_to_request,
    read_response_body,
)

ALLOWED_HOSTS = ["api.github.com"]
BASE = "https://api.github.com"
CREDENTIAL = "custom.github"
SKIP_DIRS = {".git", ".gradle", "out", "build", "__pycache__"}
SKIP_EXT = {".apk", ".zip", ".pyc"}
SKIP_FILES = {"local.properties"}


class ApiError(RuntimeError):
    pass


def api(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    add_surrogate_to_request(
        req, CREDENTIAL, entry_name="access_token", allowed_hosts=ALLOWED_HOSTS
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = read_response_body(resp)
            return json.loads(raw.decode()) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ApiError(f"{method} {path} -> HTTP {exc.code}: {detail}")


def collect_files(root):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn in SKIP_FILES or os.path.splitext(fn)[1] in SKIP_EXT:
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            files.append((rel, full))
    return sorted(files)


def main(argv):
    if len(argv) != 5:
        print(__doc__.strip())
        return 2
    local_dir, repo, branch, message = argv[1], argv[2], argv[3], argv[4]
    if not os.path.isdir(local_dir):
        print(f"not a directory: {local_dir}", file=sys.stderr)
        return 2

    files = collect_files(local_dir)
    if not files:
        print("no files to push", file=sys.stderr)
        return 2
    print(f"pushing {len(files)} files to {repo}@{branch} ...")

    try:
        ref = api("GET", f"/repos/{repo}/git/ref/heads/{branch}")
        parent_sha = ref["object"]["sha"]
        print(f"parent commit: {parent_sha[:7]}")
    except ApiError as exc:
        if "HTTP 404" not in str(exc) and "Git Repository is empty" not in str(exc):
            raise
        parent_sha = None
        # The git-database API refuses an empty repo, so seed it with one
        # file through the Contents API, then continue normally.
        seed_rel, seed_full = files[0]
        with open(seed_full, "rb") as fh:
            seed_b64 = base64.b64encode(fh.read()).decode("ascii")
        api("PUT", f"/repos/{repo}/contents/{seed_rel}",
            {"message": message, "content": seed_b64, "branch": branch})
        ref = api("GET", f"/repos/{repo}/git/ref/heads/{branch}")
        parent_sha = ref["object"]["sha"]
        print(f"seeded empty repo, parent commit: {parent_sha[:7]}")

    tree_entries = []
    for rel, full in files:
        with open(full, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode("ascii")
        blob = api("POST", f"/repos/{repo}/git/blobs",
                   {"content": b64, "encoding": "base64"})
        tree_entries.append({"path": rel, "mode": "100644",
                             "type": "blob", "sha": blob["sha"]})
        print(f"  blob {rel}")
    if os.path.isfile(os.path.join(local_dir, "build-manual.sh")):
        for e in tree_entries:
            if e["path"] == "build-manual.sh":
                e["mode"] = "100755"

    tree_body = {"tree": tree_entries}
    commit = api("POST", f"/repos/{repo}/git/commits",
                 {"message": message, "tree": api("POST", f"/repos/{repo}/git/trees", tree_body)["sha"],
                  "parents": [parent_sha] if parent_sha else []})
    commit_sha = commit["sha"]
    print(f"commit: {commit_sha[:7]}")

    if parent_sha:
        api("PATCH", f"/repos/{repo}/git/refs/heads/{branch}", {"sha": commit_sha})
    else:
        api("POST", f"/repos/{repo}/git/refs",
            {"ref": f"refs/heads/{branch}", "sha": commit_sha})
    print(f"pushed {repo}@{branch} -> {commit_sha[:7]}")
    print(f"https://github.com/{repo}/commit/{commit_sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
