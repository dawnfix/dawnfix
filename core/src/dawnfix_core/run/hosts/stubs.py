"""Bitbucket: coming soon (not in 0.4.0; `dawnfix run` refuses it before any stage). The interface is the one GitHub and GitLab implement (base.HostAdapter);
docs/platforms.md (private repo) lists what it must do."""
from .base import NotImplementedAdapter


class BitbucketAdapter(NotImplementedAdapter):
    """Coming soon: pull requests (draft), issues (when the tracker is on), access token push URL."""
    name = "Bitbucket"
