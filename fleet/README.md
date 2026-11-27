# Dawnfix Fleet: the agency board

One screen for an agency or contractor running N clients' production: per client, alarms
firing, spend this week against last, the soonest certificate expiry, Dawnfix findings and
draft PRs, whether the collector can still get in (and when it last did), and an orphan-count
slot. Plus a white-label weekly report per client, as a printable page and an opt-in email.

Built 27 Oct 2026; merged into the Worker and shipped as **Dawnfix Fleet** on
28 Oct 2026. **Nothing here has been deployed or run against a real cloud account.**

**The collector is free.** It runs in your own GitHub Actions with no key and no plan check.
Source available under FSL-1.1-ALv2 (see [LICENSE](../LICENSE) at the repo root). Without a
key, `fleet-collect.yml` writes `summary.json` per client, prints it in the job log and stops.
**The hosted board, the client reports and the weekly emails are Dawnfix Enterprise**: with
the optional `DAWNFIX_ENTERPRISE_KEY` secret the workflow also sends each summary to the board.
Enterprise is a monthly subscription, priced per organization (https://dawnfix.dev/pricing).

The product name, company and domain live in the Worker's one constants
module, `worker/src/brand.ts` (`FLEET_PRODUCT`, `NEUTRAL_SENDER`, `COMPANY`, `DEFAULT_ORIGIN`).
The collector, the CloudFormation and the workflow template carry no brand and no URL at all
(tests check), so a rename touches that one file.

## Parts

```
collector/   Python. `fleet collect --client <slug>` -> summary.json. Read-only AWS, guarded.
schema/      fleet-summary.schema.json: the only thing that leaves a client account.
fixtures/    summary.json: what the collector writes for a stubbed client; the board's tests POST it.
(board)      Lives in the Worker now: worker/src/fleet/, worker/migrations/0004_fleet.sql,
             worker/test/fleet/. See "Board" below.
infra/aws/   CloudFormation: the per-client read role (External ID) and the agency hub role.
templates/   The agency's GitHub Actions workflow (matrix over clients).
```

## How data flows

```
agency repo, GitHub Actions (hourly, one job per client)
  OIDC -> hub role (may only sts:AssumeRole on */role/fleet-read)
       -> AssumeRole(client read role, ExternalId = that client's secret)
       -> DescribeAlarms (ALARM) · ListCertificates + DescribeCertificate · GetCostAndUsage (1/day)
       -> summary.json (enums, counts, cents, days, a 16-hex account ref)
  POST /v1/fleet/summary  (agency key + X-Fleet-Client: <client slug>)
                                                    -> D1 fleet_* tables -> /fleet/<agency>
```

A client can instead run the same collector in its own Actions with its own client key,
OIDC straight into its read role, no hub and no External ID.

Install from PyPI: `pipx install dawnfix` (or `pip install dawnfix` in a venv). One package
holds every Dawnfix CLI (`dawnfix`, `logbill`, `parity`, `sweeper`, `leastpriv`, `receipt`,
`fleet`); `fleet --version` prints the release. For development in this folder:
`make install test` (an editable install of this tool and `../core`).

## Collector (`collector/`)

```sh
cd fleet/collector && make install && make test
fleet validate --config fleet.yml
fleet collect --client k3m9x2a7b4cd --config fleet.yml --out summary.json [--cache-dir .fleet-cache] [--no-spend]
fleet check summary.json
```

- `fleet.yml` (see `examples/fleet.yml`) is keyed by the client's **board slug**, which is
  random, so the file names no client. Per account: `provider: aws`, `env`
  (prod|staging|dev|shared|other), `account_id`, `regions`, optional `checks`, and either
  `role_arn` + `external_id_env` (cross-account; the External ID is required with a role and
  is read from that environment variable, never from the file) or neither (ambient creds,
  then `sts:GetCallerIdentity` must say the same account).
- **Read-only by construction** (`guard.py`): every boto client is dawnfix-core's
  `make_client` (`dawnfix_core.awsguard`, guard first on `provide-client-params` and
  `before-parameter-build`) with a per-service allowlist: `sts: AssumeRole, GetCallerIdentity ·
  cloudwatch: DescribeAlarms · ce: GetCostAndUsage · acm: ListCertificates,
  DescribeCertificate`; any other service is refused before a client is built. The collector
  depends on `dawnfix-core` (installed from `../../core` by `make install`).
- AssumeRole: `RoleSessionName=fleet-collect`, 15 minutes, and the assumed ARN's account must
  equal `account_id` or the account is `account_mismatch`.
- Credential status enum: `ok | denied | expired | throttled | account_mismatch | error`, from
  the AWS error **code** only (messages can echo ARNs). On anything but ok every check is
  `skipped`; one check failing (`denied | throttled | error`) does not stop the others.
- **Alarms**: `DescribeAlarms StateValue=ALARM` (metric + composite), every configured region,
  paginated. `firing`, and `stuck_24h` (in ALARM for more than a day).
- **Certificates**: `ListCertificates` (ISSUED + EXPIRED) then `DescribeCertificate` each, at
  most 200 per account (`truncated`). Only certificates **in use** count toward expiry:
  `expired`, `expiring_14d`, `expiring_30d`, `min_days_left`, and `manual_renewal_30d`
  (imported, or Amazon-issued but not renewal-eligible: the ones that actually lapse).
- **Spend**: Cost Explorer `GetCostAndUsage`, DAILY, UnblendedCost, credits and refunds
  excluded, one request covering 14 days → last 7 whole UTC days vs the 7 before, in cents.
  **$0.01 per request**: the answer is cached in `--cache-dir` per account per UTC day, so an
  hourly schedule costs ~$0.30/month per account, not ~$7.20. The workflow keeps the cache in
  `actions/cache` keyed by date. `--no-spend` or `checks:` without `spend` makes no call.
  Two currencies in one account is an error, not a sum.
- **Orphans**: always `{"status": "not_implemented", "count": null}` for now.
- **Account reference**: first 16 hex of sha256(client slug, provider, account id). Stable
  identity, not secrecy (AWS account ids are not secrets); the board never sees the id.
- The collector validates its own output (`summary.py`) before writing, against the same
  rules as the board. Exit 0 when written (credential failures are data), 2 bad
  config/arguments.
- GCP: the schema reserves `provider: gcp`; the collector refuses it in config for now.

## Summary schema (`schema/fleet-summary.schema.json`, `dawnfix.fleet/1`)

Top: `schema`, `generated_at`, `accounts[≤50]`. Each account: `account` (16 hex), `provider`,
`env`, `credential`, and four closed objects: `alarms {status, firing, stuck_24h}`, `spend
{status, cached, currency, as_of, this_week_cents, last_week_cents}`, `certs {status, total,
in_use, expired, expiring_14d, expiring_30d, manual_renewal_30d, min_days_left, truncated}`,
`orphans {status, count}`. No names, ARNs, ids, regions or free text. Two rules both
validators enforce beyond the JSON Schema: a check not `ok` has only nulls (and an `ok` one has
its numbers), and an account appears once. Python, TypeScript (`worker/src/fleet/validate.ts`) and the schema file are held
together by tests on both sides; `fixtures/summary.json` is regenerated with `make fixture`
and a test fails if it drifts.

## Board (merged into `worker/`)

The board was `fleet/board/` until 28 Oct 2026; it now lives in the Worker and `fleet/board/`
is gone. Sources: `worker/src/fleet/` (`routes`, `ingest`, `validate`, `data`, `assess`,
`pages`, `weekly`, `sample`, `render/{board,report,format,site}`), table definitions:
`worker/migrations/0004_fleet.sql`, tests: `worker/test/fleet/` (run with the Worker's suite:
`cd worker && npm test`).

| Method | Path | Auth | What |
|---|---|---|---|
| POST | `/v1/fleet/summary` | Bearer client key, or agency key + `X-Fleet-Client` (Enterprise) | One collection. 201 stored, 200 duplicate, 400/413/415, 401/403 key, **402 `plan_limit`** (`limit: fleet` without Enterprise; `limit: fleet_clients` for a client above the allowance, with the reason), 404 client not yours |
| PATCH | `/v1/fleet/client` | agency key + `X-Fleet-Client` | `{"weekly_email"?: bool, "auto_send_after_24h"?: bool}`, both off by default |
| PATCH | `/v1/fleet/agency` | agency key | `{"reply_to": email \| null}`: where client replies go |
| GET | `/fleet/:agency` | session, agency members only | The board |
| GET | `/fleet/:agency/report/:client` | session, agency or that client's members | The white-label weekly report as it stands, printable |
| GET/POST | `/fleet/:agency/report/:client/draft` | session, **agency members only** (a client's people get 404) | This week's frozen draft; Send to client / Hold this week / Release / auto-send on/off. POSTs are same-origin forms |
| GET | `/fleet`, `/fleet/sample` | public | What it is, how to get the board (Enterprise), the exact client IAM policy; a sample board from synthetic data |

- **Plans** (`worker/src/plans.ts`): the hosted board is Enterprise only. `limits.fleet` is
  `none` (Free) or `full` (Enterprise), and `limits.fleet_clients` caps how many clients one
  board holds (see `plans.ts`; write to us to raise it). A client counts once it has an
  account heard from in the last 30 days; one already counted is never refused.
- **Weekly report, agency first**: Mondays 07:00 UTC (`0 7 * * 1`) each opted-in client's
  report for the last 7 whole UTC days is drafted and **frozen** in `fleet_reports` (subject,
  text, HTML: the page shows exactly what will be sent), last week's unsent draft is
  superseded, and the agency's members get one email with a link per client to the draft page.
  Nothing goes to a client from the cron. "Send to client" is one conditional UPDATE
  (draft/held → sent), so double clicks, two members and a click racing the automatic send all
  send once; the row keeps who sent it (address or `auto`), when, the recipients (the client's
  members on the digest) and the reply-to. A hold stops only the automatic send. With
  `auto_send_after_24h` on, the hourly cron (`15 * * * *`) sends an un-held draft 24 h after it
  was drafted (never one older than 6 days). Client mail carries the agency's display name and
  `replyTo` = the agency's `reply_to`, else the member who pressed Send, else (auto) its first
  member. No brand and no link to our domain in anything a client sees (tests grep).
- **Board**: all clients on one screen, worst first (Act now / Look this week / OK / No data),
  each with its reasons in words, built from enums and numbers only, and each client's weekly
  report state. Thresholds in `assess.ts`: stale after 26 h, red cert ≤ 14 days needing manual
  renewal, amber ≤ 30, spend amber at +25% and +$50. Server-rendered with the Worker's page
  shell (light/dark, board CSS in `<head>`), no script; under 760 px each row becomes a card.
  The page shows env names only, never an account reference.
- Sign-in from a Fleet page returns to it (`/login?…&next=/fleet/…`, safe same-origin paths
  under `/s/` and `/fleet/` only). The agency's status page links to its board.

## CloudFormation (`infra/aws/`)

- `fleet-client-read-role.yaml`, deployed in each client account: trust either the agency hub
  role **with `sts:ExternalId`** (a rule refuses an agency trust without one; `NoEcho`,
  16–128 chars) or one GitHub repo's default branch via OIDC, or both. Policy:
  `cloudwatch:DescribeAlarms`, `acm:ListCertificates`, `acm:DescribeCertificate` (this
  account's certificates only), and `ce:GetCostAndUsage` behind `AllowCostExplorer`. A test
  checks the policy grants exactly the collector's allowlist.
- `fleet-agency-hub-role.yaml`, in the agency's account: GitHub OIDC for one repo/branch;
  may only `sts:AssumeRole` on `arn:aws:iam::*:role/<ClientRoleName>`.

## Merged

The merge plan that was here is done (28 Oct 2026): migration `0004_fleet.sql`; sources in
`worker/src/fleet/`, the re-export shim deleted and imports pointed at the Worker modules;
the fleet brand folded into `worker/src/brand.ts`; `fleetRoute` first in `worker/src/index.ts`,
`runFleetCron` in `worker/src/cron.ts`, `"0 7 * * 1"` and `"15 * * * *"` in `wrangler.jsonc`;
tests in `worker/test/fleet/` with the helpers in `worker/test/helpers.ts`. The Worker-side
wants (page() extra stylesheet, exported validate helpers, status page link, sign-in return,
`mail.ts` `replyTo`) are in. The collector uses dawnfix-core's `make_client`, and
`infra/aws/verify_readonly.py --profile fleet` checks a client role against
`CLIENT_ROLE_ACTIONS` (held equal by `infra/tests/test_verify_profile.py` here).
`fleet/infra/aws/fleet-client-read-policy.json` is the client policy rendered from the template
(for the hosted `/fleet` page); `FLEET_WRITE_POLICY=1` rewrites it and a test fails on drift.
Client onboarding: run `fleet/tools/fleet-client.sh`, or use it from your coding agent with
the steps in `prompts/fleet-setup.md`.
