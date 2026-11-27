"""CI context detection: GitHub Actions, GitLab CI, Bitbucket Pipelines, CircleCI."""
import pytest

from dawnfix_core.run.context import detect, parse_remote


def test_github_actions():
    c = detect({"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "octo/shop-api", "GITHUB_SHA": "a" * 40,
                "GITHUB_REF_NAME": "main", "GITHUB_RUN_ID": "99", "GITHUB_SERVER_URL": "https://github.com",
                "ACTIONS_ID_TOKEN_REQUEST_URL": "https://x", "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "t"})
    assert (c.provider, c.repo, c.host, c.repo_host, c.commit, c.branch, c.run_id) == (
        "github-actions", "octo/shop-api", "github.com", "github", "a" * 40, "main", "99")
    assert c.run_url == "https://github.com/octo/shop-api/actions/runs/99"
    assert c.oidc is True


def test_gitlab_ci_with_subgroups_and_a_self_hosted_server():
    c = detect({"GITLAB_CI": "true", "CI_PROJECT_PATH": "acme/platform/shop-api", "CI_SERVER_HOST": "git.acme.io",
                "CI_COMMIT_SHA": "b" * 40, "CI_COMMIT_BRANCH": "main", "CI_PIPELINE_ID": "7",
                "CI_JOB_URL": "https://git.acme.io/acme/platform/shop-api/-/jobs/70", "CI_JOB_TOKEN": "x"})
    assert (c.provider, c.repo, c.host, c.repo_host, c.branch, c.run_id) == (
        "gitlab-ci", "acme/platform/shop-api", "git.acme.io", "gitlab", "main", "7")
    assert c.run_url.endswith("/-/jobs/70") and c.oidc is False
    assert detect({"GITLAB_CI": "true", "DAWNFIX_OIDC_TOKEN_VAR": "AWS_ID", "AWS_ID": "jwt"}).oidc is True


def test_bitbucket_pipelines():
    c = detect({"BITBUCKET_BUILD_NUMBER": "42", "BITBUCKET_REPO_FULL_NAME": "acme/shop-api",
                "BITBUCKET_COMMIT": "c" * 40, "BITBUCKET_BRANCH": "main", "BITBUCKET_STEP_OIDC_TOKEN": "jwt"})
    assert (c.provider, c.repo, c.host, c.repo_host, c.run_id) == (
        "bitbucket-pipelines", "acme/shop-api", "bitbucket.org", "bitbucket", "42")
    assert c.run_url == "https://bitbucket.org/acme/shop-api/pipelines/results/42" and c.oidc is True


@pytest.mark.parametrize("remote, host, repo_host", [
    ("git@github.com:octo/shop-api.git", "github.com", "github"),
    ("https://github.com/octo/shop-api", "github.com", "github"),
    ("git@bitbucket.org:octo/shop-api.git", "bitbucket.org", "bitbucket"),
    ("https://gitlab.com/octo/shop-api.git", "gitlab.com", "gitlab"),
])
def test_circleci_reads_the_repo_host_from_its_remote(remote, host, repo_host):
    c = detect({"CIRCLECI": "true", "CIRCLE_REPOSITORY_URL": remote, "CIRCLE_SHA1": "d" * 40,
                "CIRCLE_BRANCH": "main", "CIRCLE_BUILD_NUM": "5", "CIRCLE_BUILD_URL": "https://circleci.com/gh/octo/shop-api/5",
                "CIRCLE_PROJECT_USERNAME": "octo", "CIRCLE_PROJECT_REPONAME": "shop-api"})
    assert (c.provider, c.repo, c.host, c.repo_host, c.run_url) == (
        "circleci", "octo/shop-api", host, repo_host, "https://circleci.com/gh/octo/shop-api/5")
    assert c.oidc is False
    assert detect({"CIRCLECI": "true", "CIRCLE_OIDC_TOKEN_V2": "jwt"}).oidc is True


def test_local_and_overrides():
    c = detect({})
    assert c.provider == "local" and c.repo_host == "" and c.oidc is False
    c = detect({"CIRCLECI": "true", "DAWNFIX_REPO": "octo/api", "DAWNFIX_REPO_HOST": "github"})
    assert (c.repo, c.repo_host, c.host) == ("octo/api", "github", "github.com")


def test_parse_remote():
    assert parse_remote("ssh://git@github.com:22/a/b.git") == ("github.com", "a/b")
    assert parse_remote("not a url") == ("", "")
