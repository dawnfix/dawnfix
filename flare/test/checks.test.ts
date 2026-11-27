// One block per check: the planted problem in the fixture account is found, the clean
// neighbour next to it is not, and the knobs (allowlists, thresholds) move the result.

import { beforeAll, describe, expect, it } from 'vitest';
import { nextFreeBlock } from '../src/core/checks/ratelimit.js';
import { tokenIssues } from '../src/core/checks/tokens.js';
import { mapToken } from '../src/core/collect.js';
import type { LocalWorker, Snapshot } from '../src/core/types.js';
import { scanRepos } from '../src/node/scan.js';
import { ACCOUNT_ID, ACCOUNT_TOKENS, NOW } from './fixtures/cloudflare.js';
import { apiSnapshot, byCheck, REPOS, run } from './helpers.js';

let snap: Snapshot;
let local: LocalWorker[];
beforeAll(async () => {
  snap = await apiSnapshot();
  local = (await scanRepos([`${REPOS}/*`], { base: REPOS })).workers;
});
const withLocal = async () => apiSnapshot({}, local);
const lw = (over: Partial<LocalWorker>): LocalWorker => ({ name: 'w', file: 'w/wrangler.jsonc', routes: [], ratelimitNamespaces: [], authMarkers: [], ...over });
const localOnly = (workers: LocalWorker[]): Snapshot => ({ takenAt: NOW.toISOString(), accounts: [], local: workers, localGaps: [] });

describe('workers-dev-enabled', () => {
  it('is high for a Worker that also has a custom domain', () => {
    const f = byCheck(run(snap), 'workers-dev-enabled');
    expect(f.map((x) => [x.resource, x.severity])).toEqual([['shop', 'high']]);
    expect(f[0]!.detail).toContain('shop.acme-sub.workers.dev');
    expect(f[0]!.detail).toContain('shop.example.com');
  });
  it('is medium when workers.dev is the only address, low with no fetch handler', () => {
    const s = structuredClone(snap);
    const a = s.accounts[0]!;
    a.customDomains = a.customDomains!.filter((d) => d.service !== 'shop');
    a.scripts!.find((x) => x.name === 'queue-consumer')!.subdomain = { enabled: true, previewsEnabled: false };
    const f = byCheck(run(s), 'workers-dev-enabled');
    expect(f.map((x) => [x.resource, x.severity]).sort()).toEqual([
      ['queue-consumer', 'low'],
      ['shop', 'medium'],
    ]);
  });
  it('local: absent with no routes defaults to on; absent with routes is info; explicit false is clean', () => {
    const r = run(localOnly([lw({ name: 'a' }), lw({ name: 'b', routes: [{ pattern: 'b.example.com', customDomain: true }] }), lw({ name: 'c', workersDev: false, previewUrls: false })]));
    expect(byCheck(r, 'workers-dev-enabled').map((x) => [x.resource, x.severity])).toEqual([
      ['a', 'medium'],
      ['b', 'info'],
    ]);
  });
  it('local: catches a staging env that turns it back on', async () => {
    const f = byCheck(run(await withLocal()), 'workers-dev-enabled').filter((x) => x.source === 'local');
    expect(f.map((x) => x.resource)).toEqual(['blog-staging']);
  });
});

describe('preview-urls-enabled', () => {
  it('flags previews from the API', () => {
    expect(byCheck(run(snap), 'preview-urls-enabled').map((x) => [x.resource, x.severity])).toEqual([['shop', 'medium']]);
  });
  it('local: absent follows workers_dev', () => {
    const r = run(localOnly([lw({ name: 'a' }), lw({ name: 'b', workersDev: false }), lw({ name: 'c', previewUrls: true, workersDev: false })]));
    expect(byCheck(r, 'preview-urls-enabled').map((x) => [x.resource, x.severity])).toEqual([
      ['c', 'medium'],
      ['a', 'low'],
      ['b', 'info'],
    ]);
  });
});

describe('hostname-without-auth', () => {
  it('flags hostnames with neither Access nor app sign-in; Access on the whole host is clean', () => {
    const f = byCheck(run(snap), 'hostname-without-auth');
    expect(f.map((x) => [x.resource, x.severity, x.title]).sort()).toEqual([
      ['blog.example.com', 'medium', 'No Access application and no app sign-in found'],
      ['internal.example.com', 'low', 'Access covers only some paths'],
      ['shop.example.com', 'medium', 'No Access application and no app sign-in found'],
    ]);
  });
  it('honours the public allowlist (wildcards too) and appAuthScripts', () => {
    const f = byCheck(run(snap, { publicHostnames: ['*.example.com'], appAuthScripts: [] }), 'hostname-without-auth');
    expect(f).toEqual([]);
    const g = byCheck(run(snap, { appAuthScripts: ['shop'] }), 'hostname-without-auth');
    expect(g.map((x) => x.resource)).not.toContain('shop.example.com');
  });
  it('accepts an auth marker found in the repo', async () => {
    const s = await apiSnapshot({}, [lw({ name: 'shop', authMarkers: ['passkey / WebAuthn'] })]);
    expect(byCheck(run(s), 'hostname-without-auth').map((x) => x.resource)).not.toContain('shop.example.com');
  });
  it('says "unverified" when Access could not be read', async () => {
    const s = await apiSnapshot({ deny: [`/accounts/${ACCOUNT_ID}/access/apps`] });
    const f = byCheck(run(s), 'hostname-without-auth');
    expect(f.find((x) => x.resource === 'admin.example.com')?.severity).toBe('low');
    expect(f[0]!.detail).toMatch(/could not be read/);
  });
  it('local-only Workers with no marker are info; with a marker they are clean', () => {
    const r = run(localOnly([lw({ name: 'a', routes: [{ pattern: 'a.example.net/*', customDomain: false }] }), lw({ name: 'b', routes: [{ pattern: 'b.example.net', customDomain: true }], authMarkers: ['sign-in route'] })]));
    expect(byCheck(r, 'hostname-without-auth').map((x) => [x.resource, x.severity])).toEqual([['a.example.net', 'info']]);
  });
});

describe('ratelimit-namespace-shared', () => {
  it('API: a clash across Workers is high, two bindings in one Worker is medium', () => {
    const f = byCheck(run(snap), 'ratelimit-namespace-shared');
    expect(f.map((x) => [x.resource, x.severity])).toEqual([
      ['namespace 1001', 'high'],
      ['namespace 1101', 'medium'],
    ]);
    expect(f[0]!.detail).toContain('shop.PAGE_LIMIT');
    expect(f[0]!.detail).toContain('blog.PAGE_LIMIT');
  });
  it('joins local files with API bindings without double-counting the same binding', async () => {
    const f = byCheck(run(await withLocal()), 'ratelimit-namespace-shared').find((x) => x.resource === 'namespace 1001')!;
    expect(f.title).toBe('Ratelimit namespace 1001 shared by 3 Workers');
    expect(f.source).toBe('api+local');
    expect(f.detail).toContain('blog-staging.PAGE_LIMIT');
  });
  it('local files alone are enough', () => {
    const r = run(localOnly([lw({ name: 'a', ratelimitNamespaces: [{ binding: 'L', namespaceId: '1101' }] }), lw({ name: 'b', ratelimitNamespaces: [{ binding: 'L', namespaceId: '1101' }] }), lw({ name: 'c', ratelimitNamespaces: [{ binding: 'L', namespaceId: '1201' }] })]));
    const f = byCheck(r, 'ratelimit-namespace-shared');
    expect(f.map((x) => [x.account, x.resource, x.severity])).toEqual([['local', 'namespace 1101', 'high']]);
    expect(f[0]!.fix).toContain('1301-1399');
  });
  it('suggests the next free hundred-block', () => {
    expect(nextFreeBlock(['1201', '1202', '2402', 'abc'])).toBe('2501');
    expect(nextFreeBlock(['x'])).toBeUndefined();
  });
});

describe('route-to-missing-script', () => {
  it('flags a zone route and a custom domain whose Worker is gone; ignores script-less routes', () => {
    const f = byCheck(run(snap), 'route-to-missing-script');
    expect(f.map((x) => [x.resource, x.severity])).toEqual([
      ['legacy.example.com/*', 'high'],
      ['old.example.com', 'high'],
    ]);
  });
  it('stays quiet when the scripts list could not be read', async () => {
    const s = await apiSnapshot({ deny: [`/accounts/${ACCOUNT_ID}/workers/scripts`] });
    expect(byCheck(run(s), 'route-to-missing-script')).toEqual([]);
  });
});

describe('dangling-dns', () => {
  it('finds CNAMEs to missing workers.dev scripts, foreign subdomains, dead sibling names and orphan placeholders', () => {
    const f = byCheck(run(snap), 'dangling-dns');
    expect(f.map((x) => [x.resource, x.severity]).sort()).toEqual([
      ['docs.example.com', 'medium'],
      ['edge.example.com', 'medium'],
      ['stale.example.com', 'medium'],
      ['status.example.com', 'high'],
    ]);
  });
  it('a placeholder record with a route or custom domain, and a CNAME covered by a wildcard, are clean', () => {
    const names = byCheck(run(snap), 'dangling-dns').map((x) => x.resource);
    for (const ok of ['shop.example.com', 'blog.example.com', 'legacy.example.com', 'cdn.example.com', 'www.example.com']) expect(names).not.toContain(ok);
  });
  it('does not call placeholders orphaned when routes were unreadable', async () => {
    const s = await apiSnapshot({ deny: ['/zones/aaaa0000aaaa0000aaaa0000aaaa0000/workers/routes'] });
    expect(byCheck(run(s), 'dangling-dns').map((x) => x.resource)).not.toContain('stale.example.com');
  });
});

describe('dead-script', () => {
  it('flags a scheduled script whose crons are gone and which is old; cron, queue and service-bound scripts are alive', () => {
    const f = byCheck(run(snap), 'dead-script');
    expect(f.map((x) => [x.resource, x.severity, x.title])).toEqual([['old-cron', 'medium', 'Unreachable and not deployed for a long time']]);
  });
  it('a live cron keeps it reachable; staleDays moves the age cut-off', () => {
    const s = structuredClone(snap);
    s.accounts[0]!.scripts!.find((x) => x.name === 'old-cron')!.crons = ['0 3 * * *'];
    expect(byCheck(run(s), 'dead-script').map((x) => [x.resource, x.severity])).toEqual([['old-cron', 'low']]);
    expect(byCheck(run(s, { staleDays: 1000 }), 'dead-script')).toEqual([]);
    expect(byCheck(run(snap, { staleDays: 20 }), 'dead-script').map((x) => x.resource)).toContain('blog');
  });
});

describe('compat-date-old', () => {
  it('low past the threshold, medium past twice it', () => {
    const f = byCheck(run(snap), 'compat-date-old');
    expect(f.map((x) => [x.resource, x.severity])).toEqual([
      ['blog', 'medium'],
      ['old-cron', 'low'],
    ]);
    expect(byCheck(run(snap, { compatMonths: 60 }), 'compat-date-old')).toEqual([]);
  });
  it('local files report Workers the API did not see', () => {
    const r = run(localOnly([lw({ name: 'a', compatibilityDate: '2025-01-01' }), lw({ name: 'b', compatibilityDate: '2026-10-01' }), lw({ name: 'c', compatibilityDate: 'nope' })]));
    expect(byCheck(r, 'compat-date-old').map((x) => [x.resource, x.severity])).toEqual([['a', 'low']]);
  });
});

describe('secrets-changed', () => {
  it('first run records names only and reports nothing', () => {
    const r = run(snap);
    expect(byCheck(r, 'secrets-changed')).toEqual([]);
    expect(r.secretsBaseline[`${ACCOUNT_ID}/shop`]).toEqual(['API_KEY', 'STRIPE_KEY']);
  });
  it('reports added and removed names against the baseline', () => {
    const r = run(snap, { secretsBaseline: { [`${ACCOUNT_ID}/shop`]: ['API_KEY', 'OLD_KEY'], [`${ACCOUNT_ID}/gone-now`]: ['X'] } });
    const f = byCheck(r, 'secrets-changed');
    expect(f).toHaveLength(1);
    expect(f[0]!.severity).toBe('medium');
    expect(f[0]!.detail).toBe('added STRIPE_KEY; removed OLD_KEY. Names only; values are never read.');
    expect(r.secretsBaseline[`${ACCOUNT_ID}/gone-now`]).toEqual(['X']);
  });
  it('added only is low', () => {
    const r = run(snap, { secretsBaseline: { [`${ACCOUNT_ID}/shop`]: ['API_KEY'] } });
    expect(byCheck(r, 'secrets-changed')[0]!.severity).toBe('low');
  });
});

describe('tokens', () => {
  it('write on all accounts is high, no expiry is medium, unused is low; scoped and disabled tokens are clean', () => {
    const r = run(snap);
    const f = r.result.findings.filter((x) => x.check.startsWith('token-'));
    expect(f.map((x) => [x.check, x.resource, x.severity])).toEqual([
      ['token-over-scoped', 'ci-deploy (account token)', 'high'],
      ['token-no-expiry', 'ci-deploy (account token)', 'medium'],
      ['token-unused', 'old-laptop (user token)', 'low'],
    ]);
  });
  it('many write groups on one account is medium', () => {
    const t = mapToken(
      { id: 't', name: 'kitchen-sink', expires_on: '2027-01-01T00:00:00Z', policies: [{ effect: 'allow', permission_groups: Array.from({ length: 9 }, (_, i) => ({ name: `Thing ${i} Write` })), resources: { [`com.cloudflare.api.account.${ACCOUNT_ID}`]: '*' } }] },
      'account',
    );
    expect(tokenIssues(t, NOW).map((x) => [x.check, x.severity])).toEqual([['token-over-scoped', 'medium']]);
  });
  it('reads nested zone resources as all-zones', () => {
    const t = mapToken({ ...ACCOUNT_TOKENS[0], policies: [{ effect: 'allow', permission_groups: [{ name: 'DNS Write' }], resources: { [`com.cloudflare.api.account.${ACCOUNT_ID}`]: { 'com.cloudflare.api.account.zone.*': '*' } } }] }, 'account');
    expect(tokenIssues(t, NOW)[0]!.detail).toContain('every zone');
  });
});

describe('zone-tls', () => {
  it('flags TLS 1.0, HTTPS off and HSTS off on one zone, nothing on the hardened one', () => {
    const f = byCheck(run(snap), 'zone-tls');
    expect(f.map((x) => [x.resource, x.title, x.severity])).toEqual([
      ['example.com', 'Minimum TLS 1.0', 'medium'],
      ['example.com', 'Always Use HTTPS is off', 'medium'],
      ['example.com', 'HSTS off', 'low'],
    ]);
  });
  it('flags a short HSTS max-age', () => {
    const s = structuredClone(snap);
    s.accounts[0]!.zones![1]!.settings!.hsts!.maxAge = 300;
    expect(byCheck(run(s), 'zone-tls').map((x) => x.title)).toContain('HSTS max-age 300s');
  });
});

describe('ordering and summary', () => {
  it('sorts by severity and counts each level', () => {
    const r = run(snap).result;
    const ranks = r.findings.map((x) => ['critical', 'high', 'medium', 'low', 'info'].indexOf(x.severity));
    expect(ranks).toEqual([...ranks].sort((a, b) => a - b));
    expect(Object.values(r.summary).reduce((a, b) => a + b, 0)).toBe(r.findings.length);
  });
});
