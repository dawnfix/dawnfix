# Dawnfix

An AI SRE (AI Site Reliability Engineer) for AWS and GCP that runs in your own GitHub
Actions. A deterministic, read-only job reads CloudWatch Logs, alarms, load balancer 5xx or
Cloud Logging every hour, fingerprints and redacts the errors, and remembers which ones it
has seen. When one is new, an agent with your own Anthropic key either files a GitHub issue
with the cause, the impact and a severity, or writes a failing test and the fix and opens a
draft PR for you to review. It never merges or deploys. Your logs never leave your accounts.

Free and source available. No key and no plan is needed for anything in this repo.

## Quick start

In the repo whose production Dawnfix should watch (Node 20+, and `gh` signed in):

```sh
npx dawnfix init
```

It asks where your logs are (AWS or GCP) and how far the agent may go (`autonomy`, start
with `diagnose`), shows the two files it will write, and writes them when you say yes:

- `.dawnfix.yml`: the log sources, `autonomy`, `test.command` (every key:
  [templates/dawnfix.yml](templates/dawnfix.yml));
- `.github/workflows/dawnfix.yml`: about 15 lines that call the reusable workflow, with your
  schedule and permissions:

```yaml
name: dawnfix
on:
  schedule: [{ cron: "17 * * * *" }] # the `schedule` of .dawnfix.yml
  workflow_dispatch: { inputs: { baseline: { type: boolean }, dry_run: { type: boolean } } }
permissions: { contents: write, pull-requests: write, issues: write, id-token: write }
jobs:
  dawnfix:
    uses: dawnfix/dawnfix/.github/workflows/dawnfix.yml@v0
    with:
      aws-role-arn: ${{ vars.DAWNFIX_AWS_ROLE_ARN }}
    secrets:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      DAWNFIX_ENTERPRISE_KEY: ${{ secrets.DAWNFIX_ENTERPRISE_KEY }} # optional
```

It never asks for a secret and never writes one. It prints what you run next:

1. **Read-only cloud role.** AWS: `infra/aws/dawnfix-read-role.yaml` with CloudFormation
   (it trusts GitHub OIDC for your repo's default branch only; check it with
   `infra/aws/verify_readonly.py`). GCP: `infra/gcp/setup-wif.sh` (Workload Identity
   Federation, `roles/logging.viewer` only).
2. **Secrets**, typed by you: `gh secret set ANTHROPIC_API_KEY`.
3. **Review and run.** Open a PR with the two files and merge it. Then
   `gh workflow run dawnfix.yml -f dry_run=true` shows exactly what would leave your account,
   and `gh workflow run dawnfix.yml -f baseline=true` records the errors you already have, so
   only new ones are reported.
4. `npx dawnfix doctor` checks the config, the pinned workflow, the secret and variable
   names, and says whether you run Free or Enterprise.

Later, switch `autonomy` to `plan` or `draft-pr` through a PR (and give `install-command`).
For draft PRs that trigger your CI, set a GitHub App (`pr-app-id`,
`DAWNFIX_PR_APP_PRIVATE_KEY`) or a fine-grained token (`DAWNFIX_PR_TOKEN`) as the PR author.

### The workflows

| Reusable workflow (`uses: dawnfix/dawnfix/.github/workflows/<file>@v0`) | Copy-it-yourself template |
|---|---|
| [dawnfix.yml](.github/workflows/dawnfix.yml): the read job and the diagnose or fix agent | [templates/github/workflows/dawnfix.yml](templates/github/workflows/dawnfix.yml) |
| [parity.yml](.github/workflows/parity.yml): config drift between two AWS environments | [dawnfix-parity.yml](templates/github/workflows/dawnfix-parity.yml) |
| [flare.yml](.github/workflows/flare.yml): the daily Cloudflare audit | [dawnfix-flare.yml](templates/github/workflows/dawnfix-flare.yml) |
| [receipt.yml](.github/workflows/receipt.yml): a cost comment on every production deploy | [dawnfix-receipt.yml](templates/github/workflows/dawnfix-receipt.yml) |

Each reusable workflow's header shows its caller and lists its inputs and secrets. The
permissions in your caller are a ceiling: every job asks for less (only the read job gets
`id-token`, only the publish job can push, on a fresh runner after the agent's job has
ended, and it only opens draft PRs). `@v0` follows the
latest 0.x release; pin `@v0.3.0` or a commit SHA to freeze it. Each release installs the
same version of the PyPI package `dawnfix` and loads the agent's instructions from
`prompts/ci/` at its own tag. Fallback, without PyPI: the `core-ref` input (a tag or commit
SHA of this repo) installs from git at that ref and loads the instructions from it.

The templates are the same jobs and steps, reading repository variables
(`DAWNFIX_AWS_ROLE_ARN`, `DAWNFIX_INSTALL_COMMAND`, ...) instead of inputs, for those who
would rather keep the whole file in their repo. Copy one, copy the `schedule` of
`.dawnfix.yml` into its cron, and set the variables its header lists.

### The CLIs

```sh
pipx install dawnfix          # PyPI: dawnfix (the tick), logbill, parity, sweeper, leastpriv, receipt, fleet
dawnfix validate --config .dawnfix.yml
npx dawnfix flare --help      # npm: the Cloudflare audit (also node flare/dist/cli.js)
```

## What it costs you

Dawnfix itself is free, with no key. It runs on accounts you already pay for, and those
bills go to you, not to us:

- **Anthropic tokens**, on your own `ANTHROPIC_API_KEY`. Only the diagnose or fix job uses
  them, and only on a run that found a new error. A quiet hour spends no tokens.
  `limits.fix_prs_per_day` and the agent's `max_turns` cap a busy day.
- **GitHub Actions minutes.** The read job runs every hour, about a minute each, so roughly
  750 minutes a month on the default schedule, plus the agent jobs when they run. Free on
  public repos; on private repos they count against your plan's included minutes.
- **AWS API calls** in your account: the tick reads with `FilterLogEvents` and
  `DescribeAlarms`, and load balancer 5xx with `GetMetricData` ($0.01 per 1,000 metrics).
  Logbill's Logs Insights queries are billed per GB scanned; it prints the estimate and
  stops at its budget.
- **AWS Cost Explorer, for Receipt only**: $0.01 per request, one per deploy (two with
  `--tag-key`).

| `autonomy` | What happens when a new error shows up |
|---|---|
| `diagnose` | An issue: cause with `file:line`, impact, severity. The agent has no shell and the job cannot push |
| `plan` | An issue with the planned test and fix |
| `draft-pr` | A failing test, then the fix, as two commits on `dawnfix/<fingerprint>`, opened as a draft PR. An issue when no cause or failing test can be shown |

## Use it from your coding agent

[prompts/](prompts/README.md) holds copy-paste prompts for any coding agent (Claude Code,
Codex, Cursor and others): set up Dawnfix in a repo, diagnose or fix a findings file, check
status, and run each tool below. Paste one, or ask your agent to save it as a skill or a
command. [prompts/ci/](prompts/ci/) holds the instructions the workflow gives its agent.

## What is here

| Folder | |
|---|---|
| [core/](core/README.md) | `dawnfix-core`: the deterministic tick (query, fingerprint, dedupe, redact), the findings and ingest schemas |
| [.github/workflows/](.github/workflows/) | the reusable workflows `dawnfix.yml`, `parity.yml`, `flare.yml`, `receipt.yml`, and `release.yml` |
| [templates/](templates/) | `.dawnfix.yml` and the copy-it-yourself workflows: `dawnfix.yml`, and the optional `dawnfix-parity.yml`, `dawnfix-flare.yml`, `dawnfix-receipt.yml` |
| [infra/](infra/aws/README.md) | the read-only AWS role (CloudFormation), its verifier, the GCP Workload Identity script |
| [prompts/](prompts/README.md) | copy-paste prompts for coding agents, and the CI agent's instructions |
| [logbill/](logbill/README.md) | Dawnfix Logbill: read-only CloudWatch Logs bill X-ray that runs on your machine |
| [parity/](parity/README.md) | Dawnfix Parity: read-only config drift between AWS environments and a secret inventory; names and metadata only |
| [flare/](flare/README.md) | Dawnfix Flare: read-only audit of Cloudflare accounts and Workers and your wrangler files; one bundled file, `node flare/dist/cli.js` |
| [sweeper/](sweeper/README.md) | Dawnfix Sweeper: what an AWS migration left behind, priced per month, with a teardown plan; never deletes |
| [leastpriv/](leastpriv/README.md) | Dawnfix Leastpriv: least-privilege trim of one IAM role from last-accessed data, as a PR body and diffs; never changes IAM |
| [receipt/](receipt/README.md) | Dawnfix Receipt: a comment on every production deploy with what it did to the AWS bill |
| [fleet/](fleet/README.md) | Dawnfix Fleet: a read-only collector for agencies that look after many client accounts |
| [hosted/](hosted/README.md) | a helper for Dawnfix Enterprise, the hosted part (below) |

Also [cli/](cli/README.md), the npm package `dawnfix` (`init`, `doctor`, `flare`), and
`pyproject.toml`, the PyPI package `dawnfix` (core and the Python tools in one). How a
release is published: [RELEASING.md](RELEASING.md).

Tests: `cd core && make install && make test`; `core/.venv/bin/pytest -q infra/tests`;
`cd <logbill|parity|sweeper|leastpriv|receipt> && make install test`;
`cd fleet/collector && make install && make test`;
`cd flare && npm ci && npm test && npm run build:check`;
`cd cli && npm ci && npm test && npm run build:check`.

## Enterprise (hosted, optional)

Everything above runs in your own accounts with no key. Dawnfix Enterprise is our hosted
part: a status page, digest and alert emails, the Fleet board, and support.
Dawnfix Enterprise is sold by contact: [dawnfix@sivakoza.ai](mailto:dawnfix@sivakoza.ai). It is a monthly
subscription, priced per organization (https://dawnfix.dev/pricing). With an Enterprise key
in the `DAWNFIX_ENTERPRISE_KEY` secret (passed to the reusable workflow; the templates also
read the older name `DAWNFIX_LICENSE`), the workflows also send counts (never log text, names or
values) to the hosted service. Field by field: `core/schema/ingest.schema.json` and
https://dawnfix.dev/security. Without the key, each of those steps prints one line, such as
"Hosted reporting (status page and digest) needs an Enterprise key.", sends nothing, and the
run goes on.

## Licence

Dawnfix is under the [Functional Source License, Version 1.1, ALv2 Future License](LICENSE)
(FSL-1.1-ALv2). In plain words, and the licence text is what counts:

- You may use, copy, modify and run it, including in your company and for your clients'
  systems.
- You may not sell it or offer it, or a substitute for it, as a competing product or service.
- Every release becomes Apache-2.0 two years after it is published.
- Contributions are welcome.

Versions released before 27 Nov 2026 were MIT-licensed; from v0.2.0 on the code is under
FSL-1.1-ALv2.
