"""The GitLab adapter: REST v4, the token in PRIVATE-TOKEN only to the exact API host, no
redirects, draft merge requests only, dedupe by branch and by fingerprint in the issue title or
marker, the daily count, the push URL."""
from datetime import datetime, timezone

import pytest

from dawnfix_core.run.context import detect
from dawnfix_core.run.hosts import Change, GitLabAdapter, HostError, adapter_for
from dawnfix_core.run.web import Http

from .run_fakes import FakeHttp

FP = "1997f26556fdd1c5"
TOKEN = "glpat" + "-" + "T" * 24
P = "/api/v4/projects/4242"
GITLAB_ENV = {"GITLAB_CI": "true", "CI_PROJECT_PATH": "acme/platform/shop-api", "CI_PROJECT_ID": "4242",
              "CI_SERVER_HOST": "gitlab.com", "CI_COMMIT_SHA": "b" * 40, "CI_COMMIT_BRANCH": "main",
              "CI_PIPELINE_ID": "7", "CI_JOB_URL": "https://gitlab.com/acme/platform/shop-api/-/jobs/70"}


def gl(answers, env=GITLAB_ENV):
    http = FakeHttp(answers)
    return adapter_for(detect(env), TOKEN, http), http


def mr(iid, state="opened", branch=f"dawnfix/{FP}", **kw):
    return {"iid": iid, "id": 9000 + iid, "state": state, "source_branch": branch,
            "web_url": f"https://gitlab.com/acme/platform/shop-api/-/merge_requests/{iid}", **kw}


def test_the_project_by_id_on_gitlab_com_and_the_token_in_private_token_only():
    a, http = gl({("GET", P): (200, {"default_branch": "trunk"})})
    assert isinstance(a, GitLabAdapter)
    assert a.default_branch() == "trunk" and a.default_branch() == "trunk"
    assert len(http.calls) == 1
    c = http.calls[0]
    assert c["url"] == "https://gitlab.com/api/v4/projects/4242"
    assert c["headers"]["PRIVATE-TOKEN"] == TOKEN and "Authorization" not in c["headers"]


def test_the_project_by_path_when_there_is_no_project_id():
    a, http = gl({("GET", "/api/v4/projects/acme%2Fplatform%2Fshop-api"): (200, {"default_branch": "main"})},
                 env={"DAWNFIX_REPO_HOST": "gitlab", "DAWNFIX_REPO": "acme/platform/shop-api"})
    assert a.default_branch() == "main"
    assert http.calls[0]["url"] == "https://gitlab.com/api/v4/projects/acme%2Fplatform%2Fshop-api"


def test_a_self_managed_server_only_from_dawnfix_repo_host_url():
    # CI_SERVER_HOST alone never decides where the token goes.
    with pytest.raises(HostError, match="DAWNFIX_REPO_HOST_URL"):
        gl({}, env={**GITLAB_ENV, "CI_SERVER_HOST": "git.acme.io"})
    a, http = gl({("GET", P): (200, {"default_branch": "main"})},
                 env={**GITLAB_ENV, "CI_SERVER_HOST": "evil.example", "DAWNFIX_REPO_HOST": "gitlab",
                      "DAWNFIX_REPO_HOST_URL": "https://git.acme.io"})
    a.default_branch()
    assert http.calls[0]["url"] == "https://git.acme.io/api/v4/projects/4242"
    assert a.push_url(TOKEN) == f"https://oauth2:{TOKEN}@git.acme.io/acme/platform/shop-api.git"


def test_not_a_project_path():
    for bad in ("shop-api", "acme/../x", "acme/sh op"):
        with pytest.raises(HostError, match="not a GitLab project path"):
            gl({}, env={"DAWNFIX_REPO_HOST": "gitlab", "DAWNFIX_REPO": bad})


def test_find_existing_merge_request_any_state_and_open_issue_by_title_or_marker():
    a, http = gl({
        ("GET", f"{P}/merge_requests?"): (200, [mr(3, branch="dawnfix/other"), mr(5, state="merged")]),
        ("GET", f"{P}/issues?"): (200, [
            {"iid": 8, "state": "opened", "title": "dawnfix: other (ffffffffffffffff)", "description": ""},
            {"iid": 12, "state": "opened", "title": "Checkout fails",
             "description": f"x\n<!-- dawnfix:fingerprint={FP} -->", "web_url": "u12"}]),
    })
    e = a.find_existing(FP)
    assert (e.change.number, e.change.state, e.change.kind) == (5, "merged", "change")
    assert (e.issue.number, e.issue.kind, e.issue.url) == (12, "issue", "u12")
    assert f"source_branch=dawnfix%2F{FP}" in http.calls[0]["path"] and "state=all" in http.calls[0]["path"]
    assert "labels=dawnfix" in http.calls[1]["path"] and "state=opened" in http.calls[1]["path"]
    with pytest.raises(ValueError):
        a.find_existing("../../x")


def test_find_existing_nothing_and_closed_states():
    a, _ = gl({("GET", f"{P}/merge_requests?"): (200, [mr(6, state="closed")]), ("GET", f"{P}/issues?"): (200, [])})
    e = a.find_existing(FP)
    assert e.change.state == "closed" and e.issue is None
    a, _ = gl({("GET", f"{P}/merge_requests?"): (200, []), ("GET", f"{P}/issues?"): (200, [])})
    assert a.find_existing(FP) == type(e)()


def test_open_draft_change_is_a_draft_merge_request_with_labels_never_merged():
    a, http = gl({
        ("GET", P + "?"): (200, {}),
        ("POST", f"{P}/labels"): (409, {"message": "exists"}),
        ("POST", f"{P}/merge_requests"): (201, mr(9, draft=True, title="Draft: dawnfix: t")),
        ("GET", P): (200, {"default_branch": "main"}),
    })
    c = a.open_draft_change(f"dawnfix/{FP}", "dawnfix: t", "body")
    assert c == Change("change", 9, "open", "https://gitlab.com/acme/platform/shop-api/-/merge_requests/9")
    post = [x for x in http.calls if x["method"] == "POST" and x["path"].endswith("/merge_requests")][0]
    import json
    d = json.loads(post["body"])
    assert d["title"] == "Draft: dawnfix: t" and d["target_branch"] == "main" and d["source_branch"] == f"dawnfix/{FP}"
    assert d["labels"] == "dawnfix,AI-generated" and d["remove_source_branch"] is False
    assert not {"merge_when_pipeline_succeeds", "auto_merge"} & set(d)
    with pytest.raises(HostError, match="not a dawnfix branch"):
        a.open_draft_change("main", "t", "b")


def test_a_merge_request_that_is_not_a_draft_is_an_error():
    a, _ = gl({("POST", f"{P}/labels"): (201, {}), ("GET", P): (200, {"default_branch": "main"}),
               ("POST", f"{P}/merge_requests"): (201, mr(9, draft=False, title="dawnfix: t"))})
    with pytest.raises(HostError, match="not as a draft"):
        a.open_draft_change(f"dawnfix/{FP}", "dawnfix: t", "b")


def test_issue_comment_and_errors():
    a, http = gl({("POST", f"{P}/labels"): (201, {}),
                  ("POST", f"{P}/issues/4/notes"): (201, {}),
                  ("POST", f"{P}/merge_requests/9/notes"): (201, {}),
                  ("POST", f"{P}/issues"): (201, {"iid": 4, "state": "opened", "web_url": "u4"})})
    assert a.open_issue("t", "b") == Change("issue", 4, "open", "u4")
    import json
    issue = [x for x in http.calls if x["path"] == f"{P}/issues"][0]
    assert json.loads(issue["body"]) == {"title": "t", "description": "b", "labels": "dawnfix,AI-generated"}
    a.comment(Change("issue", 4, "open", ""), "again")
    a.comment(Change("change", 9, "open", ""), "again")
    assert [x["path"] for x in http.calls[-2:]] == [f"{P}/issues/4/notes", f"{P}/merge_requests/9/notes"]
    a, _ = gl({("POST", f"{P}/issues"): (403, {"message": "forbidden"})})
    with pytest.raises(HostError, match="HTTP 403"):
        a.open_issue("t", "b")


def test_changes_opened_today_counts_dawnfix_branches_only():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    a, http = gl({("GET", f"{P}/merge_requests?"): (200, [
        mr(1, created_at=f"{today}T01:00:00.000Z"), mr(2, branch="feature/x", created_at=f"{today}T02:00:00.000Z"),
        mr(3, branch="dawnfix/aaaaaaaaaaaaaaaa", created_at=f"{today}T03:00:00.000Z"),
        mr(4, created_at="2020-01-01T00:00:00.000Z")])})
    assert a.changes_opened_today() == 2
    assert f"created_after={today}T00:00:00Z" in http.calls[0]["path"]


def test_push_url_oauth2():
    a, _ = gl({})
    assert a.push_url(TOKEN) == f"https://oauth2:{TOKEN}@gitlab.com/acme/platform/shop-api.git"


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

    def opener(req, timeout):
        seen.append((req.full_url, dict(req.header_items())))
        return Resp(302)

    a = GitLabAdapter(detect(GITLAB_ENV), TOKEN, Http(opener=opener))
    with pytest.raises(HostError, match="redirect, not followed"):
        a.open_issue("t", "b")
    assert seen and all(u.startswith("https://gitlab.com/api/v4/") for u, _ in seen)
    with pytest.raises(ValueError):
        Http().request("GET", "https://gitlab.com/api/v4/x", headers={"PRIVATE-TOKEN": TOKEN})
    with pytest.raises(HostError, match="refusing to send a token"):
        a._req("GET", "https://evil.example/api/v4/projects/1")


def test_ci_config_path_and_ci_skip():
    a, http = gl({("GET", P): (200, {"default_branch": "main", "ci_config_path": "pipelines/main.yml"})})
    assert a.ci_config_path() == "pipelines/main.yml" and a.default_branch() == "main"
    assert len(http.calls) == 1  # one project read for both
    assert a.push_options == ("ci.skip",)
    a, _ = gl({("GET", P): (200, {"default_branch": "main", "ci_config_path": None})})
    assert a.ci_config_path() == ""
