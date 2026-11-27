"""Repo host adapters: GitHub, GitLab and Bitbucket Cloud."""
from .base import Change, Existing, HostAdapter, HostError, NotImplementedAdapter
from .github import GitHubAdapter
from .gitlab import GitLabAdapter
from .bitbucket import BitbucketAdapter

ADAPTERS = {"github": GitHubAdapter, "gitlab": GitLabAdapter, "bitbucket": BitbucketAdapter}


def adapter_for(ctx, token="", http=None, *, bitbucket_email: str = "") -> HostAdapter:
    """bitbucket_email: DAWNFIX_BITBUCKET_EMAIL, for an Atlassian API token (Basic auth); without it
    a Bitbucket token is an access token (Bearer)."""
    cls = ADAPTERS.get(ctx.repo_host)
    if cls is None:
        raise HostError(
            f"unknown repo host for '{ctx.repo or '?'}' (CI {ctx.provider}): set DAWNFIX_REPO_HOST to github, "
            "gitlab or bitbucket, and DAWNFIX_REPO to the repo path")
    if cls is BitbucketAdapter:
        return cls(ctx, token, http, user=bitbucket_email)
    return cls(ctx, token, http)


__all__ = ["ADAPTERS", "BitbucketAdapter", "Change", "Existing", "GitHubAdapter", "GitLabAdapter",
           "HostAdapter", "HostError", "NotImplementedAdapter", "adapter_for"]
