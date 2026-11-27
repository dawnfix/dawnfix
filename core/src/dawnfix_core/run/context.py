"""Where this run is: the CI system and the repo, read from the CI's own environment variables
into one CiContext. GitHub Actions, GitLab CI, Bitbucket Pipelines and CircleCI.

DAWNFIX_REPO_HOST (github | gitlab | bitbucket) and DAWNFIX_REPO (the repo path) override what
is detected, e.g. for a CircleCI project whose remote URL is not set. When DAWNFIX_REPO_HOST is
set, the server follows from it alone: the public one (github.com, gitlab.com, bitbucket.org),
or DAWNFIX_REPO_HOST_URL (https://host[:port]) for a self-hosted GitHub Enterprise Server,
GitLab or Bitbucket server. A host detected from CI variables is never used with it, so a
token cannot be sent to a server the CI happened to name.
"""
import re
from dataclasses import asdict, dataclass
from urllib.parse import urlsplit

REPO_HOSTS = ("github", "gitlab", "bitbucket")
PUBLIC = {"github": "https://github.com", "gitlab": "https://gitlab.com", "bitbucket": "https://bitbucket.org"}


class ContextError(Exception):
    pass


@dataclass(frozen=True)
class CiContext:
    provider: str    # github-actions | gitlab-ci | bitbucket-pipelines | circleci | local
    repo: str        # owner/name (GitLab: group/subgroup/project)
    host: str        # github.com, gitlab.com, bitbucket.org, or a self-hosted host name
    repo_host: str   # github | gitlab | bitbucket | "" (unknown): picks the HostAdapter
    commit: str
    branch: str
    run_id: str
    run_url: str
    oidc: bool       # the job can get an OIDC token (cloud credentials) right now
    host_url: str = ""  # https://<host>: the repo host's web URL (push URL and API derive from it)
    api_url: str = ""   # GitHub Actions' own GITHUB_API_URL, when the repo host was detected there
    host_source: str = ""  # override (DAWNFIX_REPO_HOST_URL) | public (DAWNFIX_REPO_HOST alone) | ci
    project_id: str = ""   # GitLab CI_PROJECT_ID (numeric), unless DAWNFIX_REPO names the project

    def as_dict(self) -> dict:
        return asdict(self)


def _repo_host(host: str) -> str:
    h = host.lower()
    if h == "github.com":
        return "github"
    if h == "bitbucket.org":
        return "bitbucket"
    if "gitlab" in h:
        return "gitlab"
    return ""


def parse_remote(url: str) -> tuple[str, str]:
    """(host, repo path) of a git remote URL: https://host/a/b(.git) or git@host:a/b(.git)."""
    url = (url or "").strip()
    m = re.match(r"^(?:https?|ssh|git)://(?:[^@/]+@)?([^/:]+)(?::\d+)?/(.+?)(?:\.git)?/?$", url) or \
        re.match(r"^[^@/]+@([^:/]+):(.+?)(?:\.git)?/?$", url)
    return (m.group(1), m.group(2)) if m else ("", "")


def detect(env) -> CiContext:
    g = lambda k: env.get(k, "") or ""
    if g("GITHUB_ACTIONS") == "true":
        server = g("GITHUB_SERVER_URL") or "https://github.com"
        host = re.sub(r"^https?://", "", server).rstrip("/")
        repo = g("GITHUB_REPOSITORY")
        ctx = dict(provider="github-actions", repo=repo, host=host, repo_host="github" if host else "",
                   commit=g("GITHUB_SHA"), branch=g("GITHUB_HEAD_REF") or g("GITHUB_REF_NAME"),
                   run_id=g("GITHUB_RUN_ID"),
                   run_url=f"{server.rstrip('/')}/{repo}/actions/runs/{g('GITHUB_RUN_ID')}" if repo else "",
                   oidc=bool(g("ACTIONS_ID_TOKEN_REQUEST_URL") and g("ACTIONS_ID_TOKEN_REQUEST_TOKEN")),
                   api_url=g("GITHUB_API_URL"))
    elif g("GITLAB_CI") == "true":
        host = g("CI_SERVER_HOST") or "gitlab.com"
        ctx = dict(provider="gitlab-ci", repo=g("CI_PROJECT_PATH"), host=host, repo_host="gitlab",
                   project_id=g("CI_PROJECT_ID") if re.match(r"^[0-9]{1,20}$", g("CI_PROJECT_ID")) else "",
                   commit=g("CI_COMMIT_SHA"), branch=g("CI_COMMIT_BRANCH") or g("CI_COMMIT_REF_NAME"),
                   run_id=g("CI_PIPELINE_ID"), run_url=g("CI_JOB_URL") or g("CI_PIPELINE_URL"),
                   # GitLab ID tokens are named by the pipeline (id_tokens:); DAWNFIX_OIDC_TOKEN_VAR names it.
                   oidc=bool(g(g("DAWNFIX_OIDC_TOKEN_VAR")) if g("DAWNFIX_OIDC_TOKEN_VAR") else g("GITLAB_OIDC_TOKEN")))
    elif g("BITBUCKET_BUILD_NUMBER"):
        repo = g("BITBUCKET_REPO_FULL_NAME")
        ctx = dict(provider="bitbucket-pipelines", repo=repo, host="bitbucket.org", repo_host="bitbucket",
                   commit=g("BITBUCKET_COMMIT"), branch=g("BITBUCKET_BRANCH"), run_id=g("BITBUCKET_BUILD_NUMBER"),
                   run_url=f"https://bitbucket.org/{repo}/pipelines/results/{g('BITBUCKET_BUILD_NUMBER')}" if repo else "",
                   oidc=bool(g("BITBUCKET_STEP_OIDC_TOKEN")))
    elif g("CIRCLECI") == "true":
        host, path = parse_remote(g("CIRCLE_REPOSITORY_URL"))
        repo = path or (f"{g('CIRCLE_PROJECT_USERNAME')}/{g('CIRCLE_PROJECT_REPONAME')}"
                        if g("CIRCLE_PROJECT_USERNAME") and g("CIRCLE_PROJECT_REPONAME") else "")
        ctx = dict(provider="circleci", repo=repo, host=host, repo_host=_repo_host(host),
                   commit=g("CIRCLE_SHA1"), branch=g("CIRCLE_BRANCH"), run_id=g("CIRCLE_BUILD_NUM"),
                   run_url=g("CIRCLE_BUILD_URL"),
                   oidc=bool(g("CIRCLE_OIDC_TOKEN_V2") or g("CIRCLE_OIDC_TOKEN")))
    else:
        ctx = dict(provider="local", repo="", host="", repo_host="", commit="", branch="", run_id="",
                   run_url="", oidc=False)
    if g("DAWNFIX_REPO"):
        ctx["repo"] = g("DAWNFIX_REPO")
        ctx["project_id"] = ""
    url = g("DAWNFIX_REPO_HOST_URL").rstrip("/")
    if url:
        u = urlsplit(url)
        if u.scheme != "https" or not u.hostname or u.path or u.query or u.username:
            raise ContextError(f"DAWNFIX_REPO_HOST_URL must be https://<host>[:<port>], not '{url}'")
    if g("DAWNFIX_REPO_HOST"):
        if g("DAWNFIX_REPO_HOST") not in REPO_HOSTS:
            raise ContextError("DAWNFIX_REPO_HOST must be github, gitlab or bitbucket")
        ctx["repo_host"] = g("DAWNFIX_REPO_HOST")
        ctx["host_url"] = url or PUBLIC[ctx["repo_host"]]
        ctx["host_source"] = "override" if url else "public"
        ctx["api_url"] = ""
    elif url:
        ctx["host_url"] = url
        ctx["host_source"] = "override"
        ctx["api_url"] = ""
    elif ctx["host"]:
        ctx["host_url"] = f"https://{ctx['host']}"
        ctx["host_source"] = "ci"
    if ctx.get("host_url"):
        u = urlsplit(ctx["host_url"])
        ctx["host"] = u.netloc.lower()
    return CiContext(**ctx)
