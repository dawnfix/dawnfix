# Dawnfix Parity

Read-only config parity and secret inventory for teams whose config lives in AWS
itself: SSM Parameter Store, Secrets Manager, ECS task definition env and Lambda env vars.

- `parity diff --left dev --right prod`: what exists in one environment and not the
  other, type mismatches, references to parameters/secrets that do not exist, and
  prod pointing at dev's paths.
- `parity inventory`: per secret/parameter: last changed, last read, rotation, who
  references it; flags unread, never rotated, rotation overdue, orphaned.
- `parity check`: `diff` for CI. Exits 1 on drift and writes a Markdown job summary;
  `--inventory` adds the inventory flags, `--ingest-out` writes the counts-only
  `dawnfix.parity/1` document (below). A composite GitHub Action (`action.yml`) wraps it.
- Literal secrets in plain env vars: an ECS `environment` entry or Lambda variable whose
  name says credential (`DB_PASSWORD`, `JWT_SECRET`, `apiToken`, `STRIPE_API_KEY`,
  `PRIVATE_KEY`) or whose value has a known credential shape (`sk_live_…`, `AKIA…`,
  `ghp_…`, a PEM private key), holding a literal instead of a reference. Reported by
  name only.

Names and metadata only. **Values are never printed or stored.** With
`--compare-hashes` parity reads values, turns each into a salted SHA-256 (HMAC, fresh
random salt per run) on arrival, and only ever reports "same" or "differs".

Free. Source available under FSL-1.1-ALv2 (see [LICENSE](../LICENSE) at the repo root).
Run it as a CLI, in CI (the composite action or the free workflow
`templates/github/workflows/dawnfix-parity.yml`, see [CI](#ci)), or use it from your coding
agent with the copy-paste prompts `prompts/parity.md` and `prompts/parity-ci.md`. The weekly
"unread / never-rotated / orphaned secrets" email is part of Dawnfix Enterprise, our hosted
service. Brand, org and URLs live in [`src/dawnfix_parity/brand.py`](src/dawnfix_parity/brand.py)
(plus the non-Python copies listed in `tests/test_brand.py`). Depends on `dawnfix-core`
(`../core`) for the read-only AWS client guard.

Install from PyPI: `pipx install dawnfix` (or `pip install dawnfix` in a venv). One package
holds every Dawnfix CLI (`dawnfix`, `logbill`, `parity`, `sweeper`, `leastpriv`, `receipt`,
`fleet`); `parity --version` prints the release. For development in this folder:
`make install test` (an editable install of this tool and `../core`).

## Install and run

```sh
make install          # uv venv + editable ../core and parity, with pytest (Python 3.11+)
make test

.venv/bin/parity validate                      # parse .parity.yml; no AWS calls
.venv/bin/parity diff --left dev --right prod
.venv/bin/parity diff --left dev --right prod --compare-hashes --format markdown
.venv/bin/parity check --left dev --right prod --fail-on missing_in_right,type_mismatch,dangling_reference
.venv/bin/parity inventory --env prod
.venv/bin/parity inventory --env prod --cloudtrail --cloudtrail-days 90 --format json -o inv.json
.venv/bin/parity check --left dev --right prod --inventory --ingest-out parity-ingest.json
.venv/bin/parity diff --left dev --right prod --aws-profile dev=ci-dev --aws-profile prod=ci-prod
```

`--format json` reports end with a `pitch` (`line`, `url`) from `brand.py`: one line about
the free CI workflow.

Credentials: per environment `aws.profile` (local) and/or `aws.role_arn` (assumed with
`sts:AssumeRole`); in CI the role from GitHub OIDC. `--aws-profile ENV=PROFILE` (repeatable)
replaces both `aws.profile` and `aws.role_arn` for ENV: the CI workflow keeps one OIDC role
per environment as a named profile. Expired SSO session: exit 3 with the `aws sso login` hint.

## Config: `.parity.yml`

See [`examples/.parity.yml`](examples/.parity.yml) for every field. Per environment:

| Field | Meaning |
|---|---|
| `region`, `aws.profile`, `aws.role_arn`, `aws.account_id` | where and as whom; `account_id` is optional (taken from ARNs otherwise) and lets parity spot ARNs in the other account |
| `ssm.paths` | `/app/dev` = path, recursive; no leading `/` = name prefix |
| `secrets.prefixes` | Secrets Manager name prefixes |
| `ecs` | list of `{cluster, services: [globs], task_definitions: [families]}`; services use their current task definition, families their latest ACTIVE revision |
| `lambda.functions` | function name globs |
| `normalize` | rules run in order after the matched SSM path / secret prefix is stripped: `env_token: dev` (`api-dev` -> `api-{env}`), `strip_prefix`, `replace: {from, to}`, `regex: {pattern, to}`; each may be limited with `kinds: [ssm, secret, ecs, lambda]` |
| `markers` | extra substrings that identify this environment, for cross-environment detection |

Top level: `allow` (known differences: `{kind, key glob, reason}`; allowed findings
are shown but never fail `check`), `hashes.must_match` / `hashes.must_differ` (key globs),
`inventory.unread_days` / `rotation_max_age_days` (default 90).

## What is compared

Every item gets a key `kind:normalised-name`:

| Kind | Key example | Type compared |
|---|---|---|
| `ssm` | `ssm:DB_URL` | `String` / `StringList` / `SecureString` |
| `secret` | `secret:stripe` | `Secret` |
| `ecs` | `ecs:api-{env}/app/DB_URL` (service/container/var) | `plain` (environment) vs `secret-ref` (secrets/valueFrom) |
| `lambda` | `lambda:worker-{env}/QUEUE` | `plain` |

Findings (`check` fails on all but `unverifiable_reference` and `duplicate_key` by default;
change with `--fail-on`):

| Finding | When |
|---|---|
| `missing_in_left` / `missing_in_right` | key in one environment only; a whole missing ECS service or Lambda is one finding (`lambda:fn/*`) |
| `type_mismatch` | e.g. `String` in dev, `SecureString` in prod; `high` when one side is secret and the other plain (a secret moved into a plain env var) |
| `dangling_reference` | a task definition `secrets.valueFrom`, `repositoryCredentials`, or an env value that names a parameter/secret which does not exist (checked with `DescribeParameters` / `DescribeSecret`, metadata only) |
| `cross_env_reference` | prod's task def/Lambda points at dev's path, prefix or account (and vice versa) |
| `value_shared` | `--compare-hashes`: a `SecureString`/secret (or `must_differ` key) holds the same value in both |
| `value_differs` | `--compare-hashes`: a `must_match` key differs |
| `unverifiable_reference` | target in an account that is not a configured environment, or the lookup was denied |
| `duplicate_key` | two names in one environment normalise to the same key: your rules are too broad |
| `plaintext_secret` | (fails by default, `high`) a plain ECS/Lambda env var holds a literal credential: by name (tokens `PASSWORD`, `PASSWD`, `SECRET`, `TOKEN`, `API_KEY`, `PRIVATE_KEY`, `ACCESS_KEY`, `CLIENT_SECRET`, `CREDENTIALS`, ... in `SNAKE`, `kebab` or `camelCase`; not names about a secret such as `SECRET_ARN`, `TOKEN_TTL`, `PASSWORD_MIN_LENGTH`) or by value shape (Stripe live, AWS access key id, GitHub, Slack, `sk-…` API keys, PEM private key). Not flagged: references (ARNs, known names, paths), empty/boolean/numeric values, placeholders (`${X}`, `{{resolve:…}}`), URLs without credentials. Only the name and the reason (`name` / `value_shape`) are reported (`src/dawnfix_parity/refs.py`) |

### How references are found

- ECS `secrets[].valueFrom`: SSM ARN, Secrets Manager ARN (full, partial, or with
  `:json-key:stage:id` suffix), or a bare SSM name (same account/region, as ECS reads it).
- ECS `repositoryCredentials.credentialsParameter`.
- ECS `environment` values and Lambda env values are inspected for: an embedded SSM or
  Secrets Manager ARN; a known parameter/secret name; a path under any configured SSM
  path (a value like `/app/prod/` is a *prefix reference* covering the subtree). Only the
  matched name/ARN is ever reported; any other value is dropped unseen.
- Not detectable statically: names built in code, the Parameters and Secrets Lambda
  extension, `environmentFiles` on S3. `--cloudtrail` covers the first two at runtime.

## Inventory flags

| Flag | Secrets Manager | SSM (`SecureString` for rotation) |
|---|---|---|
| `unread` | `LastAccessedDate` missing or older than `unread_days` | only with `--cloudtrail` and a window of at least `unread_days`: no reads seen |
| `never_rotated` | rotation off and never rotated | `Version` is 1 |
| `rotation_overdue` | last rotated (or created) more than `rotation_max_age_days` ago; with rotation on, the rotation Lambda is probably failing | last changed more than `rotation_max_age_days` ago |
| `orphaned` | no static reference from any configured ECS service/Lambda in any environment, and no CloudTrail reads | same |

`LastAccessedDate` is day-granular in AWS. "Orphaned" means "no reference parity can
see": check `--cloudtrail` before deleting anything.

### `--cloudtrail` (opt-in)

Looks up `GetSecretValue`, `GetParameter`, `GetParameters` and `GetParametersByPath` in
CloudTrail event history (`LookupEvents`) and shows readers per item, grouped by role
(the session issuer, not the per-task session). Rate-limited to 1.5 calls/s (the API
allows 2/s per account and region), capped by `--cloudtrail-max-pages` per event name
(50 events a page; a warning says when the cap was hit), window 1-90 days (CloudTrail's
limit). Failed/denied calls are not counted. Event history is per region; values are
never in CloudTrail.

## CI

Read-only, and free to run:

- **The composite action** below (or `parity check` in any CI). Fails the job on drift and
  writes the Markdown job summary. Nothing leaves the runner.
- **The Dawnfix Parity workflow**, also free: call the reusable
  `dawnfix/dawnfix/.github/workflows/parity.yml@v0` (the caller is in its header), or copy
  `templates/github/workflows/dawnfix-parity.yml` (steps in its header, or give
  `prompts/parity-ci.md` to your coding agent): weekly (Mondays, before the
  digest) and on pushes to main touching `.parity.yml`, task definitions or IaC; one OIDC role
  per environment; `parity check --inventory --ingest-out`. The names stay in the job summary
  in GitHub. It prints the `dawnfix.parity/1` document in the log: counts per finding kind
  and per inventory flag, pass/drift, and a hashed environment-pair id
  ([`schema/parity-ingest.schema.json`](schema/parity-ingest.schema.json), closed objects, no
  strings beyond enums). Without a key nothing is sent anywhere.
- **Dawnfix Enterprise** (hosted, optional): with the `DAWNFIX_ENTERPRISE_KEY` secret the workflow
  also POSTs that document to `/v1/parity`. The hosted service turns it into a status-page
  trend and a Monday "unread / never-rotated / orphaned secrets" section in the digest, with
  a link back to the Actions run where the names are. Monthly subscription, priced per
  organization: https://dawnfix.dev/pricing.

```yaml
permissions: { id-token: write, contents: read }
steps:
  - uses: actions/checkout@v4
  - uses: aws-actions/configure-aws-credentials@v4
    with: { role-to-assume: "${{ vars.PARITY_ROLE_ARN }}", aws-region: eu-central-1 }
  - uses: dawnfix/dawnfix/parity@v0
    with: { left: dev, right: prod }
```

Full example: [`examples/workflow.yml`](examples/workflow.yml). Inputs: `left`, `right`,
`config`, `compare-hashes`, `fail-on`, `python-version`; output `exit-code`.

Exit codes: `0` no drift, `1` drift (`check` only; `diff` and `inventory` exit 0),
`2` config/usage error, `3` AWS error (code only; messages can echo input), `4` the
read-only guard refused a call (a bug: please report).

## Read-only by construction

- [`src/dawnfix_parity/aws.py`](src/dawnfix_parity/aws.py) lists every API operation
  parity may call (`READ_ONLY_OPERATIONS`), per service (`SERVICE_OPERATIONS`: an SSM client
  cannot call Secrets Manager operations, and so on). Clients come from `dawnfix-core`'s
  public `make_client` (`dawnfix_core.awsguard`), which refuses anything else with
  `ReadOnlyViolation` at the first event of the call (`provide-client-params`), before
  botocore validates or builds the request and before a Stubber answers.
- [`iam/`](iam/README.md): a metadata-only policy (no value-reading action at all), an
  opt-in hash-mode add-on (`ssm:GetParameters`, `secretsmanager:GetSecretValue`,
  `kms:Decrypt` via SSM/Secrets Manager only), and a GitHub OIDC trust policy. A test
  keeps the policies and the allow-list in sync.
- Values are read only with `--compare-hashes`. ECS `DescribeTaskDefinition` and Lambda
  `ListFunctions` return plain env values regardless; parity inspects them for
  references, then drops them (or keeps a digest in hash mode). Digests are excluded from
  every report and every `to_dict`; the salt is random per run and never leaves memory.

## Layout

```
src/dawnfix_parity/
  brand.py       brand, org and URL strings
  config.py      .parity.yml parsing, normalisation rules
  aws.py         per-service allowlists for dawnfix-core's guard, clients, AssumeRole
  collect.py     SSM / Secrets Manager / ECS / Lambda collection (two phases)
  refs.py        reference parsing from task defs and env values; plaintext-secret check
  resolve.py     reference -> existing item / owning environment / targeted lookup
  diff.py        findings
  inventory.py   rows and flags
  cloudtrail.py  opt-in LookupEvents, rate limiter
  report.py      text / Markdown / JSON
  ingest.py      the counts-only dawnfix.parity/1 document (--ingest-out)
  cli.py         diff | check | inventory | validate
tests/           botocore Stubber only; no network
schema/          parity-ingest.schema.json
sample/          make_sample.py -> sample.json (the site's /parity sample; a test keeps it current)
action.yml       composite GitHub Action
examples/        .parity.yml, workflow.yml
iam/             policies
```
