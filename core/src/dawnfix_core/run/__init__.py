"""dawnfix run: the CI-agnostic engine. The same jobs as the GitHub Actions reusable workflow,
as four commands, each meant for its own CI job holding only the secret it needs:

  dawnfix run read      cloud credentials (OIDC) only: the read-only tick, findings artifact
  dawnfix run agent     the AI API key only: Claude Code headless, a patch or report artifact
  dawnfix run publish   the host token only: a fresh checkout, the patch validated and
                        committed, pushed to an explicit URL, a draft PR/MR or an issue
  dawnfix run report    the Enterprise key only: the optional hosted summary and PR state

The repo host (GitHub and GitLab; Bitbucket is coming soon) is reached through a
HostAdapter (hosts/). The GitHub Actions reusable workflow stays the way to run Dawnfix on
GitHub Actions; this engine is for other CI systems.
"""
