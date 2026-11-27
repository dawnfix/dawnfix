# dawnfix-core

The deterministic half of Dawnfix (the read job of the workflow). One `tick`
reads the last hour of production errors, read-only, folds them into
fingerprints, drops what it has seen before, redacts everything and writes
`findings.json`. No LLM runs here; when nothing is new the workflow stops and
spends no tokens.

Free. Source available under FSL-1.1-ALv2 (see [LICENSE](../LICENSE) at the repo root).
It runs in your own GitHub Actions with no key; the main workflow is the reusable
`.github/workflows/dawnfix.yml` (copy-it-yourself form: `templates/github/workflows/dawnfix.yml`).

## Install

From PyPI: `pipx install dawnfix` (add `[gcp]` for GCP sources: `pipx install 'dawnfix[gcp]'`).
The package `dawnfix` is this core (command `dawnfix`) and every Python tool, one version.
The reusable workflow installs the same package at its own release. For development:

```sh
cd core
make install          # uv venv + editable install with dev extras
make test
```

Without `make`: `uv venv && uv pip install -e '.[dev]' && .venv/bin/pytest -q`.
GCP support is an extra (`pip install 'dawnfix-core[gcp]'`); AWS-only installs
never import the Google client.

## Run

```sh
dawnfix validate --config .dawnfix.yml
dawnfix config --config .dawnfix.yml --json   # resolved config, defaults filled in
dawnfix tick --config .dawnfix.yml --state state.json --out findings.json \
  [--window-minutes 60] [--ingest-out ingest.json] [--dry-run] [--baseline]
```

| Exit | Meaning |
|---|---|
| 0 | No new fingerprints (spikes of known ones may still be in `findings.json`) |
| 10 | New fingerprints: run the fix job |
| 1 | Every source failed (credentials, permissions); state is not written |
| 2 | Bad config, bad state file or bad arguments |

- `--dry-run` prints exactly the ingest payload that would leave the account
  and writes nothing (no state, no findings).
- `--baseline` records everything seen as known and exits 0. Use it on the
  first run against a noisy prod so the first real tick only reports new errors.
- Credentials come from the environment. In GitHub Actions that is the OIDC role
  assumed by `aws-actions/configure-aws-credentials` (the `role` in the config)
  and `google-github-actions/auth` for GCP.

## Config

See `examples/dawnfix.yml`, and `templates/dawnfix.yml` at the repo root for every key. Notes:

- `log_groups` entries can be a name or `{name, filter_pattern, stream_prefix}`.
  Without `filter_pattern`, a broad error pattern is used (`DEFAULT_FILTER` in
  `sources/aws.py`); lines are then classified locally (5xx, level >= 50,
  ERROR/FATAL, `*Error`/`*Exception`) and the rest dropped.
- `alb: app/<name>/*` matches load balancers by glob; the tick sums
  `HTTPCode_ELB_502/503/504_Count` per balancer and `HTTPCode_Target_5XX_Count`
  per target group.
- `limits` also takes `max_events_per_source` (5000), `max_findings` (50, at
  most 150: the hosted ingest caps a tick at 64 KB, about 300 bytes per finding),
  `spike_factor` (3) and `spike_min_count` (10).
- `test: {command: "npm test"}` (optional): the one command the fix agent may
  run. Plain words only (letters, digits, `. / : = @ + _ -`, single spaces, at
  most 200 characters), because the workflow turns it into the agent's only Bash
  permission, `Bash(<command>:*)`. Without it the fix job can only open issues.
- `dawnfix config --json` prints `version`, `autonomy`, `schedule`, `limits`,
  `phi_mode`, `report`, `test.command` (or null), source ids and the rule count.
  The workflow reads its limits and test command from it with `jq`.
- `extends` is not implemented yet and is rejected with a clear message.

Rules: every condition must match (`<field> <op> <value>`; ops `== != ~= ^= $=`
and `> >= < <=` on `status`/`count`; fields `source source_id kind service route
method status error error_class alarm count severity fingerprint`). Actions are
`ignore`, `severity: critical|high|medium|low` and `notify: email|issue|none`.
Rules run in order; `ignore` sticks and the last matching severity wins.
Default severity: `high` for alarms and load balancer 5xx, `medium` otherwise.

## What it does to the data

1. **Query** (read-only): CloudWatch `FilterLogEvents` per log group,
   `DescribeAlarms` in `ALARM`, ALB metrics via `GetMetricData`; Cloud Logging
   entries matching `filter` (default `severity>=ERROR`). Every AWS client
   refuses any operation outside that allowlist before the request is built.
   Paginated and capped per source.
2. **Normalize**: paths become templates (`/users/:id/mail/:email`, decoded
   `%40`/`%2540` first), error class (`TypeError`, `ECONNRESET`, `HTTP502`) and a
   message stem with timestamps, numbers and redacted values folded.
3. **Fingerprint**: first 16 hex of SHA-256 over (source, service, route
   template, error stem). Stable across runs and machines.
4. **Dedupe**: the state file keeps `first_seen`, `last_seen`, `total`, `ticks`
   per fingerprint and the end of the last window per source (so overlapping
   schedules don't double count). A fingerprint is `new` if unseen, `spike` if
   this window's count is >= `spike_factor` x its per-tick mean and >=
   `spike_min_count`, otherwise `known` (counted, not listed).
5. **Redact**: every string in the output passes `redact.py` (emails incl.
   `%40`/`%2540`, phones, long ids, ObjectIds, UUIDs, JWT/bearer, URL userinfo,
   query strings, printable ASCII only) and is length-capped. Instruction-like
   text is left as inert data; the fix job must wrap it as untrusted.
6. **PHI mode** (`phi_mode: true`): no `error` stem and no `sample`; only
   fingerprints, counts, classes and route templates.

## Read-only AWS clients (public API)

```python
from dawnfix_core import ReadOnlyViolation, make_client   # also from dawnfix_core.awsguard

logs = make_client(session, "logs", "eu-central-1")                          # default allowlist
sts = make_client(session, "sts", None, allowed={"GetCallerIdentity"})        # your own
```

`make_client(session, service, region, allowed=None)` returns a boto3 client that raises
`ReadOnlyViolation` for any operation outside its allowlist, before the request is built.
`allowed` takes AWS operation names (`FilterLogEvents`, not `filter_log_events`); `None`
uses `DEFAULT_ALLOWED[service]` — `logs`: FilterLogEvents; `cloudwatch`: DescribeAlarms,
GetMetricData; `elbv2`: DescribeLoadBalancers, DescribeTargetGroups — and refuses every call
for any other service. The guard is registered first on `provide-client-params` (the first
event of every call, before a botocore `Stubber` answers) and on `before-parameter-build`.
The names stay importable from `dawnfix_core.sources.aws` for older callers. Other
Dawnfix tools (logbill, parity, fleet, sweeper, receipt, leastpriv) can build their clients with it
instead of carrying their own guard copies.

## Outputs

- `findings.json`, schema `schema/findings.schema.json`: for the fix job, stays
  in the customer's Actions run.
- Ingest payload, schema `schema/ingest.schema.json`: the only thing meant for
  the hosted service. Enums, counts, fingerprints, route templates, error class
  and a PR URL slot; no service names, no messages.

## Layout

```
src/dawnfix_core/
  awsguard.py   make_client + ReadOnlyViolation: the read-only boto3 guard
  cli.py        dawnfix tick | validate | config
  tick.py       one tick end to end
  config.py     .dawnfix.yml loader and validation
  rules.py      conditions and actions
  sources/      aws.py, gcp.py
  normalize.py  route templates, error stems, fingerprints
  redact.py     redaction (also a stdin filter: python -m dawnfix_core.redact)
  state.py      known fingerprints
  findings.py   findings.json and ingest payload
schema/         JSON Schemas for both outputs
examples/       sample .dawnfix.yml
tests/          pytest, no live cloud (botocore Stubber, fake GCP client)
```
