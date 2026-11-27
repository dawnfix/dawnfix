"""GitHub: the same behaviour as the publish job of the reusable workflow, through the REST API
(urllib) instead of the gh CLI. github.com, or GitHub Enterprise Server by its host name."""
import re
from datetime import datetime, timezone
from urllib.parse import quote

from ..web import TokenRefused, host_of
from .base import LABELS, Change, Existing, HostAdapter, HostError

FIX_BRANCH = re.compile(r"^dawnfix/[0-9a-f]{16}$")
LABEL_SPEC = {"dawnfix": ("5319E7", "Opened by Dawnfix"),
              "AI-generated": ("BFD4F2", "AI-generated change (EU AI Act Art. 50)")}


class GitHubAdapter(HostAdapter):
    name = "GitHub"

    def __init__(self, ctx, token="", http=None):
        super().__init__(ctx, token, http)
        if not re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", ctx.repo or ""):
            raise HostError(f"not a GitHub repo path: '{ctx.repo}'")
        self.host = ctx.host or "github.com"
        if ctx.api_url:  # GitHub Actions' own API URL, for the server it runs on
            self.api = ctx.api_url.rstrip("/")
        elif self.host == "github.com":
            self.api = "https://api.github.com"
        else:  # GitHub Enterprise Server, named by DAWNFIX_REPO_HOST_URL
            self.api = f"https://{self.host}/api/v3"
        # The token goes to this host only, checked in web.Http before anything is sent.
        self.allowed = (host_of(self.api),)
        self._labels_ready = False
        self._default = ""

    # --- plumbing -------------------------------------------------------------------------
    def _list(self, path):
        d = self._call("GET", path) or []
        if not isinstance(d, list) or not all(isinstance(x, dict) for x in d):
            raise HostError(f"GitHub API GET {path.split('?')[0]}: not a list")
        return d

    def _call(self, method, path, body=None, ok=(200, 201)):
        r = self._req(method, f"{self.api}/repos/{self.ctx.repo}{path}", body)
        if r.status not in ok:
            what = "a redirect, not followed" if 300 <= r.status < 400 else f"HTTP {r.status or 'no answer'}"
            raise HostError(f"GitHub API {method} {path.split('?')[0]}: {what}")
        return r.data

    def _req(self, method, url, body=None):
        try:
            return self.http.request(method, url, body=body, token=self.token, allowed_hosts=self.allowed,
                                     headers={"Accept": "application/vnd.github+json",
                                              "X-GitHub-Api-Version": "2022-11-28"})
        except TokenRefused as e:
            raise HostError(str(e)) from None

    @staticmethod
    def _change(d, kind) -> Change:
        state = "merged" if d.get("merged_at") else d.get("state", "open")
        return Change(kind, int(d["number"]), state, d.get("html_url", ""))

    def _ensure_labels(self):
        if self._labels_ready:
            return
        for name, (color, desc) in LABEL_SPEC.items():
            # 422: it exists already. Any other failure is left to the call that uses the label.
            try:
                self._call("POST", "/labels", {"name": name, "color": color, "description": desc}, ok=(201, 422))
            except HostError:
                pass
        self._labels_ready = True

    # --- the interface --------------------------------------------------------------------
    def default_branch(self) -> str:
        if not self._default:
            r = self._req("GET", f"{self.api}/repos/{self.ctx.repo}")
            if r.status != 200 or not isinstance(r.data, dict) or not r.data.get("default_branch"):
                raise HostError(f"GitHub API GET /repos/{self.ctx.repo}: HTTP {r.status or 'no answer'}")
            self._default = r.data["default_branch"]
        return self._default

    def find_existing(self, fingerprint: str) -> Existing:
        if not re.match(r"^[0-9a-f]{16}$", fingerprint):
            raise ValueError("not a fingerprint")
        owner = self.ctx.repo.split("/")[0]
        prs = self._list(f"/pulls?state=all&per_page=10&head={quote(owner)}:dawnfix/{fingerprint}")
        prs = [p for p in prs if (p.get("head") or {}).get("ref") == f"dawnfix/{fingerprint}"]
        issues = self._list("/issues?state=open&labels=dawnfix&per_page=100")
        issues = [i for i in issues if "pull_request" not in i and fingerprint in (i.get("title") or "")]
        return Existing(change=self._change(prs[0], "change") if prs else None,
                        issue=self._change(issues[0], "issue") if issues else None)

    def open_draft_change(self, branch: str, title: str, body: str) -> Change:
        self._ensure_labels()
        d = self._call("POST", "/pulls", {"title": title, "head": branch, "base": self.default_branch(),
                                          "body": body, "draft": True}, ok=(201,))
        change = self._change(d, "change")
        self._call("POST", f"/issues/{change.number}/labels", {"labels": list(LABELS)})
        return change

    def open_issue(self, title: str, body: str, labels=LABELS) -> Change:
        self._ensure_labels()
        return self._change(self._call("POST", "/issues", {"title": title, "body": body, "labels": list(labels)},
                                       ok=(201,)), "issue")

    def comment(self, change: Change, body: str) -> None:
        self._call("POST", f"/issues/{change.number}/comments", {"body": body}, ok=(201,))

    def changes_opened_today(self) -> int:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        prs = self._list("/pulls?state=all&per_page=100&sort=created&direction=desc")
        return sum(1 for p in prs if FIX_BRANCH.match((p.get("head") or {}).get("ref", ""))
                   and str(p.get("created_at", "")).startswith(today))

    def push_url(self, token: str) -> str:
        return f"https://x-access-token:{token}@{self.host}/{self.ctx.repo}.git"
