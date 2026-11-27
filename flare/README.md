# Dawnfix Flare

Read-only audit of one or more Cloudflare accounts and the Workers in them, plus the
`wrangler.toml` / `wrangler.json(c)` files in your repos. It answers: which Workers are
reachable around their custom domain, which hostnames have no sign-in in front, which
Workers share a rate-limit counter, what DNS and routes point at nothing, what is dead or
old, which tokens could do too much, and which zones still accept weak TLS.

Free. Source available under FSL-1.1-ALv2 (see [LICENSE](../LICENSE) at the repo root).
Run it once from your machine, or every day in your own GitHub Actions with the free
workflow (see "Daily audit in CI" below). Only the email the day new exposure appears is
Dawnfix Enterprise, our hosted service. The product name, org
and URLs it prints are kept in one file:
[`src/core/brand.ts`](src/core/brand.ts).

From npm, with nothing to clone: `npx dawnfix flare --help` (the npm package `dawnfix`
bundles this CLI; `npx dawnfix flare ...` takes every option below).

`dist/cli.js` is the whole tool in one file (esbuild bundle of `src/`, no runtime
dependencies), checked in so it runs with plain `node` 20 or newer, no install:

```sh
read -rs CF_API_TOKEN && export CF_API_TOKEN # read-only token, see below; nothing echoed
node dist/cli.js --repos ~/dev/*             # table, exit 1 on any high finding
node dist/cli.js --json report.json --html report.html
node dist/cli.js --no-api --repos ~/dev/*    # wrangler files only, no API calls
node dist/cli.js --token-env CF_A --token-env CF_B   # several tokens / accounts
```

Use it from your coding agent: `prompts/flare.md` at the repo root is a copy-paste prompt
that runs this bundle, asks you to set the token in your own terminal (never in the chat),
writes the HTML report and explains the top findings.

Development:

```sh
npm ci
npm test && npm run typecheck   # vitest (no test reaches the network) and tsc
npm run build                   # writes dist/cli.js; commit it
npm run build:check             # exit 1 if dist/cli.js is stale (a test checks the same)
npm run sample                  # regenerate examples/demo-ingest.json after an output change
```

## Token

Create a **custom API token** with read permissions only. The tool also refuses any
non-GET request in code (`src/core/client.ts`), so a token with more scope still cannot
change anything, but do not give it more.

| Permission (dashboard name) | Level | Used for |
|---|---|---|
| Account > Workers Scripts | Read | scripts, workers.dev / preview flags, bindings, secret **names**, deployments, cron schedules, custom domains, account workers.dev subdomain |
| Account > Access: Apps and Policies | Read | which hostnames and workers.dev URLs Access protects |
| Account > Account Settings | Read | account list and names |
| Account > Account API Tokens | Read | account-owned tokens and their permission group names (optional) |
| User > API Tokens | Read | user-owned tokens (optional; only on a user-owned token) |
| Zone > Zone | Read | zone list |
| Zone > Workers Routes | Read | zone Workers routes |
| Zone > DNS | Read | DNS records |
| Zone > Zone Settings | Read | min TLS, Always Use HTTPS, HSTS |

Resources: the accounts and zones you want audited. A missing permission does not stop
the run: the part it covers is listed under "Not checked" with the HTTP status, and the
checks that need it stay quiet (or say "unverified") rather than guess.

Tokens are only read from environment variables (`CF_API_TOKEN`, `CLOUDFLARE_API_TOKEN`,
or the names given with `--token-env` / `tokenEnv`), never from argv or the config file.

## Checks

| Check | Severity | Source | What it finds |
|---|---|---|---|
| `workers-dev-enabled` | high with a custom domain, medium if workers.dev is its only address, low without a fetch handler or behind Access; local: medium if the next deploy turns it on (low for a cron-only Worker), info if not set explicitly | API, wrangler | `<script>.<sub>.workers.dev` answers, outside the zone's WAF, rate-limit rules and Access. Locally follows wrangler's default: absent means on when there are no routes. |
| `preview-urls-enabled` | medium (low behind Access); local low/info | API, wrangler | Per-version preview hostnames on workers.dev. |
| `hostname-without-auth` | medium; low if Access covers only a path or Access was unreadable; info for local-only Workers | API (+ repo) | Custom domain or route with no Access app covering the host and no app sign-in marker in the repo. Silence with `publicHostnames` (wildcards) or `appAuthScripts`. Markers: Access JWT header, passkey/WebAuthn, `/login`-style routes, email allowlists, basic auth; configurable as `authMarkers`. |
| `ratelimit-namespace-shared` | high across Workers, medium for two bindings in one Worker | API bindings + wrangler (`ratelimits` and `unsafe.bindings`) | A `namespace_id` named more than once in an account. Suggests the next free hundred-block. Each `[env.x]` counts as its own Worker. |
| `route-to-missing-script` | high | API | Zone route or Workers custom domain whose script no longer exists. |
| `dangling-dns` | high / medium | API | CNAME to `<script>.<sub>.workers.dev` for a missing or workers.dev-disabled script (high), to another account's workers.dev subdomain, to a name in a sibling zone that has no record, and `192.0.2.x` / `100::` placeholder records no Workers route serves any more. |
| `dead-script` | low; medium when both | API | No route, custom domain, workers.dev, cron, queue/email handler or inbound service binding; or last deployment older than `staleDays` (180). |
| `compat-date-old` | low past `compatMonths` (12), medium past twice that | API, wrangler | Old `compatibility_date`. |
| `secrets-changed` | medium if a name was removed, low if only added | API | Secret **names** compared with the previous run (`~/.flare/state.json`, names only). The API can return secret text; the collector drops it before it reaches any data structure, and a test checks it never appears in snapshot, state or output. |
| `token-over-scoped` | high for write on all accounts/zones, medium for 8+ write groups | API | |
| `token-no-expiry` | medium with write access, else low | API | |
| `token-unused` | low | API | Not used for 90 days. |
| `zone-tls` | medium for min TLS < 1.2 or Always Use HTTPS off; low for HSTS off or max-age < 180 days | API | Active zones only. |

## Output

- Terminal table with a fix line per finding (colour on a TTY, off with `--no-color` / `NO_COLOR`).
- `--json [file]`: `{ generatedAt, findings[], gaps[], summary, accounts[], localFiles }`.
- `--html file`: one self-contained file, no external assets, light/dark from the system,
  cards stack on a phone, severity filter chips.
- `--summary FILE`: append the findings as a Markdown table (a CI job summary).
- `--ingest-out FILE`: the `dawnfix.flare/1` counts document for the hosted service
  ([`schema/flare-ingest.schema.json`](schema/flare-ingest.schema.json)): counts per check
  id and severity, the number of accounts, a salted 16-hex SHA-256 per account id, the
  number of wrangler files and unread parts. No hostname, script, zone, token, secret or
  account name; a test feeds it every name in the fixture and demo snapshots and finds none.
- `--snapshot-out` / `--snapshot-in`: save what was collected and re-audit it offline, as of
  the snapshot's `takenAt` (so a replay does not drift).
  [`examples/demo-snapshot.json`](examples/demo-snapshot.json) is the demo account (the
  site's `/flare/sample` is its report):
  `node dist/cli.js --snapshot-in examples/demo-snapshot.json --html demo.html`.
- `--json` output carries `pitch: {line, url}` (from `src/core/brand.ts`): one line about
  the free daily workflow.
- Exit code: 1 when a finding is at or above `--fail-on` (default `high`), 2 on usage error.

## Config

`flare.config.json` in the working directory, or `--config`. See
[`flare.config.example.json`](flare.config.example.json). Unknown keys are an error.

## Cloudflare API endpoints used (all GET, `https://api.cloudflare.com/client/v4`)

| Endpoint | Notes |
|---|---|
| `/accounts` · `/accounts/{account_id}` | account list (paged, 50) or the named ones |
| `/accounts/{account_id}/workers/subdomain` | the account's workers.dev subdomain |
| `/accounts/{account_id}/workers/scripts` | scripts with `handlers`, `compatibility_date`, `modified_on`, `routes` |
| `/accounts/{account_id}/workers/scripts/{script_name}/subdomain` | `enabled`, `previews_enabled` |
| `/accounts/{account_id}/workers/scripts/{script_name}/settings` | bindings (`ratelimit.namespace_id`, `service`) |
| `/accounts/{account_id}/workers/scripts/{script_name}/secrets` | names kept, text dropped |
| `/accounts/{account_id}/workers/scripts/{script_name}/deployments` | first entry is the live deployment |
| `/accounts/{account_id}/workers/scripts/{script_name}/schedules` | only for scripts with a `scheduled` handler |
| `/accounts/{account_id}/workers/domains` | Workers custom domains |
| `/zones?account.id=` | paged, 50 |
| `/zones/{zone_id}/workers/routes` | |
| `/zones/{zone_id}/dns_records` | paged, 1000 |
| `/zones/{zone_id}/settings/min_tls_version` · `always_use_https` · `security_header` | |
| `/accounts/{account_id}/access/apps` | `domain`, `self_hosted_domains`, `destinations[type=public].uri`; `destinations[type=worker]` and `[type=all_workers]` (field names unverified, see below) |
| `/accounts/{account_id}/tokens` · `/user/tokens` | policies (permission group ids and names), `expires_on`, `last_used_on`, IP condition |
| `/accounts/{account_id}/tokens/permission_groups` · `/user/tokens/permission_groups` | only when a token lists a group by id without a name: id -> name |

Up to 4 requests at a time; 429 and 5xx retried with `Retry-After` / backoff. Requests
per account: about 8 + 5 per script + 5 per zone.

## Daily audit in CI (free)

The reusable workflow `dawnfix/dawnfix/.github/workflows/flare.yml@v0` (the caller is in its
header; the copy-it-yourself form is `templates/github/workflows/dawnfix-flare.yml`; or give
`prompts/flare-ci.md` to your coding agent) runs `node flare/dist/cli.js` from the public
repo at its release tag every day at 05:17 UTC in the customer's GitHub Actions, with their read-only
token as the GitHub secret `FLARE_CLOUDFLARE_API_TOKEN` (`_2` .. `_5` for more accounts):
`--summary "$GITHUB_STEP_SUMMARY"` (names stay in GitHub), `--state` in the Actions cache
instead of `~/.flare/state.json`, and `--ingest-out` for the counts document. No key is
needed, and without one nothing leaves the runner. With
the optional Dawnfix Enterprise key (`DAWNFIX_ENTERPRISE_KEY`) the workflow also POSTs that counts
document to `/v1/flare`, and a rising critical/high/medium count against the previous run
emails the workspace the same day. The hosted service never sees a Cloudflare token.

## Severity adjustments

- workers.dev / preview URLs behind Access: an Access app on `<script>.<sub>.workers.dev`,
  on `*.<sub>.workers.dev`, or a `worker` / `all_workers` destination makes the finding low.
- Cron-only Workers: a local Worker whose source shows a `scheduled` handler (or whose config
  has `triggers.crons`), no `fetch` handler definition and no opaque default export
  (`export default app`) gets low instead of medium for a workers.dev that defaults on. A
  call to `fetch(...)` is not a handler. Deployed scripts use the API's `handlers` list.
- Token groups listed by id only are resolved to names before the write/read test.

## Layout

- `src/core/`: runtime-neutral (fetch and WebCrypto only; `tsconfig.core.json` compiles it
  with no Node types). Client, collector, checks, text, HTML and Markdown reports, the
  ingest document, the token permission list. The Dawnfix Worker imports it to render
  `/flare/sample` and the token list on `/flare`.
- `src/node/`: repo scanning, config file, secret-name baseline file.
- `src/cli.ts`: argument parsing and wiring.
- `build.mjs`: the esbuild bundle and its staleness check; `dist/cli.js`: its output.
- `schema/flare-ingest.schema.json`: the counts document the CI workflow sends with an Enterprise key.
- `examples/demo-snapshot.json`, `examples/demo-ingest.json`: the demo account and what it sends.
- `examples/worker-cron.ts`: the same audit on a Worker cron in your own account, with KV for
  the baseline (sketch, not deployed; Dawnfix's own service never holds a token).
- `test/`: vitest. `test/fixtures/cloudflare.ts` is a fake Cloudflare API with one
  planted problem per check and a clean neighbour for each; `test/fixtures/repos/` are
  wrangler files, `test/fixtures/repos-extra/` the cron-only / framework cases.
  `test/release.test.ts`: the bundle is fresh and runs with plain node, the ingest document
  has no names and matches the schema, the README token table is `TOKEN_PERMISSIONS`.
  `test/setup.ts` replaces the global fetch so no test can reach the network.
