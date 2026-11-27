"""Bitbucket Cloud: the publish stage's calls through the REST API 2.0 (urllib), the same
behaviour as the GitHub and GitLab adapters. bitbucket.org only (Bitbucket Data Center has
another API and is not supported).

- Auth, either:
  - a repository (or project or workspace) access token: `Authorization: Bearer <token>`; git
    pushes as `x-token-auth`. What CI usually uses.
  - an Atlassian API token of a user: `Authorization: Basic <email:token>` (DAWNFIX_BITBUCKET_EMAIL
    names the account's email, not a secret); git pushes as `x-bitbucket-api-token-auth`.
  Either goes only to api.bitbucket.org, exactly, and no redirect is followed (web.Http).
- Pull requests are opened as drafts (`"draft": true`, the answer checked) and never merged.
  Bitbucket pull requests have no labels: the title starts with "dawnfix:", the description says
  it is AI-generated and carries the fingerprint marker, which dedupe looks for.
- Issues only when the repository's issue tracker is on (has_issues). With it off, an issue's
  text goes to the pipeline log (and the publish step's artifact keeps it): nothing is filed
  and nothing fails. Atlassian is retiring the Bitbucket issue tracker for many workspaces; the
  log is the honest fallback.
- Branches are pushed with "[skip ci]" in each commit message (Bitbucket's convention), so the
  push starts no pipeline by itself.
"""
import base64
import re
from datetime import datetime, timezone
from urllib.parse import quote

from ..scrub import REDACT, say
from ..web import TokenRefused, host_of
from .base import LABELS, Change, Existing, HostAdapter, HostError

API = "https://api.bitbucket.org/2.0"
FIX_BRANCH = re.compile(r"^dawnfix/[0-9a-f]{16}$")
REPO_PATH = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
EMAIL = re.compile(r"^[^\s:@]+@[^\s:@]+\.[^\s:@]+$")
STATES = {"OPEN": "open", "MERGED": "merged", "DECLINED": "closed", "SUPERSEDED": "closed",
          "new": "open", "open": "open", "on hold": "open", "resolved": "closed", "invalid": "closed",
          "duplicate": "closed", "wontfix": "closed", "closed": "closed"}
ALL_PR_STATES = '(state = "OPEN" OR state = "MERGED" OR state = "DECLINED" OR state = "SUPERSEDED")'
MARKER = re.compile(r"<!-- (dawnfix:fingerprint=[0-9a-f]{16}) -->")
# The git user names Bitbucket takes with each kind of token.
GIT_USER_ACCESS_TOKEN = "x-token-auth"
GIT_USER_API_TOKEN = "x-bitbucket-api-token-auth"


def _visible_marker(body: str) -> str:
    """Bitbucket's Markdown shows HTML comments as text: the marker becomes a plain last line."""
    return MARKER.sub(r"Dawnfix fingerprint: `\1`", body)


class BitbucketAdapter(HostAdapter):
    name = "Bitbucket"
    commit_note = "[skip ci]"

    def __init__(self, ctx, token="", http=None, user: str = ""):
        super().__init__(ctx, token, http)
        repo = ctx.repo or ""
        if not REPO_PATH.match(repo) or ".." in repo:
            raise HostError(f"not a Bitbucket repository path (workspace/repo): '{repo}'")
        if (ctx.host_url or "https://bitbucket.org").rstrip("/") != "https://bitbucket.org":
            raise HostError("Bitbucket Cloud (bitbucket.org) only: Bitbucket Data Center is not supported")
        if user and not EMAIL.match(user):
            raise HostError("DAWNFIX_BITBUCKET_EMAIL must be the email of the Atlassian account the API token is for")
        self.user = user
        if user and token:
            # Basic auth: the header value is a secret too, so it is redacted like the token.
            self._auth = ("Basic", base64.b64encode(f"{user}:{token}".encode()).decode())
            REDACT.add(self._auth[1])
        else:
            self._auth = ("Bearer", token)
        self.host = "bitbucket.org"
        self.allowed = (host_of(API),)
        self.repo_api = f"{API}/repositories/{repo}"
        self._info = None

    @property
    def auth_values(self) -> tuple[str, ...]:
        """Every form of the credential that could end up in text (for the publish guard)."""
        return tuple(v for v in (self.token, self._auth[1]) if v)

    # --- plumbing -------------------------------------------------------------------------
    def _call(self, method, path, body=None, ok=(200, 201)):
        scheme, cred = self._auth
        try:
            r = self.http.request(method, f"{self.repo_api}{path}", body=body, token=cred, scheme=scheme,
                                  allowed_hosts=self.allowed, headers={"Accept": "application/json"})
        except TokenRefused as e:
            raise HostError(str(e)) from None
        if r.status not in ok:
            what = "a redirect, not followed" if 300 <= r.status < 400 else f"HTTP {r.status or 'no answer'}"
            raise HostError(f"Bitbucket API {method} {path.split('?')[0] or '/'}: {what}")
        return r.data

    def _values(self, path):
        """The values of one page (pagelen 50; dawnfix needs no more than the newest few)."""
        d = self._call("GET", path)
        vals = d.get("values") if isinstance(d, dict) else None
        if not isinstance(vals, list) or not all(isinstance(x, dict) for x in vals):
            raise HostError(f"Bitbucket API GET {path.split('?')[0]}: not a page of values")
        return vals

    @staticmethod
    def _q(expr: str) -> str:
        return quote(expr, safe="")

    @staticmethod
    def _change(d, kind) -> Change:
        url = ((d.get("links") or {}).get("html") or {}).get("href", "")
        return Change(kind, int(d["id"]), STATES.get(str(d.get("state", "OPEN")), "open"), str(url))

    def _repo(self) -> dict:
        if self._info is None:
            d = self._call("GET", "")
            if not isinstance(d, dict):
                raise HostError("Bitbucket API GET /repositories/:repo: not a repository")
            self._info = d
        return self._info

    # --- the interface --------------------------------------------------------------------
    def default_branch(self) -> str:
        name = (self._repo().get("mainbranch") or {}).get("name")
        if not isinstance(name, str) or not name:
            raise HostError("Bitbucket API GET /repositories/:repo: no main branch")
        return name

    def issues_enabled(self) -> bool:
        return self._repo().get("has_issues") is True

    def find_existing(self, fingerprint: str) -> Existing:
        if not re.match(r"^[0-9a-f]{16}$", fingerprint):
            raise ValueError("not a fingerprint")
        branch = f"dawnfix/{fingerprint}"
        marker = f"dawnfix:fingerprint={fingerprint}"
        q = f'(source.branch.name = "{branch}" OR description ~ "{marker}") AND {ALL_PR_STATES}'
        prs = self._values(f"/pullrequests?pagelen=50&sort=-created_on&q={self._q(q)}")
        prs = [p for p in prs if ((p.get("source") or {}).get("branch") or {}).get("name") == branch
               or marker in str(p.get("description") or "")]
        issue = None
        if self.issues_enabled():
            q = f'(title ~ "{fingerprint}" OR content.raw ~ "{marker}") AND (state = "new" OR state = "open")'
            issues = self._values(f"/issues?pagelen=50&q={self._q(q)}")
            issues = [i for i in issues if fingerprint in str(i.get("title") or "")
                      or marker in str((i.get("content") or {}).get("raw") or "")]
            issue = self._change(issues[0], "issue") if issues else None
        return Existing(change=self._change(prs[0], "change") if prs else None, issue=issue)

    def open_draft_change(self, branch: str, title: str, body: str) -> Change:
        if not FIX_BRANCH.match(branch):
            raise HostError(f"not a dawnfix branch: '{branch}'")
        d = self._call("POST", "/pullrequests", {
            "title": title, "description": _visible_marker(body), "draft": True, "close_source_branch": False,
            "source": {"branch": {"name": branch}}, "destination": {"branch": {"name": self.default_branch()}}},
            ok=(201,))
        if not isinstance(d, dict) or "id" not in d:
            raise HostError("Bitbucket API POST /pullrequests: no pull request in the answer")
        if d.get("draft") is not True:
            raise HostError(f"Bitbucket opened pull request #{d['id']} but not as a draft; check it by hand")
        return self._change(d, "change")

    def open_issue(self, title: str, body: str, labels=LABELS) -> Change:
        if not self.issues_enabled():
            # No tracker: the text goes to this step's log (already through the secret guard).
            say(f"the repository's issue tracker is off, so nothing is filed. The issue Dawnfix would open "
                f"({', '.join(labels)}) follows; turn the tracker on (Repository settings > Features > Issues) "
                "to get issues instead")
            say(f"  | {title}")
            for line in _visible_marker(body).splitlines():
                say(f"  | {line}")
            return Change("log", 0, "open", self.ctx.run_url)
        text = _visible_marker(body) + f"\n\nLabels: {', '.join(labels)}\n"
        d = self._call("POST", "/issues", {"title": title, "content": {"raw": text}, "kind": "bug"}, ok=(201,))
        if not isinstance(d, dict) or "id" not in d:
            raise HostError("Bitbucket API POST /issues: no issue in the answer")
        return self._change(d, "issue")

    def comment(self, change: Change, body: str) -> None:
        kind = {"change": "pullrequests", "issue": "issues"}.get(change.kind)
        if kind is None:
            raise HostError(f"cannot comment on a {change.kind}")
        self._call("POST", f"/{kind}/{int(change.number)}/comments", {"content": {"raw": _visible_marker(body)}},
                   ok=(201,))

    def changes_opened_today(self) -> int:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        q = f'created_on >= {today}T00:00:00+00:00 AND source.branch.name ~ "dawnfix/" AND {ALL_PR_STATES}'
        prs = self._values(f"/pullrequests?pagelen=50&sort=-created_on&q={self._q(q)}")
        return sum(1 for p in prs if FIX_BRANCH.match(str(((p.get("source") or {}).get("branch") or {}).get("name") or ""))
                   and str(p.get("created_on", "")).startswith(today))

    def push_url(self, token: str) -> str:
        user = GIT_USER_API_TOKEN if self.user else GIT_USER_ACCESS_TOKEN
        return f"https://{user}:{quote(token, safe='')}@{self.host}/{self.ctx.repo}.git"
