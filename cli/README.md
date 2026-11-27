# dawnfix (npm)

Set up [Dawnfix](https://dawnfix.dev), the AI SRE that runs in your own GitHub Actions, in a
repo; check the setup; and run Dawnfix Flare. One bundled file, no dependencies, Node 20 or
newer. Source available under FSL-1.1-ALv2 (the `LICENSE` in this package).

```sh
npx dawnfix init           # shows .dawnfix.yml and a 15-line workflow, writes them when you say yes
npx dawnfix init --dry-run # only shows them, and the next steps
npx dawnfix doctor         # config, pinned workflow, secret and variable names, Free or Enterprise
npx dawnfix flare --help   # read-only Cloudflare audit
```

`init` never asks for a secret and never writes one. It prints the commands you run: the
read-only cloud role (AWS CloudFormation or GCP Workload Identity Federation) and
`gh secret set ANTHROPIC_API_KEY`.

The workflow it writes calls the reusable workflow
`dawnfix/dawnfix/.github/workflows/dawnfix.yml@v0`. The Python tools (`dawnfix`, `logbill`,
`parity`, `sweeper`, `leastpriv`, `receipt`, `fleet`) are the PyPI package `dawnfix` of the
same version.

Docs and source: https://github.com/dawnfix/dawnfix

## Development (in the repo, `cli/`)

```sh
npm ci
npm run build         # writes dist/cli.js from src/ and ../flare/src/; commit it
npm run build:check   # exit 1 if dist/cli.js is stale
npm test              # node --test: init, doctor, flare, the bundle, npm pack + install
```
