"""GitLab: the publish stage's calls through the REST API v4 (urllib), the same behaviour as the
GitHub adapter. gitlab.com, or a self-managed GitLab named by DAWNFIX_REPO_HOST_URL.

- The project is CI_PROJECT_ID when GitLab CI gave it (and DAWNFIX_REPO did not override the
  path), else the URL-encoded project path (group/subgroup/project).
- The token (a project access token: role Developer, scopes api and write_repository) goes in
  the PRIVATE-TOKEN header, only to the exact API host, and no redirect is followed (web.Http).
- Merge requests are opened as drafts ("Draft: " title) and never merged; merge when the
  pipeline succeeds is never set.
"""
import re
from datetime import datetime, timezone
from urllib.parse import quote

from ..web import TokenRefused, host_of
from .base import LABELS, Change, Existing, HostAdapter, HostError

FIX_BRANCH = re.compile(r"^dawnfix/[0-9a-f]{16}$")
PROJECT_PATH = re.compile(r"^[A-Za-z0-9_.][A-Za-z0-9_.-]*(/[A-Za-z0-9_.][A-Za-z0-9_.-]*){1,20}$")
LABEL_SPEC = {"dawnfix": ("#5319E7", "Opened by Dawnfix"),
              "AI-generated": ("#BFD4F2", "AI-generated change (EU AI Act Art. 50)")}
STATES = {"opened": "open", "reopened": "open", "closed": "closed", "locked": "closed", "merged": "merged"}
DRAFT = "Draft: "


class GitLabAdapter(HostAdapter):
    name = "GitLab"
    push_options = ("ci.skip",)

    def __init__(self, ctx, token="", http=None):
        super().__init__(ctx, token, http)
        if not PROJECT_PATH.match(ctx.repo or "") or ".." in ctx.repo:
            raise HostError(f"not a GitLab project path: '{ctx.repo}'")
        host_url = (ctx.host_url or "").rstrip("/")
        # gitlab.com, or the server the owner named in DAWNFIX_REPO_HOST_URL. A server only the CI
        # variables name (CI_SERVER_HOST) is never sent the token.
        if host_url != "https://gitlab.com" and ctx.host_source != "override":
            raise HostError(
                f"the GitLab server '{ctx.host or '?'}' is not gitlab.com: for a self-managed GitLab set "
                "DAWNFIX_REPO_HOST=gitlab and DAWNFIX_REPO_HOST_URL=https://<your GitLab host> in the publish job")
        self.host_url = host_url
        self.host = ctx.host
        self.api = f"{host_url}/api/v4"
        self.allowed = (host_of(self.api),)
        pid = ctx.project_id if re.match(r"^[0-9]{1,20}$", ctx.project_id or "") else ""
        self.project = f"{self.api}/projects/{pid or quote(ctx.repo, safe='')}"
        self._labels_ready = False
        self._info = None

    # --- plumbing -------------------------------------------------------------------------
    def _req(self, method, url, body=None):
        try:
            return self.http.request(method, url, body=body, token=self.token, token_header="PRIVATE-TOKEN",
                                     allowed_hosts=self.allowed, headers={"Accept": "application/json"})
        except TokenRefused as e:
            raise HostError(str(e)) from None

    def _call(self, method, path, body=None, ok=(200, 201)):
        r = self._req(method, f"{self.project}{path}", body)
        if r.status not in ok:
            what = "a redirect, not followed" if 300 <= r.status < 400 else f"HTTP {r.status or 'no answer'}"
            raise HostError(f"GitLab API {method} {path.split('?')[0] or '/'}: {what}")
        return r.data

    def _list(self, path):
        d = self._call("GET", path)
        if d is None:
            return []
        if not isinstance(d, list) or not all(isinstance(x, dict) for x in d):
            raise HostError(f"GitLab API GET {path.split('?')[0]}: not a list")
        return d

    @staticmethod
    def _change(d, kind) -> Change:
        return Change(kind, int(d["iid"]), STATES.get(str(d.get("state", "opened")), "open"), str(d.get("web_url", "")))

    def _ensure_labels(self):
        if self._labels_ready:
            return
        for name, (color, desc) in LABEL_SPEC.items():
            # 409: it exists already. Any other failure is left to the call that uses the label.
            try:
                self._call("POST", "/labels", {"name": name, "color": color, "description": desc}, ok=(201, 409))
            except HostError:
                pass
        self._labels_ready = True

    # --- the interface --------------------------------------------------------------------
    def _project(self) -> dict:
        if self._info is None:
            d = self._call("GET", "")
            if not isinstance(d, dict):
                raise HostError("GitLab API GET /projects/:id: not a project")
            self._info = d
        return self._info

    def default_branch(self) -> str:
        d = self._project()
        if not isinstance(d.get("default_branch"), str) or not d["default_branch"]:
            raise HostError("GitLab API GET /projects/:id: no default branch")
        return d["default_branch"]

    def ci_config_path(self) -> str:
        """Settings > CI/CD > CI/CD configuration file, when set (a path in this repo, or a file
        in another project or a URL, which no change here can touch)."""
        v = self._project().get("ci_config_path")
        return v if isinstance(v, str) else ""

    def find_existing(self, fingerprint: str) -> Existing:
        if not re.match(r"^[0-9a-f]{16}$", fingerprint):
            raise ValueError("not a fingerprint")
        branch = f"dawnfix/{fingerprint}"
        mrs = self._list(f"/merge_requests?state=all&per_page=20&source_branch={quote(branch, safe='')}")
        mrs = [m for m in mrs if m.get("source_branch") == branch]
        marker = f"dawnfix:fingerprint={fingerprint}"
        issues = self._list(f"/issues?state=opened&labels=dawnfix&per_page=100&search={fingerprint}&in=title,description")
        issues = [i for i in issues if fingerprint in str(i.get("title") or "") or marker in str(i.get("description") or "")]
        return Existing(change=self._change(mrs[0], "change") if mrs else None,
                        issue=self._change(issues[0], "issue") if issues else None)

    def open_draft_change(self, branch: str, title: str, body: str) -> Change:
        if not FIX_BRANCH.match(branch):
            raise HostError(f"not a dawnfix branch: '{branch}'")
        self._ensure_labels()
        title = title if title.startswith(DRAFT) else DRAFT + title
        d = self._call("POST", "/merge_requests", {
            "source_branch": branch, "target_branch": self.default_branch(), "title": title, "description": body,
            "labels": ",".join(LABELS), "remove_source_branch": False, "squash": False}, ok=(201,))
        if not isinstance(d, dict) or "iid" not in d:
            raise HostError("GitLab API POST /merge_requests: no merge request in the answer")
        if not (d.get("draft") is True or d.get("work_in_progress") is True or str(d.get("title", "")).startswith(DRAFT)):
            raise HostError(f"GitLab opened merge request !{d['iid']} but not as a draft; check it by hand")
        return self._change(d, "change")

    def open_issue(self, title: str, body: str, labels=LABELS) -> Change:
        self._ensure_labels()
        d = self._call("POST", "/issues", {"title": title, "description": body, "labels": ",".join(labels)}, ok=(201,))
        if not isinstance(d, dict) or "iid" not in d:
            raise HostError("GitLab API POST /issues: no issue in the answer")
        return self._change(d, "issue")

    def comment(self, change: Change, body: str) -> None:
        kind = "merge_requests" if change.kind == "change" else "issues"
        self._call("POST", f"/{kind}/{int(change.number)}/notes", {"body": body}, ok=(201,))

    def changes_opened_today(self) -> int:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        mrs = self._list(f"/merge_requests?state=all&per_page=100&order_by=created_at&sort=desc"
                         f"&created_after={today}T00:00:00Z")
        return sum(1 for m in mrs if FIX_BRANCH.match(str(m.get("source_branch") or ""))
                   and str(m.get("created_at", "")).startswith(today))

    def push_url(self, token: str) -> str:
        return f"https://oauth2:{quote(token, safe='')}@{self.host}/{self.ctx.repo}.git"
