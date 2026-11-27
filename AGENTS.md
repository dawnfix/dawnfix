# AGENTS.md

For coding agents that set up, run or change Dawnfix. Humans: start with README.md.

## What this repo is

Dawnfix, an AI SRE for AWS and GCP that runs in your own GitHub Actions. Free & source
available (FSL-1.1-ALv2), with no key: the reusable workflows in `.github/workflows/` (and
their copy-it-yourself forms in `templates/github/workflows/`), the core CLI (`core/`,
command `dawnfix`), the tools `logbill/ parity/ flare/ sweeper/ leastpriv/ receipt/ fleet/`,
and the npm CLI in `cli/` (`npx dawnfix init | doctor | flare`). The hosted Enterprise part
(status page, digest, Fleet board) is optional. Call it "source available": FSL-1.1-ALv2 is not an OSI licence.

## Setting it up for someone

Follow `prompts/setup.md`. In short:

- The short way is `npx dawnfix init` (it previews the files; `--dry-run` writes nothing),
  then `npx dawnfix doctor`. The caller it writes uses `@v0`; pin `@v0.3.0` or a commit SHA
  when asked to freeze it.
- Say what you will change before you change it, and wait for a yes.
- Cloud access is read-only. Check an AWS role with `infra/aws/verify_readonly.py`; if it
  fails, stop. Never widen a policy to make it pass.
- Never ask for a secret in the chat and never print one. The user runs
  `gh secret set ANTHROPIC_API_KEY` themselves.
- Start with `autonomy: diagnose`. Install the Python CLIs with `pipx install dawnfix` (PyPI).
  Check the config with `dawnfix validate --config .dawnfix.yml`
  and try it with `dawnfix tick --config .dawnfix.yml --state "$(mktemp -d)/state.json" --baseline --dry-run`.
- Tell the user what it costs them: their Anthropic tokens, GitHub Actions minutes, small
  CloudWatch API charges; Cost Explorer at $0.01 a request if they use Receipt.

## Running a tool

Each tool has a prompt in `prompts/<tool>.md` with its exact install and flags, and a
README in its folder. The tools read with the user's own credentials and print JSON or
Markdown; none of them changes anything in the cloud.

## Changing the code

- Tests: `cd core && make install && make test`; `cd <tool> && make install test`;
  `cd flare && npm ci && npm test && npm run build:check`;
  `cd cli && npm ci && npm test && npm run build:check`; `actionlint` on the workflows.
- `.github/workflows/{dawnfix,parity,flare,receipt}.yml` are the source; each template in
  `templates/github/workflows/` is the same below its marker line, with repository variables
  for inputs. Change both the same way (a test compares them).
- Releases: `RELEASING.md`. One version everywhere; the release workflow checks it.
- Licence: FSL-1.1-ALv2 (`LICENSE`). Keep `FSL-1.1-ALv2` in manifests and workflow headers.
- Dawnfix never merges, deploys or pages anyone. Keep it that way.
