# AGENTS.md

For coding agents that set up, run or change Dawnfix. Humans: start with README.md.

## What this repo is

Dawnfix, an AI SRE for AWS and GCP that runs in your own GitHub Actions. All of it is free
to run, with no key: the workflow in `templates/github/workflows/dawnfix.yml`, the core CLI
(`core/`, command `dawnfix`) and the tools `logbill/ parity/ flare/ sweeper/ leastpriv/
receipt/ fleet/`. The hosted Enterprise part (status page, digest, Fleet board) is optional.

## Setting it up for someone

Follow `prompts/setup.md`. In short:

- Pin `v0.2.0` or later (a tag or commit SHA) wherever a ref is asked for. Older refs have no
  `prompts/ci/`, which the workflow loads.
- Say what you will change before you change it, and wait for a yes.
- Cloud access is read-only. Check an AWS role with `infra/aws/verify_readonly.py`; if it
  fails, stop. Never widen a policy to make it pass.
- Never ask for a secret in the chat and never print one. The user runs
  `gh secret set ANTHROPIC_API_KEY` themselves.
- Start with `autonomy: diagnose`. Check the config with `dawnfix validate --config .dawnfix.yml`
  and try it with `dawnfix tick --config .dawnfix.yml --state "$(mktemp -d)/state.json" --baseline --dry-run`.
- Tell the user what it costs them: their Anthropic tokens, GitHub Actions minutes, small
  CloudWatch API charges; Cost Explorer at $0.01 a request if they use Receipt.

## Running a tool

Each tool has a prompt in `prompts/<tool>.md` with its exact install and flags, and a
README in its folder. The tools read with the user's own credentials and print JSON or
Markdown; none of them changes anything in the cloud.

## Changing the code

- Tests: `cd core && make install && make test`; `cd <tool> && make install test`;
  `cd flare && npm ci && npm test && npm run build:check`; `actionlint` on the workflows.
- Licence: FSL-1.1-ALv2 (`LICENSE`). Keep `FSL-1.1-ALv2` in manifests and workflow headers.
- Dawnfix never merges, deploys or pages anyone. Keep it that way.
