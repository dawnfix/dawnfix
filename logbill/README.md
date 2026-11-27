# Dawnfix Logbill

A free, one-shot, read-only X-ray of your CloudWatch Logs bill. It runs on your
machine with your own AWS credentials and writes one HTML file: what each log
group costs per month, which log lines cost the most, and what to change, with
a dollar figure on every suggestion.

Free. Source available under FSL-1.1-ALv2 (see [LICENSE](../LICENSE) at the repo root).
The report ends with one line about the free Dawnfix workflow
(`templates/github/workflows/dawnfix.yml`), which watches the same logs for new
errors; its text and link are in `src/logbill/brand.py`, as are every product
name, org and URL; renaming is a change to that one file (plus these docs).

## Where it ships

- As a CLI: `logbill scan` (see "Install and run" below).
- Use it from your coding agent: `prompts/logbill.md` at the repo root is a
  copy-paste prompt that installs and runs the CLI and summarises the report.
- In the public repo (`tools/cut-public-repo.sh` copies this directory whole,
  tests and sample included).
- Explained on the hosted page `/logbill` of the Dawnfix site, which renders
  `iam/logbill-readonly-policy.json`, `prices.json` and `sample/sample.json` at
  build time and serves `sample/report.html` at `/logbill/sample`.
- On PyPI, in the package `dawnfix` (every Dawnfix CLI, one version), since v0.3.0.

Install from PyPI: `pipx install dawnfix` (or `pip install dawnfix` in a venv). One package
holds every Dawnfix CLI (`dawnfix`, `logbill`, `parity`, `sweeper`, `leastpriv`, `receipt`,
`fleet`); `logbill --version` prints the release. For development in this folder:
`make install test` (an editable install of this tool and `../core`).

## Install and run

```sh
cd logbill
make install          # uv venv + editable install of ../core and logbill
make test

.venv/bin/logbill scan --profile prod --regions us-east-1,eu-central-1 --days 30 \
  --out report.html --insights-budget-gb 5
```

| Command | What it does |
|---|---|
| `logbill scan [--profile P] [--regions r1,r2\|all] [--days 30] [--out report.html] [--json PATH\|-] [--insights-budget-gb 5] [--insights-hours 24] [--top 10] [--retention-days 30] [--yes]` | Scan, price, suggest; writes the HTML and a JSON next to it (`--json -` prints the JSON instead) |
| `logbill locate --repo PATH [--report report.json] [--top 10] [--json]` | Maps the report's costliest patterns to `file:line` candidates (ripgrep, or grep if rg is missing) |
| `logbill fix --retention-days 30 [--report report.json \| --profile P --regions R] [--group NAME]... [--apply]` | Prints `aws logs put-retention-policy` for every group that never expires. `--apply` makes the change after you type `apply <n>` on a terminal; it is the only write logbill can make |

Exit codes: 0 ok; 1 no credentials, every region failed, or `--apply` not
confirmed; 2 bad arguments. AWS errors are reported as codes only.

## What it reads

Per region:

1. `DescribeLogGroups`: stored bytes, retention (never-expire is flagged), log
   class (Standard / Infrequent Access / Delivery), metric filter count, creation time.
2. `GetMetricData`: `AWS/Logs IncomingBytes` and `IncomingLogEvents` per
   `LogGroupName`, daily sums over `--days`, projected to 30 days.
3. For the `--top` costliest groups only: `DescribeSubscriptionFilters` and
   `DescribeQueries` (recent Insights queries, to tell rarely-queried groups).
4. Optional, for the same top groups: one Logs Insights query each,
   `pattern @message | sort @sampleCount desc | limit 25`, over the last
   `--insights-hours` (shrunk to fit the budget).

Every boto client has an allowlist and refuses any other operation before the
request is built (the same guard as `dawnfix-core`). The scan clients allow
the Describe/Get calls above; the Insights client, built only after the budget
check and your yes, adds `StartQuery`, `GetQueryResults`, `StopQuery`; the
`fix --apply` client allows `PutRetentionPolicy` and nothing else.

## What running it costs

Metadata calls are free. `GetMetricData` costs $0.01 per 1,000 metrics
requested: two metrics per log group, so 500 groups is about $0.01.

Logs Insights is billed per GB scanned: $0.005/GB in us-east-1, $0.0063/GB in
eu-central-1, up to $0.009/GB in sa-east-1 (`prices.json`). The first 5 GB a
month are in the AWS free tier. logbill:

- estimates each query's scan as the group's bytes per hour (the higher of the
  window mean and the newest day) times the window, and shrinks the window, or
  skips the group, so the plan never exceeds `--insights-budget-gb`
  (default 5 GB, so at most about $0.03-0.05);
- prints the estimate and asks before the first query (`--yes` skips the
  question; with no terminal and no `--yes` it skips Insights);
- reads `bytesScanned` from each finished query and starts no further query
  once the real total would pass the budget. A single query can scan more than
  estimated; that overshoot is bounded by one query's window;
- stops a query that runs over 5 minutes (`StopQuery`).

`--insights-budget-gb 0` turns Insights off: groups, retention and Infrequent
Access are still priced; per-line costs are not.

## How the numbers are made

- Prices: `prices.json`, from the AWS Price List bulk API (offer
  `AmazonCloudWatch`, published 2026-10-07, read 2026-10-27), checked against the
  worked examples on aws.amazon.com/cloudwatch/pricing. 17 regions; any other
  region uses us-east-1 prices and is marked approximate. The `uncertain` list in
  the file says what is guessed.
- Ingestion: GB/month x the class rate. Lambda and `/aws/vendedlogs/` groups use
  the vended tiers on the region's vended total (the same price as Standard
  below 10 TB/month).
- Storage: `storedBytes` x GB-month rate.
- Per line: `pattern` returns counts per pattern, not bytes. A pattern's share
  of the group's bytes is its event share weighted by its length (tokens counted
  as 8 characters), applied to the group's monthly ingestion cost.
- Suggestions: retention at 30 and 90 days (and `--retention-days`) on
  never-expiring groups, assuming stored bytes built up evenly over the group's
  age; Infrequent Access for Standard groups with no metric or subscription
  filters and at most 2 recent Insights queries; drop or sample lines with >= 5%
  of a group's bytes or >= $1/month; Lambda START/END/REPORT lines (JSON log
  format with system log level WARN); Container Insights performance groups;
  DEBUG/TRACE lines in groups whose name does not say dev/test/staging.
- The headline saving counts each dollar once: per group, retention + dropped
  lines + Infrequent Access on what is left, capped at the group's cost.

## IAM

- `iam/logbill-readonly-policy.json`: the scan. Describe* and `GetMetricData`,
  plus the Logs Insights statement (`StartQuery`, `GetQueryResults`,
  `StopQuery`), which you can delete to forbid pattern analysis. Separate from
  the Dawnfix read role in `infra/`; ReadOnlyAccess also covers it.
- `iam/logbill-apply-retention-policy.json`: only for `fix --apply`:
  `logs:PutRetentionPolicy`. Not needed to print the commands.

`sts:GetCallerIdentity` (for the account id in the report) needs no permission.

## Privacy

- Runs locally. Nothing is uploaded; there is no telemetry. The report has no
  external assets or links, so opening it makes no network request.
- Log lines never leave AWS except as Insights `pattern` results, which go
  through the `dawnfix-core` redactor (emails including `%40`, phones, long
  ids, UUIDs, JWTs, bearer tokens, URL userinfo, query strings; printable ASCII
  only) before they are printed or saved. Log group names are kept as they are.
- The report and JSON contain your account id, log group names and redacted
  patterns: treat them as internal.

## Sample report

`sample/make_sample.py` runs a scan against the test scenario (`tests/scenario.py`:
three made-up log groups in the AWS documentation account id `123456789012`, all
calls answered by botocore's Stubber) and `locate` against `tests/fixtures/repo`,
then writes `sample/report.html` and `sample/sample.json` (the report, the locate
result and the HTML). It refuses output with a script, a link, a URL, an email or
any other 12-digit id. `tests/test_sample.py` fails when they are stale:

```sh
.venv/bin/python sample/make_sample.py      # after any change to the report
```

## Layout

```
prices.json             price table (source, date, uncertain items)
iam/                    read-only scan policy; the retention-apply policy
src/logbill/
  brand.py              product name, org, URLs (the one file to rename)
  cli.py                scan | locate | fix
  scan.py               one scan end to end
  awsread.py            allowlisted clients and the read calls
  model.py              log groups and their monthly cost
  insights.py           budget plan, pattern queries, pattern parsing
  suggest.py            savings suggestions and the combined total
  locate.py             pattern -> file:line
  report.py             HTML and JSON
  fix.py                retention commands and the guarded apply
sample/                 make_sample.py, the generated report.html and sample.json
tests/                  pytest, botocore Stubber, no live AWS
```
