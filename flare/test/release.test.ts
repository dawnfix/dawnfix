// What ships: the checked-in bundle matches the sources, runs with plain node, and the
// dawnfix.flare/1 document it writes for CI carries counts only, never a name.

import { execFileSync } from 'node:child_process';
import { mkdtemp, readFile } from 'node:fs/promises';
import { readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { bundle, OUT, ROOT } from '../build.mjs';
import { audit } from '../src/core/audit.js';
import { BRAND } from '../src/core/brand.js';
import { hashAccountId, ingestDoc, INGEST_SCHEMA, MAX_INGEST_ACCOUNTS } from '../src/core/ingest.js';
import { TOKEN_PERMISSIONS, permissionLine } from '../src/core/permissions.js';
import { mdCell, renderMarkdown } from '../src/core/report/markdown.js';
import { CHECK_IDS, DEFAULT_OPTIONS, SEVERITIES, type Snapshot } from '../src/core/types.js';
import { main, type Io } from '../src/cli.js';
import { fakeCloudflare, NOW } from './fixtures/cloudflare.js';
import { apiSnapshot, REPOS, run } from './helpers.js';
import { scanRepos } from '../src/node/scan.js';

const SCHEMA = JSON.parse(readFileSync(join(ROOT, 'schema', 'flare-ingest.schema.json'), 'utf8'));
const DEMO = join(ROOT, 'examples', 'demo-snapshot.json');
const demo = (): Snapshot => JSON.parse(readFileSync(DEMO, 'utf8'));

/** Every name a snapshot holds: what must never reach the hosted service. */
function namesIn(s: Snapshot): string[] {
  const out = new Set<string>();
  const add = (v: unknown) => typeof v === 'string' && v.length > 0 && out.add(v);
  for (const a of s.accounts) {
    add(a.id);
    add(a.name);
    add(a.workersSubdomain);
    for (const sc of a.scripts ?? []) {
      add(sc.name);
      sc.routes.forEach(add);
      sc.secretNames?.forEach(add);
      sc.crons?.forEach(add);
      for (const b of sc.bindings ?? []) [b.name, b.namespaceId, b.service].forEach(add);
    }
    for (const d of a.customDomains ?? []) [d.hostname, d.service, d.zoneId, d.zoneName].forEach(add);
    for (const z of a.zones ?? []) {
      [z.id, z.name].forEach(add);
      for (const r of z.routes ?? []) [r.id, r.pattern, r.script].forEach(add);
      for (const r of z.dns ?? []) [r.id, r.name, r.content].forEach(add);
    }
    for (const app of a.accessApps ?? []) [app.id, app.name, ...app.domains].forEach(add);
    for (const t of a.tokens ?? []) [t.id, t.name].forEach(add);
  }
  for (const w of s.local) {
    [w.name, w.file, w.env].forEach(add);
    w.routes.forEach((r) => add(r.pattern));
    w.ratelimitNamespaces.forEach((r) => [r.binding, r.namespaceId].forEach(add));
  }
  return [...out];
}

/** A substring check for real names; short ones as whole JSON strings (a count "3" is not a name). */
function leaks(doc: unknown, names: string[]): string[] {
  const text = JSON.stringify(doc);
  return names.filter((n) => (n.length >= 4 ? text.includes(n) : text.includes(JSON.stringify(n))));
}

/** The schema, applied by hand: flare has no runtime dependencies, so no JSON Schema library. */
function conforms(doc: Record<string, unknown>): void {
  const count = (v: unknown) => expect(Number.isSafeInteger(v) && (v as number) >= 0 && (v as number) <= SCHEMA.$defs.count.maximum).toBe(true);
  const sev = (o: unknown) => {
    expect(Object.keys(o as object).sort()).toEqual([...SCHEMA.$defs.severities.required].sort());
    Object.values(o as object).forEach(count);
  };
  expect(Object.keys(doc).sort()).toEqual([...SCHEMA.required].sort());
  expect(doc.schema).toBe(SCHEMA.properties.schema.const);
  expect(doc.generated_at).toMatch(new RegExp(SCHEMA.properties.generated_at.pattern));
  count(doc.accounts);
  count(doc.local_files);
  count(doc.gaps);
  for (const id of doc.account_ids as string[]) expect(id).toMatch(new RegExp(SCHEMA.properties.account_ids.items.pattern));
  sev(doc.summary);
  expect(Object.keys(doc.findings as object)).toEqual(SCHEMA.properties.findings.required);
  Object.values(doc.findings as object).forEach(sev);
}

describe('dist/cli.js', () => {
  it('is what the sources build to (run `npm run build` after changing src/)', async () => {
    expect(readFileSync(OUT, 'utf8') === (await bundle()), 'dist/cli.js is stale: npm run build').toBe(true);
  });

  it('runs with plain node and no node_modules: --help, and a replayed snapshot', async () => {
    const help = execFileSync(process.execPath, [OUT, '--help'], { encoding: 'utf8', cwd: tmpdir(), env: { PATH: '' } });
    expect(help).toContain(`${BRAND.fullName}: read-only audit`);
    expect(help).toContain('--ingest-out FILE');
    const dir = await mkdtemp(join(tmpdir(), 'flare-dist-'));
    execFileSync(process.execPath, [OUT, '--snapshot-in', DEMO, '--ingest-out', join(dir, 'i.json'), '--fail-on', 'never'], { encoding: 'utf8', cwd: dir, env: { PATH: '' } });
    expect(JSON.parse(await readFile(join(dir, 'i.json'), 'utf8'))).toEqual(JSON.parse(readFileSync(join(ROOT, 'examples', 'demo-ingest.json'), 'utf8')));
  });

  it('imports nothing outside node: built-ins', () => {
    const text = readFileSync(OUT, 'utf8');
    const imports = [...text.matchAll(/^import .* from ["']([^"']+)["'];?$/gm)].map((m) => m[1]);
    expect(imports.length).toBeGreaterThan(0);
    for (const i of imports) expect(i).toMatch(/^node:/);
    expect(text).not.toMatch(/require\(["'](?!node:)/);
    expect(text).not.toContain(resolve(ROOT, '..'));
  });
});

describe('the ingest document (dawnfix.flare/1)', () => {
  it('lists the same checks and severities as the schema, and closes every object', () => {
    expect(SCHEMA.properties.findings.required).toEqual([...CHECK_IDS]);
    expect(SCHEMA.$defs.severities.required).toEqual([...SEVERITIES]);
    expect(SCHEMA.properties.schema.const).toBe(INGEST_SCHEMA);
    expect(SCHEMA.properties.account_ids.maxItems).toBe(MAX_INGEST_ACCOUNTS);
    for (const o of [SCHEMA, SCHEMA.properties.findings, SCHEMA.$defs.severities]) expect(o.additionalProperties).toBe(false);
  });

  it('counts every finding once, by check and severity', async () => {
    const { result } = run(await apiSnapshot());
    const doc = await ingestDoc(result);
    conforms(doc as unknown as Record<string, unknown>);
    const total = Object.values(doc.findings).reduce((n, s) => n + Object.values(s).reduce((a, b) => a + b, 0), 0);
    expect(total).toBe(result.findings.length);
    expect(doc.summary).toEqual(result.summary);
    expect(doc.findings['workers-dev-enabled'].high).toBe(1);
    expect(doc.accounts).toBe(1);
    expect(doc.account_ids).toEqual([await hashAccountId(result.accounts[0]!.id)]);
  });

  it('never contains a name from the snapshot: fixture account with repos, and the demo', async () => {
    const local = (await scanRepos([`${REPOS}/*`], { base: REPOS })).workers;
    for (const snap of [await apiSnapshot({}, local), demo()]) {
      const names = namesIn(snap);
      expect(names.length).toBeGreaterThan(40);
      const { result } = audit(snap, { ...DEFAULT_OPTIONS, now: new Date(snap.takenAt) });
      // the result itself is full of them; the document has none
      expect(leaks(result, names).length).toBeGreaterThan(20);
      expect(leaks(await ingestDoc(result), names)).toEqual([]);
    }
  });

  it('hashes account ids with a salt, to 16 hex, stable', async () => {
    const h = await hashAccountId('0123456789abcdef0123456789abcdef');
    expect(h).toMatch(/^[0-9a-f]{16}$/);
    expect(h).toBe(await hashAccountId('0123456789abcdef0123456789abcdef'));
    const { createHash } = await import('node:crypto');
    expect(h).not.toBe(createHash('sha256').update('0123456789abcdef0123456789abcdef').digest('hex').slice(0, 16));
  });

  it('refuses more accounts than the schema allows', async () => {
    const { result } = run(await apiSnapshot());
    const many = { ...result, accounts: Array.from({ length: MAX_INGEST_ACCOUNTS + 1 }, (_, i) => ({ id: `a${i}`, name: `n${i}`, scripts: 0, zones: 0 })) };
    await expect(ingestDoc(many)).rejects.toThrow(/at most 100/);
  });

  it('examples/demo-ingest.json is what the demo snapshot produces', async () => {
    const snap = demo();
    const { result } = audit(snap, { ...DEFAULT_OPTIONS, now: new Date(snap.takenAt) });
    expect(JSON.parse(readFileSync(join(ROOT, 'examples', 'demo-ingest.json'), 'utf8'))).toEqual(await ingestDoc(result));
  });
});

describe('cli: --summary, --ingest-out, pitch, replay clock', () => {
  let out = '';
  let err = '';
  const io = (dir: string, env: Record<string, string> = { CF_API_TOKEN: 'test-token' }): Io => ({
    env,
    fetch: fakeCloudflare().fetch,
    stdout: (s) => void (out += s),
    stderr: (s) => void (err += s),
    now: () => NOW,
    isTTY: false,
    cwd: dir,
  });

  it('appends a Markdown table to --summary and writes --ingest-out', async () => {
    const dir = await mkdtemp(join(tmpdir(), 'flare-ci-'));
    const { writeFile } = await import('node:fs/promises');
    await writeFile(join(dir, 'summary.md'), '# earlier step\n');
    out = '';
    expect(await main(['--no-state', '--summary', 'summary.md', '--ingest-out', 'ingest.json', '--json', 'r.json'], io(dir))).toBe(1);
    const md = await readFile(join(dir, 'summary.md'), 'utf8');
    expect(md.startsWith('# earlier step\n## Dawnfix Flare: Cloudflare audit')).toBe(true);
    expect(md).toContain('| Severity | Check | Account | Resource | Finding | Fix |');
    expect(md).toContain('| high | workers.dev exposure | Example Co | shop |');
    const doc = JSON.parse(await readFile(join(dir, 'ingest.json'), 'utf8'));
    conforms(doc);
    const r = JSON.parse(await readFile(join(dir, 'r.json'), 'utf8'));
    expect(r.pitch).toEqual(BRAND.pitch);
    expect(err).toBe('');
  });

  it('audits a replayed snapshot as of its takenAt, whatever the clock says', async () => {
    const dir = await mkdtemp(join(tmpdir(), 'flare-replay-'));
    const later = { ...io(dir, {}), now: () => new Date('2031-01-01T00:00:00Z') };
    out = '';
    await main(['--snapshot-in', DEMO, '--json', '--fail-on', 'never'], later);
    expect(JSON.parse(out).generatedAt).toBe(demo().takenAt);
  });
});

describe('the Markdown summary', () => {
  it('escapes names so they cannot break the table or add markup', () => {
    expect(mdCell('a|b')).toBe('a\\|b');
    expect(mdCell('<img src=x onerror=alert(1)>')).toBe('&lt;img src=x onerror=alert(1)&gt;');
    expect(mdCell('line\nbreak')).toBe('line break');
    expect(mdCell('`code` *bold* [link](x)')).toBe("'code' \\*bold\\* \\[link\\](x)");
  });
  it('says so when there is nothing to report', () => {
    const md = renderMarkdown({ generatedAt: NOW.toISOString(), findings: [], gaps: [], summary: { critical: 0, high: 0, medium: 0, low: 0, info: 0 }, accounts: [], localFiles: 0 });
    expect(md).toContain('**no findings**');
    expect(md).not.toContain('| Severity |');
  });
});

describe('token permissions', () => {
  it('the README table is TOKEN_PERMISSIONS, row for row', () => {
    const readme = readFileSync(join(ROOT, 'README.md'), 'utf8');
    const table = readme.slice(readme.indexOf('| Permission (dashboard name) |')).split('\n\n')[0]!;
    const rows = table.split('\n').slice(2).filter((l) => l.startsWith('|'));
    expect(rows.slice(0, TOKEN_PERMISSIONS.length)).toEqual(TOKEN_PERMISSIONS.map((p) => `| ${p.scope} > ${p.group} | ${p.level} | ${p.usedFor} |`));
    expect(rows[TOKEN_PERMISSIONS.length]).toBeUndefined();
    expect(TOKEN_PERMISSIONS.map(permissionLine)).toContain('Zone > Workers Routes > Read');
    expect(TOKEN_PERMISSIONS.map(permissionLine)).toContain('Zone > Zone Settings > Read');
  });
});
