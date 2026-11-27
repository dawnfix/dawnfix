import { mkdtemp, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { beforeEach, describe, expect, it } from 'vitest';
import { main, type Io } from '../src/cli.js';
import { fakeCloudflare, NOW, SECRET_VALUE, type Fake } from './fixtures/cloudflare.js';
import { REPOS } from './helpers.js';

let dir: string;
let fake: Fake;
let out: string;
let err: string;
const io = (env: Record<string, string> = { CF_API_TOKEN: 'test-token' }): Io => ({
  env,
  fetch: fake.fetch,
  stdout: (s) => void (out += s),
  stderr: (s) => void (err += s),
  now: () => NOW,
  isTTY: false,
  columns: 140,
  cwd: dir,
});

beforeEach(async () => {
  dir = await mkdtemp(join(tmpdir(), 'flare-'));
  fake = fakeCloudflare();
  out = '';
  err = '';
});

describe('cli', () => {
  it('prints the table and exits 1 on a high finding', async () => {
    const code = await main(['--state', join(dir, 's.json')], io());
    expect(code).toBe(1);
    expect(out).toContain('Reachable on workers.dev');
    expect(err).toBe('');
  });

  it('--fail-on never exits 0; a bad level is a usage error', async () => {
    expect(await main(['--no-state', '--fail-on', 'never'], io())).toBe(0);
    expect(await main(['--no-state', '--fail-on', 'loud'], io())).toBe(2);
    expect(err).toContain('--fail-on must be one of');
  });

  it('--json writes JSON to stdout, --json FILE and --html FILE write files', async () => {
    await main(['--no-state', '--json'], io());
    const parsed = JSON.parse(out);
    expect(parsed.findings.length).toBeGreaterThan(10);
    expect(parsed.summary.high).toBeGreaterThan(0);

    out = '';
    await main(['--no-state', '--json', 'r.json', '--html', 'r.html'], io());
    expect(JSON.parse(await readFile(join(dir, 'r.json'), 'utf8')).findings).toHaveLength(parsed.findings.length);
    expect(await readFile(join(dir, 'r.html'), 'utf8')).toMatch(/^<!doctype html>/);
    expect(out).toContain('SEVERITY'); // table still printed when JSON goes to a file
  });

  it('keeps secret names between runs and reports the change; never writes a value', async () => {
    const state = join(dir, 'state.json');
    await main(['--state', state, '--json'], io());
    const saved = await readFile(state, 'utf8');
    expect(saved).toContain('STRIPE_KEY');
    expect(saved).not.toContain(SECRET_VALUE);
    expect(out).not.toContain(SECRET_VALUE);

    fake = fakeCloudflare({ override: { '/accounts/0123456789abcdef0123456789abcdef/workers/scripts/shop/secrets': { success: true, result: [{ name: 'API_KEY', type: 'secret_text' }] } } });
    out = '';
    await main(['--state', state, '--json'], io());
    const f = JSON.parse(out).findings.filter((x: { check: string }) => x.check === 'secrets-changed');
    expect(f[0].detail).toContain('removed STRIPE_KEY');
  });

  it('scans repos given after --repos (shell-expanded) and with a quoted glob', async () => {
    await main(['--no-state', '--no-api', '--json', '--repos', join(REPOS, 'shop'), join(REPOS, 'blog')], io({}));
    const a = JSON.parse(out);
    expect(a.localFiles).toBe(2);
    expect(a.findings.some((f: { resource: string }) => f.resource === 'namespace 1001')).toBe(true);
    expect(fake.calls).toHaveLength(0);

    out = '';
    await main(['--no-state', '--no-api', '--json', '--repos', `${REPOS}/*`], io({}));
    expect(JSON.parse(out).localFiles).toBe(3);
    expect(JSON.parse(out).gaps.map((g: { what: string }) => g.what).join()).toContain('broken/wrangler.toml');
  });

  it('reads tokens from the env vars named by --token-env, never from argv', async () => {
    await main(['--no-state', '--token-env', 'A', '--token-env', 'B', '--json'], io({ A: 'test-token', B: 'second-token' }));
    expect(new Set(fake.calls.map((c) => c.auth))).toEqual(new Set(['Bearer test-token', 'Bearer second-token']));
    expect(await main(['--no-state'], io({}))).toBe(2);
    expect(err).toContain('no token: set CF_API_TOKEN or CLOUDFLARE_API_TOKEN');
    expect(await main(['--token', 'x'], io())).toBe(2);
  });

  it('applies flare.config.json and rejects unknown keys or inline tokens', async () => {
    const { writeFile } = await import('node:fs/promises');
    await writeFile(join(dir, 'flare.config.json'), JSON.stringify({ publicHostnames: ['*.example.com'], failOn: 'never' }));
    expect(await main(['--no-state', '--json'], io())).toBe(0);
    expect(JSON.parse(out).findings.some((f: { check: string }) => f.check === 'hostname-without-auth')).toBe(false);

    await writeFile(join(dir, 'bad.json'), JSON.stringify({ token: 'abc' }));
    expect(await main(['--config', 'bad.json'], io())).toBe(2);
    expect(err).toContain('put tokens in environment variables');
    await writeFile(join(dir, 'bad2.json'), JSON.stringify({ publicHostname: ['x'] }));
    expect(await main(['--config', 'bad2.json'], io())).toBe(2);
    expect(err).toContain('unknown key "publicHostname"');
  });

  it('round-trips a snapshot so an audit can be replayed offline', async () => {
    await main(['--no-state', '--snapshot-out', 'snap.json', '--json'], io());
    const first = JSON.parse(out);
    expect(await readFile(join(dir, 'snap.json'), 'utf8')).not.toContain(SECRET_VALUE);
    fake = fakeCloudflare();
    out = '';
    await main(['--snapshot-in', 'snap.json', '--json'], io({}));
    expect(JSON.parse(out).findings).toEqual(first.findings);
    expect(fake.calls).toHaveLength(0);
  });

  it('--help', async () => {
    expect(await main(['--help'], io())).toBe(0);
    expect(out).toContain('--token-env NAME');
  });
});
