# Use it from your coding agent

Dawnfix runs from the command line and from GitHub Actions. These files are prompts you
can give any coding agent (Claude Code, Codex, Cursor, and others) so it runs a Dawnfix
tool for you, the way the tool is meant to be run: read-only credentials, no secret in the
chat, nothing changed without your yes.

## How to use them

1. Open the file for the job you want.
2. Copy the fenced block.
3. Paste it into your agent, in the repo or folder you want to work on. Or ask the agent
   to save it as a reusable skill, command or rule (for example "save this as a skill
   named dawnfix-logbill"), so you can call it again later.

Each prompt installs the tool from the public repo, github.com/dawnfix/dawnfix, at a ref
you choose: a release tag or a commit SHA (v0.2.0 or later for the workflows, which load
`prompts/ci/`). Pin one so you know which code runs. Nothing here needs a licence key. The
optional Enterprise key (`DAWNFIX_LICENSE`) only turns on hosted reporting at
https://dawnfix.dev (see https://dawnfix.dev/pricing).

`prompts/ci/` holds the instructions the GitHub Actions workflow gives its own agent. You
do not paste those; the workflow fetches them.

## Prompts

| File | What it does |
|---|---|
| [setup.md](setup.md) | Set up Dawnfix in a GitHub repo: `.dawnfix.yml`, a read-only AWS role or GCP identity, the workflow, a dry run, a setup PR |
| [diagnose.md](diagnose.md) | Explain new errors in a `findings.json`: cause with `file:line`, impact, severity, as GitHub issues on your yes |
| [fix.md](fix.md) | Fix one new error locally: a failing test first, then the smallest fix, a draft PR only on your yes |
| [status.md](status.md) | How Dawnfix is doing in this repo: workflow runs, open issues and PRs, acceptance rate |
| [tick.md](tick.md) | Run one read-only tick on your machine to debug sources and rules; dry run by default |
| [logbill.md](logbill.md) | Dawnfix Logbill: what your CloudWatch Logs bill is made of, and the lines in your code behind it |
| [parity.md](parity.md) | Dawnfix Parity: config drift between two AWS environments, and unused or never-rotated secrets |
| [flare.md](flare.md) | Dawnfix Flare: read-only audit of your Cloudflare accounts, Workers and wrangler files |
| [sweeper.md](sweeper.md) | Dawnfix Sweeper: what an AWS migration left behind, priced, with a teardown plan you run |
| [leastpriv.md](leastpriv.md) | Dawnfix Leastpriv: remove the unused permissions of one IAM role, as a reviewable patch |
| [receipt.md](receipt.md) | Dawnfix Receipt: what a deploy did to the AWS bill, locally or as a workflow |
| [parity-ci.md](parity-ci.md) | Add the Parity drift check to GitHub Actions |
| [flare-ci.md](flare-ci.md) | Add the daily Flare audit to GitHub Actions |
| [fleet-setup.md](fleet-setup.md) | Add a client to the Fleet collector in an agency's repo |
