"""Repo host adapters: GitHub and GitLab; Bitbucket is coming soon (NotImplementedAdapter)."""
from .base import Change, Existing, HostAdapter, HostError, NotImplementedAdapter
from .github import GitHubAdapter
from .gitlab import GitLabAdapter
from .stubs import BitbucketAdapter

ADAPTERS = {"github": GitHubAdapter, "gitlab": GitLabAdapter, "bitbucket": BitbucketAdapter}


def adapter_for(ctx, token="", http=None) -> HostAdapter:
    cls = ADAPTERS.get(ctx.repo_host)
    if cls is None:
        raise HostError(
            f"unknown repo host for '{ctx.repo or '?'}' (CI {ctx.provider}): set DAWNFIX_REPO_HOST to github, "
            "gitlab or bitbucket, and DAWNFIX_REPO to the repo path")
    return cls(ctx, token, http)


__all__ = ["ADAPTERS", "BitbucketAdapter", "Change", "Existing", "GitHubAdapter", "GitLabAdapter",
           "HostAdapter", "HostError", "NotImplementedAdapter", "adapter_for"]
