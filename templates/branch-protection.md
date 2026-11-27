# Branch protection for a Dawnfix repo

Dawnfix opens **draft** PRs on `dawnfix/*` branches and never merges. These settings make
that a property of the repository, not a promise of the agent. Apply them to the default
branch (the one the AWS role and GCP provider trust) with a ruleset
(Settings > Rules > Rulesets) or classic branch protection.

## Default branch

| Setting | Why |
|---|---|
| Require a pull request before merging, at least 1 approval | Nothing written by the fix job reaches the default branch without a human |
| Require review from Code Owners (with `CODEOWNERS.snippet` added) | `.github/`, `.dawnfix.yml`, `.claude/` decide what the agent may read, run and publish; a PR that changes them needs an owner |
| Dismiss stale approvals when new commits are pushed | Dawnfix may push follow-up commits to its PR; an approval must cover the final diff |
| Require approval of the most recent reviewable push | Stops the PR author (the bot identity) approving its own last push |
| Require status checks to pass (your CI) | The failing-test-first contract only means something if CI runs; see "PR author" below |
| Block force pushes, block deletion | The OIDC trust is pinned to this branch name; rewriting it rewrites what is trusted |
| Do not add the Dawnfix PR author (GitHub App or PAT owner) to any bypass list | Bypass would let the bot merge its own PR |

## Why the trust is on the branch

The AWS role trusts `repo:ORG/REPO:ref:refs/heads/<default branch>`; the GCP provider can be
pinned the same way (`setup-wif.sh --branch`). A workflow run can only get cloud read
credentials from a commit already on that branch, which is the reason it must be protected:
whoever can push to it unreviewed can change the workflow and read the logs.

For a stronger boundary, use a GitHub environment (say `dawnfix`) restricted to the default
branch, deploy the AWS stack with `Environment=dawnfix`, and add `environment: dawnfix` to
the `read` job only. The `fix` job must not use that environment.

## `dawnfix/*` branches

- Leave them unprotected so the publish job can push; they are disposable.
- Optional ruleset: restrict creation of `dawnfix/*` to the Dawnfix PR author, so other
  branches cannot impersonate a Dawnfix PR.

## PR author and CI

PRs and pushes made with the workflow's `GITHUB_TOKEN` do not trigger other workflows
(GitHub's guard against recursive runs), so your CI would never run on a Dawnfix PR and
required checks would block it forever. Give the workflow a PR author that is not
`GITHUB_TOKEN`:

- a **GitHub App you own** (preferred): permissions Contents RW, Pull requests RW, Metadata R,
  installed on this repo only; set `vars.DAWNFIX_PR_APP_ID` and
  `secrets.DAWNFIX_PR_APP_PRIVATE_KEY`; or
- a **fine-grained PAT** for this repo only (Contents RW, Pull requests RW) in
  `secrets.DAWNFIX_PR_TOKEN`, owned by a machine user rather than a person.

Neither may have the `workflows` permission: the publish step already refuses diffs under
`.github/`, and without that permission GitHub refuses them too. The token is minted or read
only after the agent has finished; the agent itself only ever holds the job's `GITHUB_TOKEN`.

## Actions settings

- Settings > Actions > General > Workflow permissions: **Read repository contents** (default
  read-only). The dawnfix workflow grants itself per-job permissions.
- "Allow GitHub Actions to create and approve pull requests": leave it **off** when a PR
  author App or PAT is configured. Only the no-author fallback (PRs opened with `GITHUB_TOKEN`,
  CI won't run) needs it on, because `GITHUB_TOKEN` cannot open PRs otherwise. Dawnfix never
  approves anything.
- Fork PR workflows: require approval for outside collaborators. The dawnfix workflow has no
  `pull_request` trigger, but the rest of your CI shares the runner pool and secrets policy.
