// The follow-ups from the first build (BUILD-NOTES, Flare): Access in front of workers.dev,
// cron-only Workers, and token permission groups listed by id.

import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { collectSnapshot } from '../src/core/audit.js';
import { cronOnly } from '../src/core/checks/exposure.js';
import { mapAccessApp, mapToken, resolveGroupNames, unnamedGroupIds } from '../src/core/collect.js';
import type { LocalWorker, Snapshot } from '../src/core/types.js';
import { scanRepos } from '../src/node/scan.js';
import { ACCESS_APPS, ACCOUNT_ID, ACCOUNT_TOKENS, fakeCloudflare, NOW } from './fixtures/cloudflare.js';
import { apiSnapshot, byCheck, run } from './helpers.js';

const EXTRA = resolve(import.meta.dirname, 'fixtures/repos-extra');
const localOnly = (workers: LocalWorker[]): Snapshot => ({ takenAt: NOW.toISOString(), accounts: [], local: workers, localGaps: [] });

describe('Access in front of workers.dev', () => {
  const withApps = async (apps: unknown[]) =>
    apiSnapshot({ override: { [`/accounts/${ACCOUNT_ID}/access/apps`]: { success: true, result: [...ACCESS_APPS, ...apps] } } });
  const sev = (s: Snapshot, check: string) => byCheck(run(s), check).map((f) => [f.resource, f.severity, f.title]);

  it('a self-hosted app on the script\'s workers.dev hostname makes it low', async () => {
    const s = await withApps([{ id: 'a3', name: 'shop on workers.dev', type: 'self_hosted', domain: 'shop.acme-sub.workers.dev' }]);
    expect(sev(s, 'workers-dev-enabled')).toEqual([['shop', 'low', 'Reachable on workers.dev, around its custom domain (behind Access)']]);
    // that app names one hostname: the preview URLs are still open
    expect(sev(s, 'preview-urls-enabled')).toEqual([['shop', 'medium', 'Preview URLs enabled']]);
  });

  it('a wildcard app on the subdomain covers workers.dev and preview URLs', async () => {
    const s = await withApps([{ id: 'a4', name: 'all of workers.dev', type: 'self_hosted', self_hosted_domains: ['*.acme-sub.workers.dev'] }]);
    expect(sev(s, 'workers-dev-enabled')[0]?.[1]).toBe('low');
    expect(sev(s, 'preview-urls-enabled')).toEqual([['shop', 'low', 'Preview URLs enabled (behind Access)']]);
  });

  it('worker and all_workers destinations count (field names unverified, several read)', async () => {
    const one = await withApps([{ id: 'a5', type: 'self_hosted', destinations: [{ type: 'worker', script_name: 'shop' }] }]);
    expect(sev(one, 'workers-dev-enabled')[0]?.[1]).toBe('low');
    const other = await withApps([{ id: 'a6', type: 'self_hosted', destinations: [{ type: 'worker', script_name: 'blog' }] }]);
    expect(sev(other, 'workers-dev-enabled')[0]?.[1]).toBe('high');
    const all = await withApps([{ id: 'a7', type: 'self_hosted', destinations: [{ type: 'all_workers' }] }]);
    expect(sev(all, 'workers-dev-enabled')[0]?.[1]).toBe('low');
    expect(sev(all, 'preview-urls-enabled')[0]?.[1]).toBe('low');
    expect(mapAccessApp({ destinations: [{ type: 'worker', worker_name: 'x' }, { type: 'all_workers' }, { type: 'public', uri: 'a.example.com' }] })).toMatchObject({
      workers: ['x'],
      allWorkers: true,
      domains: ['a.example.com'],
    });
  });

  it('an app on a path, or on another subdomain, does not', async () => {
    const s = await withApps([
      { id: 'a8', type: 'self_hosted', domain: 'shop.acme-sub.workers.dev/admin' },
      { id: 'a9', type: 'self_hosted', domain: '*.other-sub.workers.dev' },
    ]);
    expect(sev(s, 'workers-dev-enabled')[0]?.[1]).toBe('high');
  });
});

describe('cron-only Workers', () => {
  it('reads handlers from the source: a call to fetch is not a handler; a framework default export is opaque', async () => {
    const r = await scanRepos([`${EXTRA}/*`], { base: EXTRA });
    const by = Object.fromEntries(r.workers.map((w) => [w.name, w]));
    expect(by.nightly?.entry).toEqual({ fetch: false, scheduled: true, opaqueDefault: false });
    expect(by.nightly?.crons).toEqual(['15 3 * * *']);
    expect(by['hono-app']?.entry).toEqual({ fetch: false, scheduled: false, opaqueDefault: true });
    expect(by.both?.entry).toEqual({ fetch: true, scheduled: true, opaqueDefault: false });
    expect(r.workers.filter(cronOnly).map((w) => w.name)).toEqual(['nightly']);
  });

  it('workers.dev on by default is low for a cron-only Worker, medium otherwise', async () => {
    const r = await scanRepos([`${EXTRA}/*`], { base: EXTRA });
    const f = byCheck(run(localOnly(r.workers)), 'workers-dev-enabled').map((x) => [x.resource, x.severity]);
    expect(f.sort()).toEqual([
      ['both', 'medium'],
      ['hono-app', 'medium'],
      ['nightly', 'low'],
    ]);
    const nightly = byCheck(run(localOnly(r.workers)), 'workers-dev-enabled').find((x) => x.resource === 'nightly');
    expect(nightly?.detail).toContain('no fetch handler');
  });

  it('without source read, nothing is downgraded', () => {
    const w: LocalWorker = { name: 'w', file: 'w/wrangler.jsonc', routes: [], ratelimitNamespaces: [], authMarkers: [], crons: ['0 1 * * *'] };
    expect(cronOnly(w)).toBe(false);
    expect(byCheck(run(localOnly([w])), 'workers-dev-enabled')[0]?.severity).toBe('medium');
  });

  it('environments inherit triggers', async () => {
    const { workersFromConfig } = await import('../src/core/wrangler.js');
    const ws = workersFromConfig({ name: 'n', triggers: { crons: ['1 1 * * *'] }, env: { staging: {}, prod: { triggers: { crons: [] } } } }, 'f');
    expect(ws.map((w) => [w.name, w.crons])).toEqual([
      ['n', ['1 1 * * *']],
      ['n-staging', ['1 1 * * *']],
      ['n-prod', undefined],
    ]);
  });
});

describe('token permission groups listed by id', () => {
  const idOnly = {
    id: 'tok-ids',
    name: 'ids-only',
    status: 'active',
    issued_on: '2026-01-01T00:00:00Z',
    policies: [{ id: 'p9', effect: 'allow', permission_groups: [{ id: 'c8fed203ed3043cba015a93ad1616f1f' }, { id: 'e086da7e2179491d91ee5f35b3ca210a' }], resources: { 'com.cloudflare.api.account.*': '*' } }],
  };

  it('keeps ids, and resolves names from the permission-groups list', () => {
    const t = mapToken(idOnly, 'account');
    expect(t.policies[0]?.permissionGroupIds).toEqual(['c8fed203ed3043cba015a93ad1616f1f', 'e086da7e2179491d91ee5f35b3ca210a']);
    expect(unnamedGroupIds([t])).toHaveLength(2);
    resolveGroupNames([t], new Map([['e086da7e2179491d91ee5f35b3ca210a', 'Workers Scripts Write']]));
    expect(t.policies[0]?.permissionGroups).toEqual(['c8fed203ed3043cba015a93ad1616f1f', 'Workers Scripts Write']);
    // a token whose groups have names needs no lookup
    expect(unnamedGroupIds([mapToken(ACCOUNT_TOKENS[0]!, 'account')])).toEqual([]);
  });

  it('collect looks the names up only when a group has none, so over-scope still fires', async () => {
    const path = `/accounts/${ACCOUNT_ID}/tokens`;
    const f = fakeCloudflare({
      override: {
        [path]: { success: true, result: [...ACCOUNT_TOKENS, idOnly], result_info: { page: 1, total_pages: 1 } },
        [`${path}/permission_groups`]: { success: true, result: [{ id: 'e086da7e2179491d91ee5f35b3ca210a', name: 'Workers Scripts Write', scopes: ['com.cloudflare.api.account'] }] },
      },
    });
    const { snapshot } = await collectSnapshot({ tokens: ['test-token'], fetch: f.fetch, now: NOW });
    expect(f.calls.filter((c) => c.url.includes('permission_groups'))).toHaveLength(1);
    const over = byCheck(run(snapshot), 'token-over-scoped').map((x) => [x.resource, x.severity]);
    expect(over).toContainEqual(['ids-only (account token)', 'high']);

    const plain = fakeCloudflare();
    await collectSnapshot({ tokens: ['test-token'], fetch: plain.fetch, now: NOW });
    expect(plain.calls.filter((c) => c.url.includes('permission_groups'))).toEqual([]);
  });

  it('an unreadable list is a gap, not a failure', async () => {
    const path = `/accounts/${ACCOUNT_ID}/tokens`;
    const f = fakeCloudflare({ override: { [path]: { success: true, result: [idOnly] } }, deny: [`${path}/permission_groups`] });
    const { snapshot } = await collectSnapshot({ tokens: ['test-token'], fetch: f.fetch, now: NOW });
    expect(snapshot.accounts[0]?.gaps.map((g) => g.what)).toContain('permission group names');
  });
});
