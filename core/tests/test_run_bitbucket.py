"""The Bitbucket Cloud adapter: REST 2.0, a Bearer access token or Basic email:API token only to
api.bitbucket.org, no redirects, draft pull requests only, dedupe by branch and by the
fingerprint marker, issues only with the tracker on (else the log), the daily count, the push
URL with the right git user, [skip ci] on the commits."""
import base64
import json
from datetime import datetime, timezone
from urllib.parse import unquote

import pytest

from dawnfix_core.run.context import detect
from dawnfix_core.run.hosts import BitbucketAdapter, Change, HostError, adapter_for
from dawnfix_core.run.scrub import REDACT
from dawnfix_core.run.web import Http

from .run_fakes import FakeHttp

FP = "1997f26556fdd1c5"
TOKEN = "AT" + "CTT3x" + "T" * 40
API_TOKEN = "AT" + "ATT3x" + "A" * 40
EMAIL = "dev@example.com"
R = "/2.0/repositories/acme/shop-api"
BB_ENV = {"BITBUCKET_BUILD_NUMBER": "41", "BITBUCKET_REPO_FULL_NAME": "acme/shop-api", "BITBUCKET_COMMIT": "b" * 40,
          "BITBUCKET_BRANCH": "main", "BITBUCKET_WORKSPACE": "acme", "BITBUCKET_REPO_SLUG": "shop-api"}
REPO = {"mainbranch": {"name": "trunk"}, "has_issues": False}


def bb(answers, env=BB_ENV, token=TOKEN, email=""):
    http = FakeHttp(answers)
    return adapter_for(detect(env), token, http, bitbucket_email=email), http


def pr(i, state="OPEN", branch=f"dawnfix/{FP}", **kw):
    return {"id": i, "state": state, "source": {"branch": {"name": branch}},
            "links": {"html": {"href": f"https://bitbucket.org/acme/shop-api/pull-requests/{i}"}}, **kw}


def q(call):
    return unquote(call["path"].split("q=", 1)[1]) if "q=" in call["path"] else ""


def test_bearer_access_token_only_to_the_api_host():
    a, http = bb({("GET", R): (200, REPO)})
    assert isinstance(a, BitbucketAdapter)
    assert a.default_branch() == "trunk" and a.default_branch() == "trunk"
    assert len(http.calls) == 1
    c = http.calls[0]
    assert c["url"] == "https://api.bitbucket.org/2.0/repositories/acme/shop-api"
    assert c["headers"]["Authorization"] == f"Bearer {TOKEN}"
    assert a.push_url(TOKEN) == f"https://x-token-auth:{TOKEN}@bitbucket.org/acme/shop-api.git"


def test_basic_email_and_api_token():
    a, http = bb({("GET", R): (200, REPO)}, token=API_TOKEN, email=EMAIL)
    a.default_branch()
    basic = base64.b64encode(f"{EMAIL}:{API_TOKEN}".encode()).decode()
    assert http.calls[0]["headers"]["Authorization"] == f"Basic {basic}"
    assert a.push_url(API_TOKEN) == f"https://x-bitbucket-api-token-auth:{API_TOKEN}@bitbucket.org/acme/shop-api.git"
    assert basic in a.auth_values and API_TOKEN in a.auth_values
    assert REDACT(f"x {basic} y") == "x *** y"
    with pytest.raises(HostError, match="DAWNFIX_BITBUCKET_EMAIL"):
        bb({}, token=API_TOKEN, email="not an email")


def test_context_from_pipelines_and_refusals():
    ctx = detect({**BB_ENV, "BITBUCKET_STEP_OIDC_TOKEN": "jwt"})
    assert (ctx.provider, ctx.repo, ctx.repo_host, ctx.host_url, ctx.oidc) == (
        "bitbucket-pipelines", "acme/shop-api", "bitbucket", "https://bitbucket.org", True)
    assert ctx.run_url == "https://bitbucket.org/acme/shop-api/pipelines/results/41"
    for bad in ("shop-api", "acme/../x", "acme/sh op", "a/b/c"):
        with pytest.raises(HostError, match="not a Bitbucket repository path"):
            bb({}, env={"DAWNFIX_REPO_HOST": "bitbucket", "DAWNFIX_REPO": bad})
    with pytest.raises(HostError, match="Data Center"):
        bb({}, env={"DAWNFIX_REPO_HOST": "bitbucket", "DAWNFIX_REPO": "a/b", "DAWNFIX_REPO_HOST_URL": "https://git.acme.io"})


def test_find_existing_pull_request_by_branch_or_marker_any_state():
    a, http = bb({
        ("GET", f"{R}/pullrequests?"): (200, {"values": [
            pr(3, branch="feature/x", description="unrelated"),
            pr(5, state="DECLINED", branch="feature/y", description=f"x\nDawnfix fingerprint: `dawnfix:fingerprint={FP}`")]}),
        ("GET", R): (200, REPO),
    })
    e = a.find_existing(FP)
    assert (e.change.number, e.change.state, e.change.kind) == (5, "closed", "change")
    assert e.issue is None  # the tracker is off: no issue call at all
    query = q(http.calls[0])
    assert f'source.branch.name = "dawnfix/{FP}"' in query and f'description ~ "dawnfix:fingerprint={FP}"' in query
    assert 'state = "MERGED"' in query and 'state = "DECLINED"' in query
    assert not [c for c in http.calls if "/issues" in c["path"]]
    with pytest.raises(ValueError):
        a.find_existing("../../x")


def test_find_existing_open_issue_when_the_tracker_is_on():
    a, http = bb({
        ("GET", f"{R}/pullrequests?"): (200, {"values": [pr(6, state="MERGED")]}),
        ("GET", f"{R}/issues?"): (200, {"values": [
            {"id": 8, "state": "new", "title": "other (ffffffffffffffff)", "content": {"raw": ""}},
            {"id": 12, "state": "open", "title": "Checkout fails", "content": {"raw": f"dawnfix:fingerprint={FP}"},
             "links": {"html": {"href": "u12"}}}]}),
        ("GET", R): (200, {**REPO, "has_issues": True}),
    })
    e = a.find_existing(FP)
    assert e.change.state == "merged"
    assert (e.issue.number, e.issue.kind, e.issue.url) == (12, "issue", "u12")


def test_open_draft_change_is_a_draft_pull_request_never_merged():
    a, http = bb({
        ("POST", f"{R}/pullrequests"): (201, pr(9, draft=True)),
        ("GET", R): (200, REPO),
    })
    body = f"## Cause\nx\n<!-- dawnfix:fingerprint={FP} -->\n"
    c = a.open_draft_change(f"dawnfix/{FP}", "dawnfix: t", body)
    assert c == Change("change", 9, "open", "https://bitbucket.org/acme/shop-api/pull-requests/9")
    post = [x for x in http.calls if x["method"] == "POST"][0]
    d = json.loads(post["body"])
    assert d["draft"] is True and d["close_source_branch"] is False and d["title"] == "dawnfix: t"
    assert d["source"] == {"branch": {"name": f"dawnfix/{FP}"}} and d["destination"] == {"branch": {"name": "trunk"}}
    assert "<!--" not in d["description"] and f"`dawnfix:fingerprint={FP}`" in d["description"]
    assert not {"merge", "auto_merge", "merge_strategy"} & set(d)
    with pytest.raises(HostError, match="not a dawnfix branch"):
        a.open_draft_change("main", "t", "b")


def test_a_pull_request_that_is_not_a_draft_is_an_error():
    a, _ = bb({("GET", R): (200, REPO), ("POST", f"{R}/pullrequests"): (201, pr(9, draft=False))})
    with pytest.raises(HostError, match="not as a draft"):
        a.open_draft_change(f"dawnfix/{FP}", "dawnfix: t", "b")


def test_issue_with_the_tracker_on_and_comments():
    a, http = bb({("GET", R): (200, {**REPO, "has_issues": True}),
                  ("POST", f"{R}/issues/4/comments"): (201, {}),
                  ("POST", f"{R}/pullrequests/9/comments"): (201, {}),
                  ("POST", f"{R}/issues"): (201, {"id": 4, "state": "new", "links": {"html": {"href": "u4"}}})})
    assert a.open_issue("t", "b") == Change("issue", 4, "open", "u4")
    issue = json.loads([x for x in http.calls if x["path"] == f"{R}/issues"][0]["body"])
    assert issue["title"] == "t" and issue["content"]["raw"].startswith("b") and "dawnfix, AI-generated" in issue["content"]["raw"]
    a.comment(Change("issue", 4, "open", ""), "again")
    a.comment(Change("change", 9, "open", ""), "again")
    assert [x["path"] for x in http.calls[-2:]] == [f"{R}/issues/4/comments", f"{R}/pullrequests/9/comments"]
    assert json.loads(http.calls[-1]["body"]) == {"content": {"raw": "again"}}


def test_with_the_tracker_off_the_issue_goes_to_the_log(capsys):
    a, http = bb({("GET", R): (200, REPO)})
    c = a.open_issue("dawnfix: crash (1997f26556fdd1c5)", f"## Cause\nline two\n<!-- dawnfix:fingerprint={FP} -->")
    assert c.kind == "log" and c.url == "https://bitbucket.org/acme/shop-api/pipelines/results/41"
    assert not [x for x in http.calls if x["method"] == "POST"]
    err = capsys.readouterr().err
    assert "issue tracker is off" in err and "  | dawnfix: crash" in err and "  | line two" in err
    with pytest.raises(HostError, match="cannot comment"):
        a.comment(c, "x")


def test_changes_opened_today_counts_dawnfix_branches_only():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    a, http = bb({("GET", f"{R}/pullrequests?"): (200, {"values": [
        pr(1, created_on=f"{today}T01:00:00.000000+00:00"), pr(2, branch="feature/x", created_on=f"{today}T02:00:00+00:00"),
        pr(3, branch="dawnfix/aaaaaaaaaaaaaaaa", state="DECLINED", created_on=f"{today}T03:00:00+00:00"),
        pr(4, created_on="2020-01-01T00:00:00+00:00")]})})
    assert a.changes_opened_today() == 2
    assert f"created_on >= {today}T00:00:00+00:00" in q(http.calls[0])
    assert "%2B00%3A00" in http.calls[0]["path"]  # the + of the offset is encoded


def test_errors_and_pages():
    a, _ = bb({("GET", f"{R}/pullrequests?"): (200, [{"not": "a page"}])})
    with pytest.raises(HostError, match="not a page"):
        a.find_existing(FP)
    a, _ = bb({("GET", R): (200, {"mainbranch": None})})
    with pytest.raises(HostError, match="no main branch"):
        a.default_branch()
    a, _ = bb({("GET", R): (403, {"error": {}})})
    with pytest.raises(HostError, match="HTTP 403"):
        a.default_branch()


def test_no_redirect_is_followed_and_no_token_leaves_the_api_host():
    seen = []

    class Resp:
        def __init__(self, status):
            self.status = status

        def read(self):
            return b"{}"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    import urllib.error

    def opener(req, timeout=None):
        seen.append((req.full_url, req.get_header("Authorization")))
        raise urllib.error.HTTPError(req.full_url, 302, "Found", {"Location": "https://evil.example/x"}, None)

    a = BitbucketAdapter(detect(BB_ENV), TOKEN, Http(opener=opener))
    with pytest.raises(HostError, match="redirect, not followed"):
        a.default_branch()
    assert len(seen) == 1 and seen[0][0].startswith("https://api.bitbucket.org/2.0/")


def test_commit_note_is_skip_ci():
    a, _ = bb({})
    assert a.commit_note == "[skip ci]" and a.push_options == ()
