"""One comment per deploy, found again by its marker and edited in place. stdlib only."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from .constants import GITHUB_API

MAX_PAGES = 30


def _default_http(method: str, url: str, token: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "dawnfix-receipt",
        **({"Content-Type": "application/json"} if data else {}),
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, None


class GitHubError(RuntimeError):
    pass


def _comparable(body: str) -> str:
    # The footer counts CE requests and cache hits, which differ on every run.
    return "\n".join(l for l in (body or "").splitlines() if not l.startswith("<sub>"))


def upsert_comment(repo: str, token: str, marker: str, body: str, *, pr: int | None = None,
                   sha: str | None = None, api: str = GITHUB_API, http=_default_http) -> tuple[str, int | None]:
    """Create or update the comment carrying `marker` on a PR (issue comments) or a commit.

    Returns (action, comment id): action is created, updated or unchanged.
    """
    if pr is None and not sha:
        raise GitHubError("need a PR number or a commit SHA")
    base = f"{api.rstrip('/')}/repos/{repo}"
    list_url = f"{base}/issues/{pr}/comments" if pr is not None else f"{base}/commits/{sha}/comments"
    edit_url = f"{base}/issues/comments/{{id}}" if pr is not None else f"{base}/comments/{{id}}"
    existing = None
    for page in range(1, MAX_PAGES + 1):
        status, items = http("GET", f"{list_url}?per_page=100&page={page}", token)
        if status != 200:
            raise GitHubError(f"listing comments failed: HTTP {status}")
        for c in items or []:
            if marker in (c.get("body") or ""):
                existing = c
        if not items or len(items) < 100:
            break
    if existing:
        if _comparable(existing.get("body")) == _comparable(body):
            return "unchanged", existing["id"]
        status, c = http("PATCH", edit_url.format(id=existing["id"]), token, {"body": body})
        if status != 200:
            raise GitHubError(f"updating comment failed: HTTP {status}")
        return "updated", existing["id"]
    status, c = http("POST", list_url, token, {"body": body})
    if status != 201:
        raise GitHubError(f"creating comment failed: HTTP {status}")
    return "created", (c or {}).get("id")
