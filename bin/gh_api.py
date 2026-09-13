#!/usr/bin/env python3
"""Call the GitHub REST API using the stored custom.github credential.

Usage:
    gh_api.py METHOD PATH [--data '{...json...}'] [--param key=value ...]

Examples:
    gh_api.py GET /user
    gh_api.py GET /user/repos --param per_page=50
    gh_api.py POST /repos/octocat/hello-world/issues --data '{"title":"Bug"}'

PATH may be given with or without the leading /.
Prints the JSON response (pretty). Exits non-zero on HTTP errors.
"""
import json
import os
import sys
import urllib.parse
import urllib.request

for _p in ("/opt/hatch/skills/skill-creator/bin",
           os.path.dirname(os.path.abspath(__file__))):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)
from dynamic_credentials import (  # noqa: E402
    add_surrogate_to_request,
    read_json_response,
    read_response_body,
)

ALLOWED_HOSTS = ["api.github.com"]
BASE = "https://api.github.com"
CREDENTIAL = "custom.github"


def main(argv):
    if len(argv) < 3 or argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        return 0
    method = argv[1].upper()
    path = argv[2]
    if not path.startswith("/"):
        path = "/" + path
    data = None
    params = []
    i = 3
    while i < len(argv):
        if argv[i] == "--data":
            i += 1
            data = argv[i].encode("utf-8")
        elif argv[i] == "--param":
            i += 1
            k, _, v = argv[i].partition("=")
            params.append((k, v))
        else:
            print(f"unknown argument: {argv[i]}", file=sys.stderr)
            return 2
        i += 1

    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    add_surrogate_to_request(
        req, CREDENTIAL, entry_name="access_token", allowed_hosts=ALLOWED_HOSTS
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = read_response_body(resp)
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {err_body}", file=sys.stderr)
        return 1
    if not body.strip():
        print(json.dumps({"status": "ok (empty response)"}))
        return 0
    try:
        parsed = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        print(body.decode("utf-8", errors="replace"))
        return 0
    print(json.dumps(parsed, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
