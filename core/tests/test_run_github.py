"""The GitHub adapter: dedupe like the workflow (dawnfix/<fp> PR in any state, open dawnfix
issue with the fingerprint in its title), draft PRs only, labels, the daily count, the push URL.
GitLab and Bitbucket have their own tests (test_run_gitlab.py, test_run_bitbucket.py)."""
from datetime import datetime, timezone

import pytest

from dawnfix_core.run.context import detect
from dawnfix_core.run.hosts import (BitbucketAdapter, GitHubAdapter, GitLabAdapter, HostAdapter, HostError,
                                    NotImplementedAdapter, adapter_for)
from urllib.parse import urlsplit

from dawnfix_core.run.web import Http, TokenRefused

from .run_fakes import HOST_TOKEN, FakeHttp

FP = "1997f26556fdd1c5"
CTX = detect({"CIRCLECI": "true", "CIRCLE_REPOSITORY_URL": "git@github.com:octo/shop-api.git",
              "CIRCLE_BUILD_URL": "https://circleci.com/gh/octo/shop-api/5"})


def gh(answers):
    http = FakeHttp(answers)
    return GitHubAdapter(CTX, HOST_TOKEN, http), http


def test_find_existing_open_pr_and_open_issue():
    a, http = gh({
        ("GET", "/repos/octo/shop-api/pulls?"): (200, [{"number": 5, "state": "open", "merged_at": None,
                                                         "html_url": "https://github.com/octo/shop-api/pull/5",
                                                         "head": {"ref": f"dawnfix/{FP}"}}]),
        ("GET", "/repos/octo/shop-api/issues?"): (200, [
            {"number": 3, "state": "open", "title": f"dawnfix: x ({FP})", "pull_request": {}},
            {"number": 8, "state": "open", "title": "dawnfix: other (ffffffffffffffff)"},
            {"number": 12, "state": "open", "title": f"dawnfix: Alarm ({FP})", "html_url": "u12"}]),
    })
    e = a.find_existing(FP)
    assert (e.change.number, e.change.state, e.change.kind) == (5, "open", "change")
    assert (e.issue.number, e.issue.kind) == (12, "issue")
    assert http.calls[0]["path"] == f"/repos/octo/shop-api/pulls?state=all&per_page=10&head=octo:dawnfix/{FP}"
    assert "labels=dawnfix" in http.calls[1]["path"] and "state=open" in http.calls[1]["path"]
    for c in http.calls:
        assert c["headers"]["Authorization"] == f"Bearer {HOST_TOKEN}"
        assert c["url"].startswith("https://api.github.com/")


def test_find_existing_merged_and_nothing():
    a, _ = gh({("GET", "/repos/octo/shop-api/pulls?"): (200, [{"number": 6, "state": "closed", "merged_at": "2026-11-01",
                                                               "head": {"ref": f"dawnfix/{FP}"}}]),
               ("GET", "/repos/octo/shop-api/issues?"): (200, [])})
    e = a.find_existing(FP)
    assert e.change.state == "merged" and e.issue is None
    a, _ = gh({("GET", "/repos/octo/shop-api/pulls?"): (200, [{"number": 1, "state": "open", "head": {"ref": "dawnfix/other"}}]),
               ("GET", "/repos/octo/shop-api/issues?"): (200, [])})
    assert a.find_existing(FP).change is None
    with pytest.raises(ValueError):
        a.find_existing("not-a-fingerprint")


def test_open_draft_change_is_a_draft_against_the_default_branch_with_labels():
    a, http = gh({("GET", "/repos/octo/shop-api"): (200, {"default_branch": "trunk"}),
                  ("POST", "/repos/octo/shop-api/labels"): (422, {}),
                  ("POST", "/repos/octo/shop-api/pulls"): (201, {"number": 41, "state": "open",
                                                                   "html_url": "https://github.com/octo/shop-api/pull/41"}),
                  ("POST", "/repos/octo/shop-api/issues/41/labels"): (200, [])})
    c = a.open_draft_change(f"dawnfix/{FP}", "dawnfix: TypeError", "body")
    assert c.url.endswith("/pull/41") and c.state == "open"
    (create,) = [i for i, x in enumerate(http.calls) if x["method"] == "POST" and x["path"] == "/repos/octo/shop-api/pulls"]
    assert http.json(create) == {"title": "dawnfix: TypeError", "head": f"dawnfix/{FP}", "base": "trunk",
                                 "body": "body", "draft": True}
    assert http.json(len(http.calls) - 1) == {"labels": ["dawnfix", "AI-generated"]}
    assert not any("merge" in x["path"] for x in http.calls)


def test_open_issue_comment_count_and_push_url():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    a, http = gh({("POST", "/repos/octo/shop-api/labels"): (201, {}),
                  ("POST", "/repos/octo/shop-api/issues/12/comments"): (201, {}),
                  ("POST", "/repos/octo/shop-api/issues"): (201, {"number": 9, "html_url": "u9"}),
                  ("GET", "/repos/octo/shop-api/pulls?"): (200, [
                      {"head": {"ref": f"dawnfix/{FP}"}, "created_at": f"{today}T01:00:00Z"},
                      {"head": {"ref": "dawnfix/ffffffffffffffff"}, "created_at": "2020-01-01T00:00:00Z"},
                      {"head": {"ref": "feature/x"}, "created_at": f"{today}T02:00:00Z"}])})
    i = a.open_issue("dawnfix: x (fp)", "b")
    assert i.number == 9
    assert http.json(len(http.calls) - 1) == {"title": "dawnfix: x (fp)", "body": "b", "labels": ["dawnfix", "AI-generated"]}
    a.comment(i.__class__("issue", 12, "open", ""), "again")
    assert a.changes_opened_today() == 1
    assert a.push_url("TOKEN") == "https://x-access-token:TOKEN@github.com/octo/shop-api.git"
    assert a.ci_context() is CTX


def test_errors_never_carry_the_token():
    a, _ = gh({})
    with pytest.raises(HostError) as e:
        a.open_issue("t", "b")
    assert HOST_TOKEN not in str(e.value) and "HTTP 404" in str(e.value)


def test_github_enterprise_api_url_comes_from_the_configured_url_only():
    ctx = detect({"DAWNFIX_REPO": "o/r", "DAWNFIX_REPO_HOST": "github", "DAWNFIX_REPO_HOST_URL": "https://git.acme.io"})
    a = GitHubAdapter(ctx, "t", FakeHttp())
    assert a.api == "https://git.acme.io/api/v3" and a.allowed == ("git.acme.io",)
    assert a.push_url("T") == "https://x-access-token:T@git.acme.io/o/r.git"
    gha = detect({"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "o/r", "GITHUB_SERVER_URL": "https://ghe.corp",
                  "GITHUB_API_URL": "https://ghe.corp/api/v3"})
    assert GitHubAdapter(gha, "t", FakeHttp()).allowed == ("ghe.corp",)


def test_repo_host_override_never_uses_a_host_named_by_ci_variables():
    """A CI remote pointing at another server must not receive the token once DAWNFIX_REPO_HOST says github."""
    ctx = detect({"CIRCLECI": "true", "CIRCLE_REPOSITORY_URL": "https://evil.example/octo/shop-api.git",
                  "DAWNFIX_REPO_HOST": "github"})
    assert (ctx.host, ctx.host_url) == ("github.com", "https://github.com")
    a = GitHubAdapter(ctx, HOST_TOKEN, FakeHttp())
    assert a.api == "https://api.github.com" and a.push_url("T").startswith("https://x-access-token:T@github.com/")
    for bad in ("http://git.acme.io", "https://git.acme.io/path", "https://u:p@git.acme.io"):
        with pytest.raises(Exception, match="DAWNFIX_REPO_HOST_URL"):
            detect({"DAWNFIX_REPO_HOST": "github", "DAWNFIX_REPO_HOST_URL": bad})
    with pytest.raises(Exception, match="github, gitlab or bitbucket"):
        detect({"DAWNFIX_REPO_HOST": "gitea"})


def test_a_token_is_refused_for_any_other_host():
    http = FakeHttp()
    with pytest.raises(TokenRefused):
        http.request("GET", "https://evil.example/x", token=HOST_TOKEN, allowed_hosts=("api.github.com",))
    with pytest.raises(TokenRefused):  # a look-alike host, another port
        http.request("GET", "https://api.github.com.evil.example/x", token=HOST_TOKEN, allowed_hosts=("api.github.com",))
    with pytest.raises(TokenRefused):
        http.request("GET", "https://api.github.com:8443/x", token=HOST_TOKEN, allowed_hosts=("api.github.com",))
    with pytest.raises(ValueError):  # no way around the check through headers
        http.request("GET", "https://evil.example/x", headers={"Authorization": f"Bearer {HOST_TOKEN}"})
    assert http.calls == []
    # The adapter's own calls: its API host, nothing else, even when the repo path is odd.
    a, http = gh({})
    a.api = "https://evil.example"
    with pytest.raises(HostError, match="refusing to send a token"):
        a.open_issue("t", "b")
    assert http.calls == []


def test_a_github_token_never_leaves_api_github_com():
    a, http = gh({("GET", "/repos/octo/shop-api/pulls?"): (200, []), ("GET", "/repos/octo/shop-api/issues?"): (200, []),
                  ("GET", "/repos/octo/shop-api"): (200, {"default_branch": "main"})})
    a.default_branch()
    a.find_existing(FP)
    try:
        a.open_issue("t", "b")
    except HostError:
        pass
    assert http.calls and {urlsplit(c["url"]).netloc for c in http.calls} == {"api.github.com"}


def test_a_redirect_to_another_host_is_refused_and_not_followed():
    seen = []

    def opener(req, timeout):
        import urllib.error
        seen.append((req.full_url, req.get_header("Authorization")))
        raise urllib.error.HTTPError(req.full_url, 302, "Found", {"Location": "https://evil.example/steal"}, None)

    r = Http(opener=opener).request("GET", "https://api.github.com/x", token="t", allowed_hosts=("api.github.com",))
    assert r.status == 302 and seen == [("https://api.github.com/x", "Bearer t")]
    a = GitHubAdapter(CTX, HOST_TOKEN, Http(opener=opener))
    seen.clear()
    with pytest.raises(HostError, match="redirect, not followed"):
        a.open_issue("t", "b")
    assert all(u.startswith("https://api.github.com/") for u, _ in seen)
    with pytest.raises(ValueError):
        Http().request("GET", "http://example.com")


def test_a_not_implemented_host_says_so_on_every_call():
    class Later(NotImplementedAdapter):
        name = "Later"
    a = Later(detect({"DAWNFIX_REPO": "o/r", "DAWNFIX_REPO_HOST": "github"}), "t", FakeHttp())
    assert isinstance(a, HostAdapter)
    for call in (lambda: a.default_branch(), lambda: a.find_existing(FP), lambda: a.open_draft_change("b", "t", "x"),
                 lambda: a.open_issue("t", "b", ("dawnfix",)), lambda: a.push_url("t"), lambda: a.changes_opened_today()):
        with pytest.raises(HostError, match="phase 2"):
            call()


@pytest.mark.parametrize("cls, host", [(GitLabAdapter, "gitlab"), (BitbucketAdapter, "bitbucket")])
def test_gitlab_and_bitbucket_are_implemented(cls, host):
    a = adapter_for(detect({"DAWNFIX_REPO": "o/r", "DAWNFIX_REPO_HOST": host}), "t", FakeHttp())
    assert isinstance(a, cls) and not isinstance(a, NotImplementedAdapter)


def test_unknown_host():
    with pytest.raises(HostError, match="DAWNFIX_REPO_HOST"):
        adapter_for(detect({"CIRCLECI": "true", "CIRCLE_REPOSITORY_URL": "https://git.example.org/o/r"}))
