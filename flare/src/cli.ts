#!/usr/bin/env node
// flare: read-only audit of Cloudflare accounts and Workers fleets.

import { existsSync, realpathSync } from 'node:fs';
import { appendFile, readFile, writeFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';
import { audit, collectSnapshot, failsAt } from './core/audit.js';
import { BRAND } from './core/brand.js';
import type { FetchLike } from './core/client.js';
import { ingestDoc } from './core/ingest.js';
import { renderHtml } from './core/report/html.js';
import { renderMarkdown } from './core/report/markdown.js';
import { renderText } from './core/report/text.js';
import { DEFAULT_OPTIONS, SEVERITIES, type Severity, type Snapshot } from './core/types.js';
import { loadConfig } from './node/config.js';
import { expandHome, scanRepos } from './node/scan.js';
import { loadState, saveState } from './node/state.js';

export const HELP = `${BRAND.fullName}: read-only audit of Cloudflare accounts and Workers.

Usage: ${BRAND.cli} [options] [--repos <dir>...]

Tokens are read from environment variables only (never from argv):
  CF_API_TOKEN or CLOUDFLARE_API_TOKEN by default, or every --token-env NAME given.

Options:
  --token-env NAME        Env var holding a token; repeat for several accounts/tokens
  --account ID            Only audit this account id (repeatable); default: all the token sees
  --repos DIR...          Scan wrangler.toml/json/jsonc under these dirs ("~/dev/*" works)
  --no-api                Local wrangler files only; no Cloudflare calls
  --config FILE           Config file (default ./flare.config.json if present)
  --public HOST           Hostname meant to be public (repeatable; "*.example.com" ok)
  --stale-days N          Dead-script threshold (default ${DEFAULT_OPTIONS.staleDays})
  --compat-months N       Old compatibility_date threshold (default ${DEFAULT_OPTIONS.compatMonths})
  --shallow               Skip per-script calls (faster; no workers.dev/bindings/secrets data)
  --json [FILE]           JSON to FILE, or to stdout instead of the table
  --html FILE             Write the self-contained HTML report
  --state FILE            Secret-name baseline (default ~/.${BRAND.cli}/state.json)
  --no-state              Do not read or write the baseline
  --snapshot-out FILE     Save the collected data (no secret values) for replay
  --snapshot-in FILE      Audit a saved snapshot instead of calling the API (as of its takenAt)
  --summary FILE          Append the findings as a Markdown table (CI job summary)
  --ingest-out FILE       Write the dawnfix.flare/1 counts document: counts per check and
                          severity and hashed account ids, no names (schema/flare-ingest.schema.json)
  --fail-on LEVEL         Exit 1 when a finding is at/above LEVEL: ${SEVERITIES.join('|')}|never (default high)
  --no-color              Plain table
  -h, --help              This help
`;

export interface Io {
  env: Record<string, string | undefined>;
  fetch: FetchLike;
  stdout: (s: string) => void;
  stderr: (s: string) => void;
  now: () => Date;
  isTTY: boolean;
  columns?: number;
  cwd: string;
}

export async function main(argv: string[], io: Io): Promise<number> {
  let parsed;
  try {
    parsed = parseArgs({
      args: argv,
      allowPositionals: true,
      options: {
        'token-env': { type: 'string', multiple: true },
        account: { type: 'string', multiple: true },
        repos: { type: 'string', multiple: true },
        'no-api': { type: 'boolean' },
        config: { type: 'string' },
        public: { type: 'string', multiple: true },
        'stale-days': { type: 'string' },
        'compat-months': { type: 'string' },
        shallow: { type: 'boolean' },
        json: { type: 'boolean' },
        html: { type: 'string' },
        state: { type: 'string' },
        'no-state': { type: 'boolean' },
        'snapshot-out': { type: 'string' },
        'snapshot-in': { type: 'string' },
        summary: { type: 'string' },
        'ingest-out': { type: 'string' },
        'fail-on': { type: 'string' },
        'no-color': { type: 'boolean' },
        help: { type: 'boolean', short: 'h' },
      },
    });
  } catch (e) {
    io.stderr(`${e instanceof Error ? e.message : String(e)}\n\n${HELP}`);
    return 2;
  }
  const v = parsed.values;
  if (v.help) {
    io.stdout(HELP);
    return 0;
  }
  // --json FILE: parseArgs has no optional values, so a .json positional right after is the file.
  let jsonFile: string | undefined;
  const positionals = [...parsed.positionals];
  if (v.json) {
    const at = argv.indexOf('--json');
    const next = argv[at + 1];
    if (next && !next.startsWith('-') && next.endsWith('.json') && positionals.includes(next)) {
      jsonFile = next;
      positionals.splice(positionals.indexOf(next), 1);
    }
  }

  try {
    const defaultConfig = join(io.cwd, 'flare.config.json');
    const cfgFile = v.config ? resolve(io.cwd, expandHome(v.config)) : existsSync(defaultConfig) ? defaultConfig : undefined;
    const cfg = await loadConfig(cfgFile, Boolean(v.config));
    const failOn = (v['fail-on'] ?? cfg.failOn ?? 'high') as Severity | 'never';
    if (failOn !== 'never' && !SEVERITIES.includes(failOn)) throw new Error(`--fail-on must be one of ${SEVERITIES.join(', ')}, never`);
    const num = (s: string | undefined, d: number, name: string) => {
      if (s === undefined) return d;
      const n = Number(s);
      if (!Number.isFinite(n) || n <= 0) throw new Error(`${name} must be a positive number`);
      return n;
    };
    let now = io.now();
    const repos = [...(v.repos ?? []), ...positionals, ...(v.repos || positionals.length ? [] : (cfg.repos ?? []))];

    let snapshot: Snapshot;
    if (v['snapshot-in']) {
      snapshot = JSON.parse(await readFile(resolve(io.cwd, v['snapshot-in']), 'utf8')) as Snapshot;
      // A replay is audited as of the moment it was taken, so ages (and the output) do not drift.
      const taken = new Date(snapshot.takenAt);
      if (!Number.isNaN(taken.getTime())) now = taken;
    } else {
      const local = repos.length ? await scanRepos(repos, cfg.authMarkers ? { markers: cfg.authMarkers } : {}) : { workers: [], gaps: [], files: [] };
      const tokenEnv = v['token-env'] ?? cfg.tokenEnv ?? ['CF_API_TOKEN', 'CLOUDFLARE_API_TOKEN'];
      const tokens = v['no-api'] ? [] : [...new Set(tokenEnv.map((n) => io.env[n]).filter((t): t is string => Boolean(t)))];
      if (!v['no-api'] && tokens.length === 0) {
        if (!repos.length) throw new Error(`no token: set ${tokenEnv.join(' or ')}, or pass --no-api with --repos`);
        io.stderr(`No token in ${tokenEnv.join('/')}; auditing local files only.\n`);
      }
      const accountIds = v.account ?? cfg.accounts;
      const collected = await collectSnapshot({
        tokens,
        fetch: io.fetch,
        local: local.workers,
        collect: { ...(accountIds?.length ? { accountIds } : {}), ...(v.shallow ? { shallow: true } : {}) },
        now,
      });
      snapshot = collected.snapshot;
      snapshot.localGaps.push(...local.gaps);
    }
    if (v['snapshot-out']) await writeFile(resolve(io.cwd, v['snapshot-out']), JSON.stringify(snapshot, null, 2) + '\n', { mode: 0o600 });

    const stateFile = resolve(io.cwd, expandHome(v.state ?? join(homedir(), `.${BRAND.cli}`, 'state.json')));
    const useState = !v['no-state'] && !v['snapshot-in'];
    const prev = useState ? await loadState(stateFile) : undefined;
    const { result, secretsBaseline } = audit(snapshot, {
      publicHostnames: [...(cfg.publicHostnames ?? []), ...(v.public ?? [])],
      appAuthScripts: cfg.appAuthScripts ?? [],
      staleDays: num(v['stale-days'], cfg.staleDays ?? DEFAULT_OPTIONS.staleDays, '--stale-days'),
      compatMonths: num(v['compat-months'], cfg.compatMonths ?? DEFAULT_OPTIONS.compatMonths, '--compat-months'),
      ...(prev ? { secretsBaseline: prev.secrets } : {}),
      now,
    });
    if (useState && Object.keys(secretsBaseline).length) await saveState(stateFile, secretsBaseline, now);

    if (v.html) {
      await writeFile(resolve(io.cwd, v.html), renderHtml(result));
      io.stderr(`HTML report: ${resolve(io.cwd, v.html)}\n`);
    }
    if (v.summary) await appendFile(resolve(io.cwd, v.summary), renderMarkdown(result));
    if (v['ingest-out']) await writeFile(resolve(io.cwd, v['ingest-out']), JSON.stringify(await ingestDoc(result), null, 2) + '\n');
    const json = JSON.stringify({ ...result, pitch: BRAND.pitch }, null, 2) + '\n';
    if (v.json && jsonFile) await writeFile(resolve(io.cwd, jsonFile), json);
    if (v.json && !jsonFile) io.stdout(json);
    else io.stdout(renderText(result, { color: io.isTTY && !v['no-color'] && !io.env.NO_COLOR, ...(io.columns ? { width: io.columns } : {}) }));
    return failsAt(result, failOn) ? 1 : 0;
  } catch (e) {
    io.stderr(`${BRAND.cli}: ${e instanceof Error ? e.message : String(e)}\n`);
    return 2;
  }
}

const invoked = process.argv[1] && existsSync(process.argv[1]) ? pathToFileURL(realpathSync(process.argv[1])).href : '';
if (import.meta.url === invoked) {
  main(process.argv.slice(2), {
    env: process.env,
    fetch: globalThis.fetch as unknown as FetchLike,
    stdout: (s) => process.stdout.write(s),
    stderr: (s) => process.stderr.write(s),
    now: () => new Date(),
    isTTY: Boolean(process.stdout.isTTY),
    ...(process.stdout.columns ? { columns: process.stdout.columns } : {}),
    cwd: process.cwd(),
  }).then((code) => process.exit(code));
}
