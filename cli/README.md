# dawnfix (npm)

Set up [Dawnfix](https://dawnfix.dev), the AI SRE that runs in your own GitHub Actions, GitLab CI
or Bitbucket Pipelines, in a repo; check the setup; and run Dawnfix Flare. One bundled file, no
dependencies, Node 20 or newer. Source available under FSL-1.1-ALv2 (the `LICENSE` in this package).

```sh
npx dawnfix init           # shows .dawnfix.yml and a 15-line workflow, writes them when you say yes
npx dawnfix init --dry-run # only shows them, and the next steps
npx dawnfix init --host gitlab  # GitLab: .dawnfix.yml and a .gitlab-ci.yml include (default when origin is GitLab)
npx dawnfix init --host bitbucket  # Bitbucket: .dawnfix.yml and bitbucket-pipelines.yml (default when origin is bitbucket.org)
npx dawnfix doctor         # config, pinned workflow, secret and variable names, Free or Enterprise
npx dawnfix flare --help   # read-only Cloudflare audit
```

`init` never asks for a secret and never writes one. It prints the commands you run: the
read-only cloud role (AWS CloudFormation or GCP Workload Identity Federation) and
`gh secret set DAWNFIX_AI_API_KEY` (your AI API key, Claude today).

The workflow it writes calls the reusable workflow
`dawnfix/dawnfix/.github/workflows/dawnfix.yml@v0`. The Python tools (`dawnfix`, `logbill`,
`parity`, `sweeper`, `leastpriv`, `receipt`, `fleet`) are the PyPI package `dawnfix` of the
same version.

On GitLab, `.gitlab-ci.yml` includes `templates/gitlab/dawnfix.gitlab-ci.yml` of the
release, pinned with its `integrity:` (sha256) hash. An existing `.gitlab-ci.yml` is never
changed: `init` writes `.dawnfix.yml` and prints the include lines to paste. The next steps
are `glab variable set` lines (each secret masked, protected and scoped to one environment)
and `glab schedule create`.

On Bitbucket, `bitbucket-pipelines.yml` is `templates/bitbucket/bitbucket-pipelines.yml` of the
release (Bitbucket has no remote include): a custom pipeline `dawnfix` for a schedule, four
steps, each a fresh container with one secret at most. An existing `bitbucket-pipelines.yml` is
never changed: `init` writes `.dawnfix.yml` and prints the part to merge. The next steps name
the deployment environments (`dawnfix-agent`, `dawnfix-publish`, `dawnfix-report`), the secured
deployment variable for each, and the schedule.

Docs and source: https://github.com/dawnfix/dawnfix

## Development (in the repo, `cli/`)

```sh
npm ci
npm run build         # writes dist/cli.js from src/, ../flare/src/ and ../templates/; commit it
npm run build:check   # exit 1 if dist/cli.js is stale
npm test              # node --test: init, doctor, flare, the bundle, npm pack + install
```
