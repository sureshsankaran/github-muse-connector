# GitHub connector skill (Muse)

A Muse workspace skill for managing GitHub repos through the GitHub REST
API. Authentication uses a personal access token stored in the assistant's
Secure Vault — the token never appears in this repo, in chat, or in logs.

## Layout

- `SKILL.md` — skill definition: purpose, tooling, auth model, operating rules
- `bin/gh_api.py` — generic GitHub REST client (`METHOD PATH [--data JSON] [--param k=v]`)
- `bin/gh_push.py` — push a local directory to a repo branch via the Git Data API
- `bin/dynamic_credentials.py` — vendored helper that exchanges the stored
  credential for a request surrogate (`hsurr:*`) at call time

## Auth model

The CLIs never read a raw secret. They attach a surrogate token to the
request; the runtime swaps it for the real credential on approved egress to
`api.github.com` only. If the bundled helper exists at
`/opt/hatch/skills/skill-creator/bin/dynamic_credentials.py` it is used,
otherwise the vendored copy in `bin/` is used.

## Usage

```sh
# Who am I?
bin/gh_api.py GET /user

# List repos
bin/gh_api.py GET /user/repos --param per_page=50

# Create an issue
bin/gh_api.py POST /repos/OWNER/REPO/issues --data '{"title":"Bug","body":"..."}'

# Push a directory to a branch (creates the branch on first push)
bin/gh_push.py ./my-project OWNER/REPO main "commit message"
```

`gh_push.py` skips build output and archives (`.git/`, `.gradle/`, `out/`,
`build/`, `__pycache__/`, `*.apk`, `*.zip`, `*.pyc`, `local.properties`).
It pushes the full directory tree as a single commit; on an empty repo it
seeds the first file through the Contents API, then completes the push
through the Git Data API.
