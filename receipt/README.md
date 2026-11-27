# Dawnfix Receipt

Free, with no key. Source available under FSL-1.1-ALv2 (see [LICENSE](../LICENSE) at the
repo root). What did this deploy do to the AWS bill? Compares Cost Explorer daily cost for N days before and after a
deploy (by service and usage type, and by a cost allocation tag if you name one), and keeps
**one** comment on the deployed commit (or a PR) up to date:

> deploy abc1234: +$40.07/day (+305%), mostly NAT Gateway data processing (+$35.10/day)

Install from PyPI: `pipx install dawnfix` (or `pip install dawnfix` in a venv). One package
holds every Dawnfix CLI (`dawnfix`, `logbill`, `parity`, `sweeper`, `leastpriv`, `receipt`,
`fleet`); `receipt --version` prints the release. For development in this folder:
`make install test` (an editable install of this tool and `../core`).

It runs in the customer's own GitHub Actions: the reusable `.github/workflows/receipt.yml`
(called as `dawnfix/dawnfix/.github/workflows/receipt.yml@v0`; copy-it-yourself form
`templates/github/workflows/dawnfix-receipt.yml`) fires on every successful `deployment_status` to the production environment
and re-runs the last 5 days' deploys daily, so the comment goes from "waiting for data" to
provisional to final. The comment stays in GitHub. Setup steps are in the workflow's header;
or use it from your coding agent with the copy-paste prompt `prompts/receipt.md`. Only with
the optional Dawnfix Enterprise key (`DAWNFIX_ENTERPRISE_KEY`) does the hosted service get a
counts-only summary for the status page's "Deploy cost" section and the digest (below).
Sample comment: https://dawnfix.dev/receipt.

```bash
receipt --deploy-sha "$SHA" --deployed-at 2026-10-20T14:03:00Z [--window 3d] [--tag-key team] \
  [--post --repo owner/name [--pr 123]] [--json receipt.json] [--ingest-out receipt-ingest.json] \
  [--cache-dir .receipt-cache]
```

Why this and not AWS's free cost-anomaly investigations: those start from an anomaly and
explain spend. This starts from a deploy and lands the answer where the change was
reviewed, including changes too small to be an anomaly.

- **CE lag.** A day counts once it has been over for `--lag-hours` (24). Until all after-days
  are in, the comment says "provisional" and when to re-run. The deploy day is left out.
- **Idempotent.** The comment carries `<!-- dawnfix-receipt:sha=<sha> -->`; re-runs edit it in
  place, and skip the edit when nothing but the footer changed.
- **Cost.** CE charges $0.01 per request. One run is one request (two with `--tag-key`), none
  if no after-day is complete yet. Responses are cached on disk; a response whose days have
  all settled (72h) is reused forever, others for 6h. Each comment states how many requests it made.
- **Noise.** A change smaller than max($1/day, 3% of baseline, 2x the baseline's day-to-day
  spread) is reported as "no material change". Credits and refunds are excluded.

## What leaves the customer's CI

Without an Enterprise key, nothing: the comment and the job summary stay in GitHub. With one,
the workflow sends this document to the hosted service.

`--ingest-out PATH` adds this deploy to a `dawnfix.receipt/1` document
(`schema/receipt-ingest.schema.json`, written by `src/dawnfix_receipt/ingest.py`; a loop
over several deploys builds one document). Per deploy, and nothing else:

| Field | |
|---|---|
| `deploy_id` | 16 hex of SHA-256 over `dawnfix.receipt/1:` + the commit SHA: an id across daily re-runs, not the SHA |
| `deployed_on` | UTC day |
| `window_days`, `after_days`, `final` | how complete the comparison is (provisional until every after-day settled) |
| `material` | the change cleared the noise floor |
| `delta_cents_per_day_bucket` | signed $/day change in cents snapped toward zero on a 1-2-5 grid (`2000` = +$20 to +$50 a day) |
| `top_driver` | the AWS product family that moved most, from a closed enum (`ec2_other`, `rds`, `s3`, ... `other`, `none`) |

Decision (28 Oct 2026): AWS service names are AWS's own catalogue, not customer data, so the
largest driver is sent, but only as a closed enum mapped from Cost Explorer's SERVICE value
(a new or odd name becomes `other`; no free text can pass). Never sent: the commit SHA,
before/after totals (they would give away the size of the bill), usage types (they carry
regions and instance sizes), tag keys and values (customer-defined), account, resource or
repo names (the repo travels only as the `X-Dawnfix-Repo` header, as for Parity and Flare).
`tests/test_ingest.py` and `tests/e2e/test_receipt_workflow.py` check it.

## Permissions

`iam/receipt-ce-read-policy.json`: `ce:GetCostAndUsage` only (the guard in
`src/dawnfix_receipt/guard.py`, on dawnfix-core's `make_client`, refuses every other call
and service; a test keeps the two equal). `iam/github-oidc-trust-policy.json` trusts
`repo:OWNER/REPO:environment:dawnfix-receipt`: the workflow's job runs in that GitHub
environment. Restrict the environment's deployment branches to the default branch if your
deployer creates deployments from branch refs. Using an environment records a deployment to
`dawnfix-receipt`; the workflow ignores every environment but production, so it does not loop.

Commit comments need `contents: write`; the workflow asks for nothing else in GitHub but
`deployments: read` and `id-token: write`. On a public repository the comment and the job
summary are public: use Receipt on private repositories.

Brand, org, URLs and the comment marker are constants in `src/dawnfix_receipt/constants.py`.

`sample/make_sample.py` builds `sample/sample.json` (the site's sample comment and ingest)
from the test suite's synthetic Cost Explorer series; a test fails when it is stale.

Tests: `make install test` (installs `../core` too). botocore Stubber and a fake GitHub; no network.

Source available under FSL-1.1-ALv2: see [LICENSE](../LICENSE) at the repo root.
